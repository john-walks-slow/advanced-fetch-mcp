import importlib
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch


class _DummyFastMCP:
    def __init__(self, name):
        self.name = name

    def tool(self):
        def decorator(fn):
            return fn
        return decorator


class ServerIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _import_server(self):
        fastmcp_stub = types.ModuleType("fastmcp")
        fastmcp_stub.Context = object
        fastmcp_stub.FastMCP = _DummyFastMCP
        sys.modules["fastmcp"] = fastmcp_stub
        return importlib.import_module("advanced_fetch_mcp.server")

    async def test_flat_arguments_are_forwarded_without_dsl_wrapper(self):
        server = self._import_server()
        with patch("advanced_fetch_mcp.server.execute_advanced_fetch", new=AsyncMock(return_value={"success": True})) as exec_mock:
            result = await server.advanced_fetch(
                url="https://example.com",
                ctx=object(),
                mode="dynamic",
                markdownify=False,
                scope="body",
                strip=[".ad"],
                keep_media=True,
                max_length=123,
                refresh_cache=True,
            )
        self.assertEqual(result, {"success": True})
        request = exec_mock.await_args.kwargs["request"]
        self.assertEqual(request.mode, "dynamic")
        self.assertFalse(request.markdownify)
        self.assertEqual(request.scope, "body")
        self.assertEqual(request.strip, [".ad"])
        self.assertTrue(request.keep_media)
        self.assertEqual(request.max_length, 123)
        self.assertTrue(request.refresh_cache)

    async def test_flat_arguments_normalize_none_strip_to_empty_list(self):
        server = self._import_server()
        with patch("advanced_fetch_mcp.server.execute_advanced_fetch", new=AsyncMock(return_value={"success": True})) as exec_mock:
            await server.advanced_fetch(
                url="https://example.com",
                ctx=object(),
                strip=None,
            )
        request = exec_mock.await_args.kwargs["request"]
        self.assertEqual(request.strip, [])
