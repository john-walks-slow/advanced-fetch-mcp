from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, PropertyMock, patch

from fastmcp.utilities.types import Image as FastMCPImage
from mcp.types import TextContent


class ReadImageTests(unittest.IsolatedAsyncioTestCase):
    def _import_server(self):
        import importlib, sys

        sys.modules.pop("advanced_fetch_mcp.server", None)
        return importlib.import_module("advanced_fetch_mcp.server")

    async def asyncSetUp(self):
        self.server = self._import_server()
        self.ctx = MagicMock()

    @patch("advanced_fetch_mcp.server.requests.Session.get")
    async def test_single_url_success(self, mock_get):
        """read_image with a single URL returns an ImageContent."""
        mock_resp = MagicMock()
        mock_resp.content = b"\x89PNG\r\n\x1a\n...fake-png-data..."
        mock_resp.headers = {"content-type": "image/png"}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        results = await self.server.read_image(
            ctx=self.ctx, url="https://example.com/image.png"
        )

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], FastMCPImage)
        self.assertEqual(results[0].data, b"\x89PNG\r\n\x1a\n...fake-png-data...")
        mock_get.assert_called_once_with(
            "https://example.com/image.png",
            timeout=30.0,
            proxies=mock_get.call_args[1].get("proxies"),
            verify=mock_get.call_args[1].get("verify"),
        )

    @patch("advanced_fetch_mcp.server.requests.Session.get")
    async def test_multiple_urls(self, mock_get):
        """read_image with multiple URLs returns multiple ImageContents."""
        mock_resp = MagicMock()
        mock_resp.content = b"fake-image"
        mock_resp.headers = {"content-type": "image/jpeg"}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        results = await self.server.read_image(
            ctx=self.ctx,
            url=[
                "https://example.com/a.jpg",
                "https://example.com/b.jpg",
            ],
        )

        self.assertEqual(len(results), 2)
        for r in results:
            self.assertIsInstance(r, FastMCPImage)
        self.assertEqual(mock_get.call_count, 2)

    @patch("advanced_fetch_mcp.server.requests.Session.get")
    async def test_url_failure_returns_text(self, mock_get):
        """When a URL fails, read_image returns a TextContent with error message."""
        mock_get.side_effect = Exception("Connection refused")

        results = await self.server.read_image(
            ctx=self.ctx, url="https://example.com/bad.png"
        )

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], TextContent)
        self.assertIn("Connection refused", results[0].text)
        self.assertIn("bad.png", results[0].text)

    @patch("advanced_fetch_mcp.server.requests.Session.get")
    async def test_mixed_success_failure(self, mock_get):
        """Mixed success and failure URLs produce corresponding results."""
        good_resp = MagicMock()
        good_resp.content = b"\x89PNG-data"
        good_resp.headers = {"content-type": "image/png"}
        good_resp.raise_for_status = MagicMock()

        def side_effect(url, **kw):
            if "good" in url:
                return good_resp
            raise Exception("Not found")

        mock_get.side_effect = side_effect

        results = await self.server.read_image(
            ctx=self.ctx,
            url=["https://example.com/good.png", "https://example.com/missing.png"],
        )

        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], FastMCPImage)
        self.assertIsInstance(results[1], TextContent)
        self.assertIn("Not found", results[1].text)

    @patch("advanced_fetch_mcp.server.requests.Session.get")
    async def test_format_detection_jpeg(self, mock_get):
        """Content-Type image/jpeg infers format='jpeg'."""
        mock_resp = MagicMock()
        mock_resp.content = b"fake-jpeg"
        mock_resp.headers = {"content-type": "image/jpeg"}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        results = await self.server.read_image(
            ctx=self.ctx, url="https://example.com/photo"
        )
        self.assertIsInstance(results[0], FastMCPImage)
        # FastMCP's Image stores format as _format internally
        self.assertEqual(results[0]._format, "jpeg")

    @patch("advanced_fetch_mcp.server.requests.Session.get")
    async def test_empty_urls_list(self, mock_get):
        """Empty URL list returns an error TextContent."""
        results = await self.server.read_image(ctx=self.ctx, url=[])

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], TextContent)
        self.assertIn("No URLs provided", results[0].text)
        mock_get.assert_not_called()

    @patch("advanced_fetch_mcp.server.requests.Session.get")
    async def test_non_image_content_type(self, mock_get):
        """Non-image content types still create an Image with fallback format."""
        mock_resp = MagicMock()
        mock_resp.content = b"<html>not an image</html>"
        mock_resp.headers = {"content-type": "text/html"}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        results = await self.server.read_image(
            ctx=self.ctx, url="https://example.com/not-image"
        )

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], FastMCPImage)
        # Falls back to png
        self.assertEqual(results[0]._format, "png")

    @patch("advanced_fetch_mcp.server.requests.Session.get")
    async def test_content_type_with_charset(self, mock_get):
        """Content-Type with charset is parsed correctly."""
        mock_resp = MagicMock()
        mock_resp.content = b"fake-gif"
        mock_resp.headers = {"content-type": "image/gif; charset=utf-8"}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        results = await self.server.read_image(
            ctx=self.ctx, url="https://example.com/animated.gif"
        )

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], FastMCPImage)
        self.assertEqual(results[0]._format, "gif")

    @patch("advanced_fetch_mcp.server.requests.Session.get")
    async def test_http_error_status(self, mock_get):
        """HTTP error status code returns a TextContent with error."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("HTTP 404 Not Found")
        mock_get.return_value = mock_resp

        results = await self.server.read_image(
            ctx=self.ctx, url="https://example.com/missing.png"
        )

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], TextContent)
        self.assertIn("HTTP 404", results[0].text)

    @patch("advanced_fetch_mcp.server.requests.Session.get")
    async def test_custom_timeout(self, mock_get):
        """Custom timeout parameter is forwarded to requests."""
        mock_resp = MagicMock()
        mock_resp.content = b"fake"
        mock_resp.headers = {"content-type": "image/png"}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        await self.server.read_image(
            ctx=self.ctx, url="https://example.com/img.png", timeout=15.0
        )

        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["timeout"], 15.0)
        # headers should not be in kwargs (set on session, not per-request)
        self.assertNotIn("headers", kwargs)


class DownloadTests(unittest.IsolatedAsyncioTestCase):
    def _import_server(self):
        import importlib, sys

        sys.modules.pop("advanced_fetch_mcp.server", None)
        return importlib.import_module("advanced_fetch_mcp.server")

    async def asyncSetUp(self):
        self.server = self._import_server()
        self.ctx = MagicMock()

    @patch("advanced_fetch_mcp.server.requests.Session.get")
    async def test_download_success(self, mock_get):
        """Successful download returns success JSON with file info."""
        mock_resp = MagicMock()
        mock_resp.headers = {"content-type": "application/pdf"}
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_content.return_value = [b"chunk1", b"chunk2"]
        mock_get.return_value = mock_resp

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            result = await self.server.download(
                ctx=self.ctx,
                url="https://example.com/doc.pdf",
                file_path=tmp_path,
                overwrite=True,
            )

            self.assertIsInstance(result, TextContent)
            data = json.loads(result.text)
            self.assertTrue(data["success"])
            self.assertEqual(data["file_path"], tmp_path)
            self.assertEqual(data["size"], 12)  # b"chunk1" + b"chunk2"
            self.assertEqual(data["content_type"], "application/pdf")
            # Verify file was actually written
            with open(tmp_path, "rb") as f:
                self.assertEqual(f.read(), b"chunk1chunk2")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    @patch("advanced_fetch_mcp.server.requests.Session.get")
    async def test_download_network_error(self, mock_get):
        """Network error returns error JSON."""
        mock_get.side_effect = Exception("Connection timeout")

        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            result = await self.server.download(
                ctx=self.ctx,
                url="https://example.com/file.bin",
                file_path=tmp_path,
                overwrite=True,
            )

            self.assertIsInstance(result, TextContent)
            data = json.loads(result.text)
            self.assertFalse(data["success"])
            self.assertIn("Connection timeout", data["error"])
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    @patch("advanced_fetch_mcp.server.requests.Session.get")
    async def test_download_partial_file_cleanup(self, mock_get):
        """Failed download cleans up partial file."""
        mock_resp = MagicMock()
        mock_resp.headers = {"content-type": "application/octet-stream"}
        mock_resp.raise_for_status = MagicMock()
        # Simulate error mid-stream
        mock_resp.iter_content.side_effect = Exception("Disk full")
        mock_get.return_value = mock_resp

        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            result = await self.server.download(
                ctx=self.ctx,
                url="https://example.com/file.bin",
                file_path=tmp_path,
                overwrite=True,
            )

            data = json.loads(result.text)
            self.assertFalse(data["success"])
            self.assertIn("Disk full", data["error"])
            # Partial file should be cleaned up
            self.assertFalse(os.path.exists(tmp_path))
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    @patch("advanced_fetch_mcp.server.requests.Session.get")
    async def test_download_file_exists_no_overwrite(self, mock_get):
        """Without overwrite, existing file returns error without downloading."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(b"existing content")

        try:
            result = await self.server.download(
                ctx=self.ctx,
                url="https://example.com/file.txt",
                file_path=tmp_path,
                overwrite=False,
            )

            self.assertIsInstance(result, TextContent)
            data = json.loads(result.text)
            self.assertFalse(data["success"])
            self.assertIn("already exists", data["error"])
            # Verify no download happened
            mock_get.assert_not_called()
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    async def test_download_creates_parent_dir(self):
        """download creates parent directories automatically."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = os.path.join(tmpdir, "nested", "sub", "file.bin")

            # Mock to avoid actual network call
            with patch("advanced_fetch_mcp.server.requests.Session.get") as mock_get:
                mock_resp = MagicMock()
                mock_resp.headers = {"content-type": "application/octet-stream"}
                mock_resp.raise_for_status = MagicMock()
                mock_resp.iter_content.return_value = [b"data"]
                mock_get.return_value = mock_resp

                result = await self.server.download(
                    ctx=self.ctx,
                    url="https://example.com/file.bin",
                    file_path=nested_path,
                    overwrite=True,
                )

                data = json.loads(result.text)
                self.assertTrue(data["success"])
                self.assertTrue(os.path.exists(nested_path))

                # Cleanup
                os.unlink(nested_path)

    @patch("advanced_fetch_mcp.server.requests.Session.get")
    async def test_download_file_exists_with_overwrite(self, mock_get):
        """With overwrite=true, existing file is overwritten."""
        mock_resp = MagicMock()
        mock_resp.headers = {"content-type": "text/plain"}
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_content.return_value = [b"new content"]
        mock_get.return_value = mock_resp

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(b"old content")

        try:
            result = await self.server.download(
                ctx=self.ctx,
                url="https://example.com/file.txt",
                file_path=tmp_path,
                overwrite=True,
            )

            data = json.loads(result.text)
            self.assertTrue(data["success"])
            # Verify old content replaced
            with open(tmp_path, "rb") as f:
                self.assertEqual(f.read(), b"new content")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


class InferImageFormatTests(unittest.TestCase):
    def _import_server(self):
        import importlib, sys

        sys.modules.pop("advanced_fetch_mcp.server", None)
        return importlib.import_module("advanced_fetch_mcp.server")

    def setUp(self):
        self.server = self._import_server()

    def test_png(self):
        self.assertEqual(self.server._infer_image_format("image/png"), "png")

    def test_jpeg(self):
        self.assertEqual(self.server._infer_image_format("image/jpeg"), "jpeg")

    def test_jpg(self):
        """JPG subtypes like image/jpg should be detected."""
        self.assertEqual(self.server._infer_image_format("image/jpg"), "jpeg")

    def test_gif(self):
        self.assertEqual(self.server._infer_image_format("image/gif"), "gif")

    def test_webp(self):
        self.assertEqual(self.server._infer_image_format("image/webp"), "webp")

    def test_svg(self):
        self.assertEqual(
            self.server._infer_image_format("image/svg+xml"), "svg+xml"
        )

    def test_fallback(self):
        """Unknown content types fall back to 'png'."""
        self.assertEqual(self.server._infer_image_format("application/pdf"), "png")
        self.assertEqual(self.server._infer_image_format("text/html"), "png")


class ToolRegistrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_tools_registered(self):
        """read_image and download are registered as tools on the MCP server."""
        import importlib, sys

        sys.modules.pop("advanced_fetch_mcp.server", None)
        server = importlib.import_module("advanced_fetch_mcp.server")

        tools = await server.mcp.list_tools()
        names = [t.name for t in tools]
        self.assertIn("read_image", names)
        self.assertIn("download", names)
        self.assertIn("advanced_fetch", names)

    async def test_tool_signatures(self):
        """Tool function signatures have expected parameters."""
        import importlib, sys

        sys.modules.pop("advanced_fetch_mcp.server", None)
        server = importlib.import_module("advanced_fetch_mcp.server")

        tools = await server.mcp.list_tools()
        ri = next(t for t in tools if t.name == "read_image")
        dl = next(t for t in tools if t.name == "download")

        ri_param_names = set(ri.parameters.get("properties", {}).keys())
        self.assertIn("url", ri_param_names)
        self.assertIn("timeout", ri_param_names)
        self.assertEqual(len(ri_param_names), 2)

        dl_param_names = set(dl.parameters.get("properties", {}).keys())
        self.assertIn("url", dl_param_names)
        self.assertIn("file_path", dl_param_names)
        self.assertIn("timeout", dl_param_names)
        self.assertIn("overwrite", dl_param_names)


if __name__ == "__main__":
    unittest.main()
