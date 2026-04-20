import importlib
import inspect
import sys
import unittest


class ServerSchemaTests(unittest.TestCase):
    def _import_real_server(self):
        sys.modules.pop("advanced_fetch_mcp.server", None)
        fastmcp_module = sys.modules.get("fastmcp")
        if fastmcp_module is not None and getattr(fastmcp_module, "FastMCP", None).__name__ == "_DummyFastMCP":
            sys.modules.pop("fastmcp", None)
        return importlib.import_module("advanced_fetch_mcp.server")

    def test_real_fastmcp_server_imports(self):
        server = self._import_real_server()
        self.assertTrue(hasattr(server, "mcp"))

    def test_public_signature_matches_current_request_model(self):
        server = self._import_real_server()
        signature = inspect.signature(server.advanced_fetch)
        params = list(signature.parameters.keys())
        self.assertEqual(
            params,
            ["url", "operation", "fetch", "render", "max_length", "find", "sampling", "eval", "ctx"],
        )
        self.assertNotIn("action", params)
        self.assertNotIn("output_format", params)
        self.assertNotIn("extract_prompt", params)
        self.assertNotIn("evaluate_js", params)
