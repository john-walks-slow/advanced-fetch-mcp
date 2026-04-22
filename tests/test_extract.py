import unittest

from advanced_fetch_mcp.extract import continue_in_text, render_view, search_in_text
from advanced_fetch_mcp.params import RenderConfig


class ExtractTests(unittest.TestCase):
    def test_render_markdown_strict_strategy(self):
        html = "<html><body><nav>Ignore</nav><main><h1>Hello</h1><p>World</p></main></body></html>"
        view = RenderConfig(output_format="markdown", strategy="strict")
        result = render_view(html, view)
        self.assertIn("Hello", result)
        self.assertIn("World", result)
        self.assertNotIn("Ignore", result)

    def test_render_html_balanced_strategy(self):
        html = "<html><head><script>1</script></head><body><nav>A</nav><main>B</main></body></html>"
        view = RenderConfig(output_format="html", strategy=None)
        result = render_view(html, view)
        self.assertIn("B", result)
        self.assertNotIn("<script>", result)

    def test_search_returns_match_cursor(self):
        result = search_in_text("a refund b refund c", "refund", False, 0)
        self.assertEqual(result["matches_total"], 2)
        self.assertIn("cursor", result["matches"][0])

    def test_continue_reads_from_cursor(self):
        result = continue_in_text("0123456789abcdef", 8, 4)
        self.assertEqual(result["text"], "89ab")

    def test_balanced_strategy_keeps_navigation_text(self):
        html = "<html><body><nav>Nav</nav><main>Main</main></body></html>"
        view = RenderConfig(output_format="markdown", strategy=None)
        result = render_view(html, view)
        self.assertIn("Nav", result)
        self.assertIn("Main", result)

    def test_strict_strategy_trafilatura_excludes_navigation(self):
        html = "<html><body><nav>Outer</nav><main><nav>Inner</nav><h1>Main</h1></main></body></html>"
        view = RenderConfig(output_format="markdown", strategy="strict")
        result = render_view(html, view)
        self.assertNotIn("Outer", result)
        self.assertNotIn("Inner", result)
        self.assertIn("Main", result)

    def test_html_output_can_include_images(self):
        html = "<html><body><img src='test.jpg'><p>Text</p></body></html>"
        view = RenderConfig(output_format="html", strategy=None, include_elements=["images"])
        result = render_view(html, view)
        self.assertIn("Text", result)

    def test_loose_strategy_is_more_inclusive(self):
        html = "<html><body><aside>Sidebar</aside><article><h1>Title</h1><p>Content</p></article></body></html>"
        view = RenderConfig(output_format="markdown", strategy="loose")
        result = render_view(html, view)
        self.assertIn("Title", result)
        self.assertIn("Content", result)

    def test_encode_cursor_returns_non_negative(self):
        from advanced_fetch_mcp.extract import encode_cursor

        self.assertEqual(encode_cursor(10), 10)
        self.assertEqual(encode_cursor(0), 0)
        self.assertEqual(encode_cursor(-5), 0)

    def test_search_with_regex_pattern(self):
        result = search_in_text("abc123def456", "\\d+", True, 0)
        self.assertEqual(result["matches_total"], 2)
        self.assertTrue(result["found"])

    def test_search_with_invalid_regex_falls_back_to_literal(self):
        result = search_in_text("test [ value", "[", True, 0)
        self.assertTrue(result["found"])
        self.assertIn("[", result["matches"][0]["snippet"])

    def test_continue_at_end_returns_empty(self):
        result = continue_in_text("short text", 100, 10)
        self.assertEqual(result["text"], "")
        self.assertIsNone(result["next_cursor"])

    def test_continue_returns_only_text_and_cursor(self):
        result = continue_in_text("0123456789abcdef", 0, 5)
        self.assertEqual(set(result.keys()), {"text", "next_cursor"})
        self.assertEqual(result["text"], "01234")
        self.assertEqual(result["next_cursor"], 5)

    def test_continue_at_exact_end_returns_no_cursor(self):
        result = continue_in_text("01234", 0, 5)
        self.assertEqual(result["text"], "01234")
        self.assertIsNone(result["next_cursor"])

    def test_trafilatura_fallback_on_empty_extraction(self):
        html = "<html><body>Plain text only</body></html>"
        view = RenderConfig(output_format="markdown", strategy="strict")
        result = render_view(html, view)
        self.assertTrue(len(result) > 0)

    def test_markdown_with_images_enabled_still_returns_text(self):
        html = "<html><body><img src='photo.jpg'><p>Text</p></body></html>"
        view = RenderConfig(output_format="markdown", strategy="strict", include_elements=["images", "formatting"])
        result = render_view(html, view)
        self.assertIn("Text", result)
