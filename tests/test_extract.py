import unittest

from advanced_fetch_mcp.extract import (
    continue_in_text,
    extract_links,
    render_view,
    search_in_text,
)
from advanced_fetch_mcp.params import ViewConfig


class ExtractTests(unittest.TestCase):
    def test_render_article_markdown(self):
        html = "<html><body><nav>Ignore</nav><main><h1>Hello</h1><p>World</p></main></body></html>"
        view = ViewConfig(output_format="markdown", markdown_engine="article")
        result = render_view(html, view)
        self.assertIn("Hello", result)
        self.assertIn("World", result)

    def test_render_article_html(self):
        html = "<html><head><script>1</script></head><body><nav>A</nav><main>B</main></body></html>"
        view = ViewConfig(output_format="html", markdown_engine="article")
        result = render_view(html, view)
        self.assertIn("B", result)
        self.assertNotIn("<script>", result)

    def test_render_full_markdown(self):
        html = "<html><body><p><a href='https://example.com'>Link</a></p></body></html>"
        view = ViewConfig(output_format="markdown", markdown_engine="full")
        result = render_view(html, view)
        self.assertIn("[Link](https://example.com)", result)

    def test_render_full_html(self):
        html = "<html><head><title>Title</title></head><body><a href='https://example.com'>Link</a><img src='a.jpg'><main>Main</main></body></html>"
        view = ViewConfig(output_format="html", markdown_engine="full")
        result = render_view(html, view)
        self.assertIn("Main", result)
        self.assertIn("Link", result)
        self.assertNotIn("<title>", result)

    def test_render_full_strips_images_when_disabled(self):
        html = "<html><body><img src='photo.jpg' alt='Photo'><p>Text</p></body></html>"
        view = ViewConfig(output_format="markdown", markdown_engine="full", render_images=False)
        result = render_view(html, view)
        self.assertIn("Text", result)

    def test_render_article_strips_images_when_disabled(self):
        html = "<html><body><img src='photo.jpg' alt='Photo'><p>Text</p></body></html>"
        view = ViewConfig(output_format="markdown", markdown_engine="article", render_images=False)
        result = render_view(html, view)
        self.assertIn("Text", result)

    def test_search_returns_match_cursor(self):
        result = search_in_text("a refund b refund c", "refund", False)
        self.assertEqual(result["matches_total"], 2)
        self.assertIn("cursor", result["matches"][0])

    def test_continue_reads_from_cursor(self):
        result = continue_in_text("0123456789abcdef", 8, 4)
        self.assertEqual(result["text"], "89ab")

    def test_encode_cursor_returns_non_negative(self):
        from advanced_fetch_mcp.extract import encode_cursor

        self.assertEqual(encode_cursor(10), 10)
        self.assertEqual(encode_cursor(0), 0)
        self.assertEqual(encode_cursor(-5), 0)

    def test_search_with_regex_pattern(self):
        result = search_in_text("abc123def456", "\\d+", True)
        self.assertEqual(result["matches_total"], 2)
        self.assertTrue(result["found"])

    def test_search_with_invalid_regex_falls_back_to_literal(self):
        result = search_in_text("test [ value", "[", True)
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
        view = ViewConfig(output_format="markdown", markdown_engine="article")
        result = render_view(html, view)
        self.assertTrue(len(result) > 0)


class ExtractLinksTests(unittest.TestCase):
    def test_extracts_all_links(self):
        html = '<html><body><a href="https://example.com/page1">Link1</a><a href="https://example.com/page2">Link2</a></body></html>'
        result = extract_links(html, "https://example.com", "", limit=10)
        self.assertEqual(len(result["links"]), 2)
        self.assertEqual(result["links_total"], 2)
        self.assertFalse(result["links_truncated"])

    def test_filters_javascript_protocol(self):
        html = '<html><body><a href="javascript:void(0)">JS</a><a href="https://example.com">Normal</a></body></html>'
        result = extract_links(html, "https://example.com", "", limit=10)
        self.assertEqual(len(result["links"]), 1)
        self.assertEqual(result["links"][0]["abs_url"], "https://example.com")

    def test_filters_mailto_and_tel(self):
        html = '<html><body><a href="mailto:test@example.com">Email</a><a href="tel:+123">Phone</a></body></html>'
        result = extract_links(html, "https://example.com", "", limit=10)
        self.assertEqual(len(result["links"]), 0)

    def test_filters_fragment_only(self):
        html = '<html><body><a href="#">Top</a><a href="#section">Section</a><a href="/page">Real</a></body></html>'
        result = extract_links(html, "https://example.com", "", limit=10)
        self.assertEqual(len(result["links"]), 1)
        self.assertEqual(result["links"][0]["href"], "/page")

    def test_resolves_relative_urls(self):
        html = '<html><body><a href="/relative/path">Rel</a></body></html>'
        result = extract_links(html, "https://example.com/base/", "", limit=10)
        self.assertEqual(result["links"][0]["abs_url"], "https://example.com/relative/path")

    def test_resolves_relative_urls_with_base(self):
        html = '<html><body><a href="other/page">Rel</a></body></html>'
        result = extract_links(html, "https://example.com/base/", "", limit=10)
        self.assertEqual(result["links"][0]["abs_url"], "https://example.com/base/other/page")

    def test_deduplicates_by_abs_url(self):
        html = '<html><body><a href="/page">First</a><a href="https://example.com/page">Second</a></body></html>'
        result = extract_links(html, "https://example.com", "", limit=10)
        self.assertEqual(len(result["links"]), 1)
        self.assertEqual(result["links"][0]["text"], "First")

    def test_skips_links_in_rendered_text(self):
        html = '<html><body><a href="https://example.com/visible">Visible</a><a href="https://example.com/hidden">Hidden</a></body></html>'
        rendered = "some text https://example.com/visible appears here"
        result = extract_links(html, "https://example.com", rendered, limit=10)
        self.assertEqual(len(result["links"]), 1)
        self.assertEqual(result["links"][0]["abs_url"], "https://example.com/hidden")

    def test_same_origin_becomes_relative(self):
        html = '<html><body><a href="https://example.com/page">Link</a></body></html>'
        result = extract_links(html, "https://example.com", "", limit=10)
        self.assertEqual(result["links"][0]["href"], "/page")
        self.assertEqual(result["links"][0]["abs_url"], "https://example.com/page")

    def test_cross_origin_stays_absolute(self):
        html = '<html><body><a href="https://other.com/page">Link</a></body></html>'
        result = extract_links(html, "https://example.com", "", limit=10)
        self.assertEqual(result["links"][0]["href"], "https://other.com/page")
        self.assertEqual(result["links"][0]["abs_url"], "https://other.com/page")

    def test_limit_truncation(self):
        html = '<html><body>'
        for i in range(5):
            html += f'<a href="https://example.com/page{i}">Link{i}</a>'
        html += '</body></html>'
        result = extract_links(html, "https://example.com", "", limit=3)
        self.assertEqual(len(result["links"]), 3)
        self.assertEqual(result["links_total"], 5)
        self.assertTrue(result["links_truncated"])

    def test_empty_html_returns_empty(self):
        result = extract_links("", "https://example.com", "", limit=10)
        self.assertEqual(result["links"], [])
        self.assertEqual(result["links_total"], 0)
        self.assertFalse(result["links_truncated"])

    def test_no_links_returns_empty(self):
        result = extract_links("<html><body><p>No links here</p></body></html>", "https://example.com", "", limit=10)
        self.assertEqual(result["links"], [])
        self.assertEqual(result["links_total"], 0)

    def test_link_text_from_img_alt(self):
        html = '<html><body><a href="https://example.com"><img src="photo.jpg" alt="Photo of something"></a></body></html>'
        result = extract_links(html, "https://example.com", "", limit=10)
        self.assertEqual(result["links"][0]["text"], "Photo of something")

    def test_link_text_empty_for_no_content(self):
        html = '<html><body><a href="https://example.com"></a></body></html>'
        result = extract_links(html, "https://example.com", "", limit=10)
        self.assertEqual(result["links"][0]["text"], "")
