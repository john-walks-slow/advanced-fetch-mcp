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

    def test_render_html_none_strategy(self):
        html = "<html><head><script>1</script></head><body><nav>A</nav><main>B</main></body></html>"
        view = RenderConfig(output_format="html", strategy="none")
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
        view = RenderConfig(output_format="markdown", strategy="none")
        result = render_view(html, view)
        self.assertIn("Nav", result)
        self.assertIn("Main", result)

    def test_strict_strategy_trafilatura_excludes_navigation(self):
        """trafilatura 智能提取正文，剔除导航元素（包括外层和内层）。"""
        html = "<html><body><nav>Outer</nav><main><nav>Inner</nav><h1>Main</h1></main></body></html>"
        view = RenderConfig(output_format="markdown", strategy="strict")
        result = render_view(html, view)
        self.assertNotIn("Outer", result)  # 外层导航被剔除
        self.assertNotIn("Inner", result)  # 内层导航也被智能剔除
        self.assertIn("Main", result)  # 正文标题保留

    def test_strip_selectors_removes_elements(self):
        html = "<html><body><div class='ad'>Advertisement</div><p>Content</p></body></html>"
        view = RenderConfig(
            output_format="markdown", strategy="none", strip_selectors=[".ad"]
        )
        result = render_view(html, view)
        self.assertNotIn("Advertisement", result)
        self.assertIn("Content", result)

    def test_empty_strip_selectors_keeps_media(self):
        html = "<html><body><img src='test.jpg'><p>Text</p></body></html>"
        view = RenderConfig(output_format="html", strategy="none", strip_selectors=[])
        result = render_view(html, view)
        self.assertIn("<img", result)
        self.assertIn("Text", result)

    def test_loose_strategy_is_more_inclusive(self):
        """loose 策略应更宽松地提取内容，可能保留更多元素。"""
        html = "<html><body><aside>Sidebar</aside><article><h1>Title</h1><p>Content</p></article></body></html>"
        view = RenderConfig(output_format="markdown", strategy="loose")
        result = render_view(html, view)
        self.assertIn("Title", result)
        self.assertIn("Content", result)

    def test_apply_strip_selectors_removes_multiple_elements(self):
        """apply_strip_selectors 应剔除多个匹配元素。"""
        from advanced_fetch_mcp.extract import apply_strip_selectors
        from bs4 import BeautifulSoup

        html = "<div><span class='ad'>Ad1</span><span class='ad'>Ad2</span><p>Content</p></div>"
        soup = BeautifulSoup(html, "html.parser")
        root = soup.div
        result = apply_strip_selectors(root, [".ad"])
        self.assertNotIn("Ad1", str(result))
        self.assertNotIn("Ad2", str(result))
        self.assertIn("Content", str(result))

    def test_apply_strip_selectors_handles_invalid_selector(self):
        """无效 selector 应不抛异常，继续处理其他 selector。"""
        from advanced_fetch_mcp.extract import apply_strip_selectors
        from bs4 import BeautifulSoup

        html = "<div><p class='valid'>Keep</p><span>Span</span></div>"
        soup = BeautifulSoup(html, "html.parser")
        root = soup.div
        # 无效 selector 不应阻止有效 selector
        result = apply_strip_selectors(root, ["::invalid", ".valid"])
        self.assertIn("Span", str(result))
        self.assertNotIn("Keep", str(result))

    def test_encode_cursor_returns_non_negative(self):
        """encode_cursor 应返回非负值。"""
        from advanced_fetch_mcp.extract import encode_cursor

        self.assertEqual(encode_cursor(10), 10)
        self.assertEqual(encode_cursor(0), 0)
        self.assertEqual(encode_cursor(-5), 0)  # 负数转为 0

    def test_search_with_regex_pattern(self):
        """search_in_text 支持正则搜索。"""
        result = search_in_text("abc123def456", "\\d+", 20, True)
        self.assertEqual(result["matches_total"], 2)
        self.assertTrue(result["found"])

    def test_search_with_invalid_regex_falls_back_to_literal(self):
        """无效正则应回退到字面搜索。"""
        # 无效正则 [ 会被 escape
        result = search_in_text("test [ value", "[", 20, True)
        self.assertTrue(result["found"])
        self.assertIn("[", result["matches"][0]["snippet"])

    def test_continue_at_end_returns_empty(self):
        """cursor 超出文本末尾应返回空。"""
        result = continue_in_text("short text", 100, 10)
        self.assertEqual(result["text"], "")
        self.assertIsNone(result["next_cursor"])

    def test_prepare_body_removes_script_and_style(self):
        """prepare_body 应移除 script/style 等噪音标签。"""
        from advanced_fetch_mcp.extract import prepare_body
        from bs4 import BeautifulSoup

        html = "<html><body><script>alert('x')</script><style>.x{}</style><p>Text</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        view = RenderConfig(output_format="markdown", strategy="none")
        root = prepare_body(soup, view)
        result_str = str(root)
        self.assertNotIn("script", result_str.lower())
        self.assertNotIn("style", result_str.lower())
        self.assertNotIn("alert", result_str)
        self.assertIn("Text", result_str)

    def test_trafilatura_fallback_on_empty_extraction(self):
        """trafilatura 提取失败时应 fallback 到 body 处理。"""
        # 极简 HTML，trafilatura 可能返回 None
        html = "<html><body>Plain text only</body></html>"
        view = RenderConfig(output_format="markdown", strategy="strict")
        result = render_view(html, view)
        self.assertTrue(len(result) > 0)

    def test_img_in_strip_selectors_excludes_images_from_trafilatura(self):
        """strip_selectors 包含 'img' 时，trafilatura 不应保留图片。"""
        html = "<html><body><img src='photo.jpg'><p>Text</p></body></html>"
        view = RenderConfig(output_format="markdown", strategy="strict", strip_selectors=["img"])
        result = render_view(html, view)
        # 图片相关内容不应出现
        self.assertNotIn("photo.jpg", result)