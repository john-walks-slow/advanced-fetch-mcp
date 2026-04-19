import unittest

from advanced_fetch_mcp.extract import build_view_config, continue_in_text, render_view, search_in_text


class ExtractTests(unittest.TestCase):
    def test_render_markdown_content_view(self):
        html = "<html><body><nav>Ignore</nav><main><h1>Hello</h1><p>World</p></main></body></html>"
        view = build_view_config({"markdownify": True, "scope": "content"})
        result = render_view(html, view)
        self.assertIn("Hello", result)
        self.assertIn("World", result)
        self.assertNotIn("Ignore", result)

    def test_render_html_body_view(self):
        html = "<html><head><script>1</script></head><body><nav>A</nav><main>B</main></body></html>"
        view = build_view_config({"markdownify": False, "scope": "body"})
        result = render_view(html, view)
        self.assertIn("<body>", result)
        self.assertIn("A", result)
        self.assertNotIn("<script>", result)

    def test_search_returns_match_cursor(self):
        result = search_in_text("a refund b refund c", "refund", 12, False)
        self.assertEqual(result["matches_total"], 2)
        self.assertIn("cursor", result["matches"][0])

    def test_continue_reads_from_cursor(self):
        result = continue_in_text("0123456789abcdef", "8", 4)
        self.assertEqual(result["text"], "89ab")

    def test_body_scope_keeps_navigation_text(self):
        html = "<html><body><nav>Nav</nav><main>Main</main></body></html>"
        view = build_view_config({"markdownify": True, "scope": "body"})
        result = render_view(html, view)
        self.assertIn("Nav", result)
        self.assertIn("Main", result)

    def test_content_scope_prefers_main_over_outer_navigation(self):
        html = "<html><body><nav>Outer</nav><main><nav>Inner</nav><h1>Main</h1></main></body></html>"
        view = build_view_config({"markdownify": True, "scope": "content"})
        result = render_view(html, view)
        self.assertNotIn("Outer", result)
        self.assertIn("Inner", result)
        self.assertIn("Main", result)
