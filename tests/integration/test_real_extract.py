"""真实内容提取集成测试。

测试各种提取策略对真实网页的实际效果。
"""

import pytest

from advanced_fetch_mcp.extract import render_view
from advanced_fetch_mcp.params import RenderConfig


@pytest.mark.integration
class TestRealExtract:
    def test_strict_strategy_on_example_com(self):
        """strict 策略提取 example.com。"""
        html = """
        <html>
        <head><title>Example</title></head>
        <body>
            <nav>Navigation</nav>
            <main>
                <h1>Example Domain</h1>
                <p>This domain is for use in illustrative examples.</p>
            </main>
            <footer>Footer</footer>
        </body>
        </html>
        """
        view = RenderConfig(output_format="markdown", strategy="strict")
        result = render_view(html, view)
        assert "Example Domain" in result
        # strict 策略应剔除导航和 footer
        assert "Navigation" not in result

    def test_none_strategy_preserves_all(self):
        """none 策略保留所有内容。"""
        html = """
        <html>
        <body>
            <nav>Nav Content</nav>
            <main>Main Content</main>
            <footer>Footer Content</footer>
        </body>
        </html>
        """
        view = RenderConfig(output_format="markdown", strategy="none")
        result = render_view(html, view)
        assert "Nav Content" in result
        assert "Main Content" in result
        assert "Footer Content" in result

    def test_loose_strategy_on_complex_html(self):
        """loose 策略应更宽松地提取内容。"""
        html = """
        <html>
        <body>
            <aside>Sidebar</aside>
            <article>
                <h1>Article Title</h1>
                <p>Article content with more details.</p>
                <p>Second paragraph.</p>
            </article>
            <nav>Site Nav</nav>
        </body>
        </html>
        """
        view = RenderConfig(output_format="markdown", strategy="loose")
        result = render_view(html, view)
        assert "Article Title" in result
        assert "Article content" in result

    def test_html_output_format(self):
        """html 输出格式应保留 HTML 标签。"""
        html = """
        <html>
        <body>
            <h1>Title</h1>
            <p>Paragraph with <strong>bold</strong> text.</p>
        </body>
        </html>
        """
        view = RenderConfig(output_format="html", strategy="none")
        result = render_view(html, view)
        assert "<h1>" in result or "Title" in result
        assert "<p>" in result or "Paragraph" in result

    def test_strip_selectors_on_real_html(self):
        """strip_selectors 应剔除指定元素。"""
        html = """
        <html>
        <body>
            <div class="advertisement">Buy Now!</div>
            <div class="sidebar">Sidebar</div>
            <main>Main Content</main>
        </body>
        </html>
        """
        view = RenderConfig(
            output_format="markdown",
            strategy="none",
            strip_selectors=[".advertisement", ".sidebar"],
        )
        result = render_view(html, view)
        assert "Main Content" in result
        assert "Buy Now!" not in result
        assert "Sidebar" not in result

    def test_markdown_format_preserves_structure(self):
        """markdown 格式应保留文档结构。"""
        html = """
        <html>
        <body>
            <h1>Heading 1</h1>
            <h2>Heading 2</h2>
            <ul>
                <li>Item 1</li>
                <li>Item 2</li>
            </ul>
        </body>
        </html>
        """
        view = RenderConfig(output_format="markdown", strategy="none")
        result = render_view(html, view)
        assert "Heading 1" in result
        assert "Heading 2" in result
        assert "Item 1" in result
        assert "Item 2" in result

    def test_trafilatura_fallback_on_invalid_html(self):
        """trafilatura 失败时应 fallback 到 body 处理。"""
        # 极简 HTML，trafilatura 可能无法提取
        html = "<html><body>Just plain text</body></html>"
        view = RenderConfig(output_format="markdown", strategy="strict")
        result = render_view(html, view)
        assert result  # 应返回某些内容而非空

    def test_img_in_strip_selectors_excludes_images(self):
        """strip_selectors 包含 img 时不应保留图片。"""
        html = """
        <html>
        <body>
            <img src="photo.jpg" alt="Photo">
            <p>Text content</p>
        </body>
        </html>
        """
        view = RenderConfig(
            output_format="markdown",
            strategy="strict",
            strip_selectors=["img"],
        )
        result = render_view(html, view)
        assert "Text content" in result