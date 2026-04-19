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
        previous_fastmcp = sys.modules.get("fastmcp")
        previous_server = sys.modules.pop("advanced_fetch_mcp.server", None)
        fastmcp_stub = types.ModuleType("fastmcp")
        fastmcp_stub.Context = object
        fastmcp_stub.FastMCP = _DummyFastMCP
        sys.modules["fastmcp"] = fastmcp_stub
        self.addCleanup(self._restore_modules, previous_fastmcp, previous_server)
        return importlib.import_module("advanced_fetch_mcp.server")

    def _restore_modules(self, previous_fastmcp, previous_server):
        sys.modules.pop("advanced_fetch_mcp.server", None)
        if previous_server is not None:
            sys.modules["advanced_fetch_mcp.server"] = previous_server
        if previous_fastmcp is None:
            sys.modules.pop("fastmcp", None)
        else:
            sys.modules["fastmcp"] = previous_fastmcp

    async def test_request_is_passed_directly(self):
        server = self._import_server()
        with patch("advanced_fetch_mcp.server.execute_advanced_fetch", new=AsyncMock(return_value={"success": True})) as exec_mock:
            result = await server.advanced_fetch(
                ctx=object(),
                url="https://example.com",
                mode="dynamic",
                output_format="html",
                strategy="none",
                strip_selectors=[".ad"],
                max_length=123,
                refresh_cache=True,
            )
        self.assertEqual(result, {"success": True})
        passed_request = exec_mock.await_args.kwargs["request"]
        self.assertEqual(passed_request.url, "https://example.com")
        self.assertEqual(passed_request.mode, "dynamic")
        self.assertEqual(passed_request.output_format, "html")
        self.assertEqual(passed_request.strategy, "none")
        self.assertEqual(passed_request.strip_selectors, [".ad"])
        self.assertEqual(passed_request.max_length, 123)
        self.assertTrue(passed_request.refresh_cache)

    async def test_evaluate_js_request_is_valid(self):
        server = self._import_server()
        with patch("advanced_fetch_mcp.server.execute_advanced_fetch", new=AsyncMock(return_value={"success": True})) as exec_mock:
            result = await server.advanced_fetch(
                ctx=object(),
                url="https://example.com",
                evaluate_js="return document.title;",
            )
        self.assertEqual(result, {"success": True})
        passed_request = exec_mock.await_args.kwargs["request"]
        self.assertEqual(passed_request.evaluate_js, "return document.title;")
        self.assertIsNone(passed_request.extract_prompt)
        self.assertIsNone(passed_request.find_in_page)