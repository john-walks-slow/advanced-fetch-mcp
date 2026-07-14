import unittest

from advanced_fetch_mcp.params import ViewConfig
from advanced_fetch_mcp.url_utils import (
    is_same_origin,
    is_skipped_href,
    make_relative_url,
    normalize_html_urls,
    normalize_markdown_urls,
)
from advanced_fetch_mcp.extract import render_view


class IsSameOriginTests(unittest.TestCase):
    def test_same_scheme_and_host(self):
        self.assertTrue(is_same_origin("https://example.com/page", "https://example.com"))

    def test_different_scheme(self):
        self.assertFalse(is_same_origin("http://example.com/page", "https://example.com"))

    def test_different_host(self):
        self.assertFalse(is_same_origin("https://other.com/page", "https://example.com"))

    def test_same_host_different_port(self):
        self.assertFalse(is_same_origin("https://example.com:8080/page", "https://example.com:443"))

    def test_subdomain_different(self):
        self.assertFalse(is_same_origin("https://blog.example.com/page", "https://example.com"))


class IsSkippedHrefTests(unittest.TestCase):
    def test_empty_skipped(self):
        self.assertTrue(is_skipped_href(""))

    def test_fragment_only_skipped(self):
        self.assertTrue(is_skipped_href("#section"))

    def test_javascript_skipped(self):
        self.assertTrue(is_skipped_href("javascript:void(0)"))

    def test_mailto_skipped(self):
        self.assertTrue(is_skipped_href("mailto:test@example.com"))

    def test_tel_skipped(self):
        self.assertTrue(is_skipped_href("tel:+123"))

    def test_data_skipped(self):
        self.assertTrue(is_skipped_href("data:text/plain,hello"))

    def test_http_not_skipped(self):
        self.assertFalse(is_skipped_href("https://example.com/page"))

    def test_relative_not_skipped(self):
        self.assertFalse(is_skipped_href("/relative/path"))


class MakeRelativeUrlTests(unittest.TestCase):
    def test_same_origin_to_relative(self):
        self.assertEqual(make_relative_url("https://example.com/page", "https://example.com"), "/page")

    def test_same_origin_with_query(self):
        self.assertEqual(make_relative_url("https://example.com/p?q=1", "https://example.com"), "/p?q=1")

    def test_same_origin_root(self):
        self.assertEqual(make_relative_url("https://example.com", "https://example.com"), "/")

    def test_cross_origin_stays_absolute(self):
        url = "https://other.com/page"
        self.assertEqual(make_relative_url(url, "https://example.com"), url)

    def test_different_scheme_stays_absolute(self):
        url = "http://example.com/page"
        self.assertEqual(make_relative_url(url, "https://example.com"), url)

    def test_empty_base_returns_original(self):
        url = "https://example.com/page"
        self.assertEqual(make_relative_url(url, ""), url)


class NormalizeHtmlUrlsTests(unittest.TestCase):
    def test_img_src_becomes_relative(self):
        html = '<img src="https://example.com/images/photo.png">'
        result = normalize_html_urls(html, "https://example.com")
        self.assertIn('src="/images/photo.png"', result)

    def test_a_href_becomes_relative(self):
        html = '<a href="https://example.com/page">Link</a>'
        result = normalize_html_urls(html, "https://example.com")
        self.assertIn('href="/page"', result)

    def test_cross_origin_stays_absolute(self):
        html = '<img src="https://other.com/img.png">'
        result = normalize_html_urls(html, "https://example.com")
        self.assertIn('src="https://other.com/img.png"', result)

    def test_srcset_normalized(self):
        html = '<img srcset="https://example.com/a.jpg 320w, https://example.com/b.jpg 640w">'
        result = normalize_html_urls(html, "https://example.com")
        self.assertIn('/a.jpg 320w', result)
        self.assertIn('/b.jpg 640w', result)
        self.assertNotIn("https://example.com", result)

    def test_srcset_cross_origin_unchanged(self):
        html = '<img srcset="https://other.com/img.jpg 320w">'
        result = normalize_html_urls(html, "https://example.com")
        self.assertIn('https://other.com/img.jpg', result)

    def test_video_src_normalized(self):
        html = '<video src="https://example.com/video.mp4"></video>'
        result = normalize_html_urls(html, "https://example.com")
        self.assertIn('src="/video.mp4"', result)

    def test_empty_html_returns_empty(self):
        self.assertEqual(normalize_html_urls("", "https://example.com"), "")

    def test_no_base_returns_original(self):
        html = '<img src="https://example.com/img.png">'
        self.assertEqual(normalize_html_urls(html, ""), html)

    def test_already_relative_not_touched(self):
        html = '<img src="/images/photo.png">'
        self.assertEqual(normalize_html_urls(html, "https://example.com"), html)

    def test_iframe_src_normalized(self):
        html = '<iframe src="https://example.com/embed"></iframe>'
        result = normalize_html_urls(html, "https://example.com")
        self.assertIn('src="/embed"', result)

    def test_mixed_origins(self):
        html = '<img src="https://example.com/a.png"><img src="https://other.com/b.png">'
        result = normalize_html_urls(html, "https://example.com")
        self.assertIn('src="/a.png"', result)
        self.assertIn('src="https://other.com/b.png"', result)


class NormalizeMarkdownUrlsTests(unittest.TestCase):
    def test_image_becomes_relative(self):
        text = "![alt](https://example.com/images/photo.png)"
        self.assertEqual(normalize_markdown_urls(text, "https://example.com"), "![alt](/images/photo.png)")

    def test_link_becomes_relative(self):
        text = "[text](https://example.com/page)"
        self.assertEqual(normalize_markdown_urls(text, "https://example.com"), "[text](/page)")

    def test_cross_origin_stays_absolute(self):
        text = "[text](https://other.com/page)"
        self.assertEqual(normalize_markdown_urls(text, "https://example.com"), text)

    def test_mixed_content(self):
        text = "A: ![img](https://example.com/a.png) B: ![img](https://other.com/b.png)"
        result = normalize_markdown_urls(text, "https://example.com")
        self.assertIn("![img](/a.png)", result)
        self.assertIn("![img](https://other.com/b.png)", result)

    def test_relative_urls_not_touched(self):
        text = "![img](/images/photo.png)"
        self.assertEqual(normalize_markdown_urls(text, "https://example.com"), text)

    def test_empty_text_returns_empty(self):
        self.assertEqual(normalize_markdown_urls("", "https://example.com"), "")

    def test_no_base_returns_original(self):
        text = "![img](https://example.com/img.png)"
        self.assertEqual(normalize_markdown_urls(text, ""), text)

    def test_text_without_urls_unchanged(self):
        text = "Just plain text"
        self.assertEqual(normalize_markdown_urls(text, "https://example.com"), text)

    def test_same_origin_with_query(self):
        text = "[link](https://example.com/page?q=hello&lang=en)"
        self.assertEqual(normalize_markdown_urls(text, "https://example.com"), "[link](/page?q=hello&lang=en)")


class RenderViewUrlNormalizationTests(unittest.TestCase):
    """Test that render_view applies URL normalization to rendered output."""

    def test_full_markdown_image_url_normalized(self):
        html = '<html><body><img src="https://example.com/images/photo.png" alt="Photo"></body></html>'
        view = ViewConfig(output_format="markdown", markdown_engine="full")
        result = render_view(html, view, base_url="https://example.com")
        # markdownify produces: ![Photo](/images/photo.png)
        self.assertIn("/images/photo.png", result)

    def test_full_markdown_link_url_normalized(self):
        html = '<html><body><a href="https://example.com/page">Link</a></body></html>'
        view = ViewConfig(output_format="markdown", markdown_engine="full")
        result = render_view(html, view, base_url="https://example.com")
        self.assertIn("](/page)", result)

    def test_article_markdown_url_normalized(self):
        # Trafilatura in article mode extracts link text as plain text, not markdown links.
        # The URL normalization post-processing is a no-op for trafilatura's markdown output,
        # but we verify it doesn't break content and no absolute URLs leak through.
        html = '<html><body><article><h1>Title</h1><p><a href="https://example.com/link">link</a></p></article></body></html>'
        view = ViewConfig(output_format="markdown", markdown_engine="article")
        result = render_view(html, view, base_url="https://example.com")
        self.assertIn("Title", result)
        self.assertIn("link", result)
        # The absolute URL should NOT appear in rendered content
        self.assertNotIn("https://example.com/link", result)

    def test_cross_origin_image_stays_absolute(self):
        html = '<html><body><img src="https://other.com/images/photo.png" alt="Photo"></body></html>'
        view = ViewConfig(output_format="markdown", markdown_engine="full")
        result = render_view(html, view, base_url="https://example.com")
        self.assertIn("https://other.com/images/photo.png", result)

    def test_no_base_url_no_normalization(self):
        html = '<html><body><img src="https://example.com/images/photo.png" alt="Photo"></body></html>'
        view = ViewConfig(output_format="markdown", markdown_engine="full")
        result = render_view(html, view, base_url=None)
        self.assertIn("https://example.com/images/photo.png", result)

    def test_full_html_url_normalized(self):
        html = '<html><body><img src="https://example.com/images/photo.png" alt="Photo"></body></html>'
        view = ViewConfig(output_format="html", markdown_engine="full")
        result = render_view(html, view, base_url="https://example.com")
        self.assertIn("photo.png", result)
        self.assertNotIn("https://example.com/images/photo.png", result)
