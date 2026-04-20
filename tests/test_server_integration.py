import importlib
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

from advanced_fetch_mcp.params import AdvancedFetchParams


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

    async def test_request_is_validated_from_current_nested_params(self):
        server = self._import_server()
        params = AdvancedFetchParams(
            url="https://example.com",
            operation="view",
            fetch={"mode": "static", "timeout": 1.5},
            render={
                "output_format": "html",
                "strategy": "loose",
                "include_elements": ["links"],
            },
            max_length=123,
        )
        with patch(
            "advanced_fetch_mcp.server.execute_advanced_fetch",
            new=AsyncMock(return_value={"success": True}),
        ) as exec_mock:
            result = await server.advanced_fetch(ctx=object(), **params.model_dump())

        self.assertEqual(result, {"success": True})
        passed_request = exec_mock.await_args.kwargs["request"]
        self.assertEqual(passed_request.url, "https://example.com")
        self.assertEqual(passed_request.fetch.mode, "static")
        self.assertEqual(passed_request.fetch.timeout, 1.5)
        self.assertEqual(passed_request.render.output_format, "html")
        self.assertEqual(passed_request.render.strategy, "loose")
        self.assertEqual(passed_request.render.include_elements, ["links"])
        self.assertEqual(passed_request.max_length, 123)

    async def test_eval_request_is_valid(self):
        server = self._import_server()
        params = AdvancedFetchParams(
            url="https://example.com",
            operation="eval",
            eval={"script": "return document.title;"},
        )
        with patch(
            "advanced_fetch_mcp.server.execute_advanced_fetch",
            new=AsyncMock(return_value={"success": True}),
        ) as exec_mock:
            result = await server.advanced_fetch(ctx=object(), **params.model_dump())

        self.assertEqual(result, {"success": True})
        passed_request = exec_mock.await_args.kwargs["request"]
        self.assertEqual(passed_request.operation, "eval")
        self.assertEqual(passed_request.eval.script, "return document.title;")
        self.assertIsNone(passed_request.sampling)
        self.assertIsNone(passed_request.find)
