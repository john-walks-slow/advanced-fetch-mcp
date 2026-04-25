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


class _DummyModelPreferences:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class ServerIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def _import_server(self):
        previous_fastmcp = sys.modules.get("fastmcp")
        previous_fastmcp_utilities = sys.modules.get("fastmcp.utilities")
        previous_fastmcp_utilities_types = sys.modules.get("fastmcp.utilities.types")
        previous_markdownify = sys.modules.get("markdownify")
        previous_server = sys.modules.pop("advanced_fetch_mcp.server", None)
        fastmcp_stub = types.ModuleType("fastmcp")
        fastmcp_stub.Context = object
        fastmcp_stub.FastMCP = _DummyFastMCP
        fastmcp_utilities_stub = types.ModuleType("fastmcp.utilities")
        fastmcp_utilities_types_stub = types.ModuleType("fastmcp.utilities.types")
        fastmcp_utilities_types_stub.ModelPreferences = _DummyModelPreferences
        markdownify_stub = types.ModuleType("markdownify")
        markdownify_stub.markdownify = lambda html, **_: html
        sys.modules["fastmcp"] = fastmcp_stub
        sys.modules["fastmcp.utilities"] = fastmcp_utilities_stub
        sys.modules["fastmcp.utilities.types"] = fastmcp_utilities_types_stub
        sys.modules["markdownify"] = markdownify_stub
        self.addCleanup(
            self._restore_modules,
            previous_fastmcp,
            previous_fastmcp_utilities,
            previous_fastmcp_utilities_types,
            previous_markdownify,
            previous_server,
        )
        return importlib.import_module("advanced_fetch_mcp.server")

    def _restore_modules(
        self,
        previous_fastmcp,
        previous_fastmcp_utilities,
        previous_fastmcp_utilities_types,
        previous_markdownify,
        previous_server,
    ):
        sys.modules.pop("advanced_fetch_mcp.server", None)
        if previous_server is not None:
            sys.modules["advanced_fetch_mcp.server"] = previous_server
        if previous_fastmcp is None:
            sys.modules.pop("fastmcp", None)
        else:
            sys.modules["fastmcp"] = previous_fastmcp
        if previous_fastmcp_utilities is None:
            sys.modules.pop("fastmcp.utilities", None)
        else:
            sys.modules["fastmcp.utilities"] = previous_fastmcp_utilities
        if previous_fastmcp_utilities_types is None:
            sys.modules.pop("fastmcp.utilities.types", None)
        else:
            sys.modules["fastmcp.utilities.types"] = previous_fastmcp_utilities_types
        if previous_markdownify is None:
            sys.modules.pop("markdownify", None)
        else:
            sys.modules["markdownify"] = previous_markdownify

    async def test_request_is_validated_from_current_nested_params(self):
        server = self._import_server()
        params = AdvancedFetchParams(
            url="https://example.com",
            operation="view",
            fetch={"mode": "static", "timeout": 1.5},
            render={
                "engine": "markdownify",
                "output_format": "html",
                "strategy": "default",
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
        self.assertEqual(passed_request.render.engine, "markdownify")
        self.assertEqual(passed_request.render.output_format, "html")
        self.assertEqual(passed_request.render.strategy, "default")
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
