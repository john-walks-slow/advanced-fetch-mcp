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

    def test_public_signature_keeps_single_tool_without_action(self):
        server = self._import_real_server()
        signature = inspect.signature(server.advanced_fetch)
        params = list(signature.parameters.keys())
        self.assertNotIn("action", params)
        self.assertIn("output_format", params)
        self.assertIn("extract_prompt", params)
        self.assertIn("evaluate_js", params)
        self.assertNotIn("prompt", params)
        self.assertNotIn("evaluateJS", params)

