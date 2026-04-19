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

    async def test_request_is_passed_directly(self):
        server = self._import_server()
        with patch("advanced_fetch_mcp.server.execute_advanced_fetch", new=AsyncMock(return_value={"success": True})) as exec_mock:
            result = await server.advanced_fetch(
                ctx=object(),
                url="https://example.com",
                mode="dynamic",
                markdownify=False,
                scope="body",
                strip=[".ad"],
                keep_media=True,
                max_length=123,
                refresh_cache=True,
            )
        self.assertEqual(result, {"success": True})
        passed_request = exec_mock.await_args.kwargs["request"]
        self.assertEqual(passed_request.url, "https://example.com")
        self.assertEqual(passed_request.mode, "dynamic")
        self.assertFalse(passed_request.markdownify)
        self.assertEqual(passed_request.scope, "body")
        self.assertEqual(passed_request.strip, [".ad"])
        self.assertTrue(passed_request.keep_media)
        self.assertEqual(passed_request.max_length, 123)
        self.assertTrue(passed_request.refresh_cache)

    async def test_evaluate_js_request_is_valid(self):
        server = self._import_server()
        with patch("advanced_fetch_mcp.server.execute_advanced_fetch", new=AsyncMock(return_value={"success": True})) as exec_mock:
            result = await server.advanced_fetch(
                ctx=object(),
                url="https://example.com",
                evaluateJS="return document.title;",
            )
        self.assertEqual(result, {"success": True})
        passed_request = exec_mock.await_args.kwargs["request"]
        self.assertEqual(passed_request.evaluateJS, "return document.title;")
        self.assertIsNone(passed_request.prompt)
        self.assertIsNone(passed_request.find_in_page)