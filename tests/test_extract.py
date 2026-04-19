import unittest

from advanced_fetch_mcp.extract import build_view_config, continue_in_text, render_view, search_in_text


class ExtractTests(unittest.TestCase):
    def test_render_markdown_strict_strategy(self):
        html = "<html><body><nav>Ignore</nav><main><h1>Hello</h1><p>World</p></main></body></html>"
        view = build_view_config({"markdownify": True, "strategy": "strict"})
        result = render_view(html, view)
        self.assertIn("Hello", result)
        self.assertIn("World", result)
        self.assertNotIn("Ignore", result)

    def test_render_html_none_strategy(self):
        html = "<html><head><script>1</script></head><body><nav>A</nav><main>B</main></body></html>"
        view = build_view_config({"markdownify": False, "strategy": "none"})
        result = render_view(html, view)
        self.assertIn("A", result)
        self.assertIn("B", result)
        self.assertNotIn("<script>", result)

    def test_search_returns_match_cursor(self):
        result = search_in_text("a refund b refund c", "refund", 12, False)
        self.assertEqual(result["matches_total"], 2)
        self.assertIn("cursor", result["matches"][0])

    def test_continue_reads_from_cursor(self):
        result = continue_in_text("0123456789abcdef", 8, 4)
        self.assertEqual(result["text"], "89ab")

    def test_none_strategy_keeps_navigation_text(self):
        html = "<html><body><nav>Nav</nav><main>Main</main></body></html>"
        view = build_view_config({"markdownify": True, "strategy": "none"})
        result = render_view(html, view)
        self.assertIn("Nav", result)
        self.assertIn("Main", result)

    def test_strict_strategy_trafilatura_excludes_navigation(self):
        """trafilatura 智能提取正文，剔除导航元素（包括外层和内层）。"""
        html = "<html><body><nav>Outer</nav><main><nav>Inner</nav><h1>Main</h1></main></body></html>"
        view = build_view_config({"markdownify": True, "strategy": "strict"})
        result = render_view(html, view)
        self.assertNotIn("Outer", result)  # 外层导航被剔除
        self.assertNotIn("Inner", result)  # 内层导航也被智能剔除
        self.assertIn("Main", result)      # 正文标题保留
