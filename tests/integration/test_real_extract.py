"""真实内容提取集成测试。"""

import pytest

from advanced_fetch_mcp.extract import render_view
from advanced_fetch_mcp.params import RenderConfig


@pytest.mark.integration
class TestRealExtract:
    def test_strict_strategy_on_example_com(self):
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
        assert "Navigation" not in result

    def test_balanced_strategy_keeps_main_content(self):
        html = """
        <html>
        <body>
            <nav>Nav Content</nav>
            <main>Main Content</main>
            <footer>Footer Content</footer>
        </body>
        </html>
        """
        view = RenderConfig(output_format="markdown", strategy=None)
        result = render_view(html, view)
        assert "Nav Content" in result
        assert "Main Content" in result

    def test_loose_strategy_on_complex_html(self):
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
        html = """
        <html>
        <body>
            <h1>Title</h1>
            <p>Paragraph with <strong>bold</strong> text.</p>
        </body>
        </html>
        """
        view = RenderConfig(output_format="html", strategy=None)
        result = render_view(html, view)
        assert "Title" in result
        assert "Paragraph" in result

    def test_markdown_format_preserves_structure(self):
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
        view = RenderConfig(output_format="markdown", strategy=None)
        result = render_view(html, view)
        assert "Heading 1" in result
        assert "Heading 2" in result
        assert "Item 1" in result
        assert "Item 2" in result

    def test_trafilatura_fallback_on_invalid_html(self):
        html = "<html><body>Just plain text</body></html>"
        view = RenderConfig(output_format="markdown", strategy="strict")
        result = render_view(html, view)
        assert result

    def test_images_can_be_included(self):
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
            include_elements=["images", "formatting"],
        )
        result = render_view(html, view)
        assert "Text content" in result
