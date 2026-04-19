"""真实静态抓取集成测试。

测试 static_fetch 对真实网页的抓取能力。
"""

import pytest

from advanced_fetch_mcp.fetch import static_fetch


@pytest.mark.integration
class TestRealStaticFetch:
    def test_fetch_example_com(self):
        """抓取 example.com 应成功返回 HTML。"""
        result = static_fetch("https://example.com/", timeout=10)
        assert result.html
        assert "Example Domain" in result.html
        assert result.final_url.startswith("https://")
        assert not result.timed_out

    def test_fetch_httpbin_html(self):
        """抓取 httpbin HTML 页面应成功。"""
        result = static_fetch("https://httpbin.org/html", timeout=15)
        assert result.html
        assert "Marn特效" in result.html or "httpbin" in result.html.lower()
        assert not result.timed_out

    def test_fetch_handles_redirect(self):
        """重定向应返回最终 URL。"""
        result = static_fetch("https://httpbin.org/redirect/2", timeout=15)
        assert result.final_url != "https://httpbin.org/redirect/2"
        assert "redirect" in result.final_url or result.final_url.endswith("/get")

    def test_timeout_returns_empty_with_flag(self):
        """超时应返回空 HTML 并标记 timed_out。"""
        # 使用极短超时测试超时行为
        result = static_fetch("https://httpbin.org/delay/5", timeout=0.1)
        assert result.timed_out
        assert result.timeout_stage == "static_request"
        assert result.html == ""

    def test_http_error_raises_for_status(self):
        """HTTP 错误状态码应抛异常（被 requests 处理）。"""
        # 404 页面
        result = static_fetch("https://httpbin.org/status/404", timeout=10)
        # static_fetch 捕获 requests 异常返回空结果
        assert result.html == "" or result.timed_out

    def test_final_url_matches_response_url(self):
        """final_url 应反映重定向后的实际 URL。"""
        result = static_fetch("https://httpbin.org/redirect-to?url=https://example.com", timeout=15)
        assert "example.com" in result.final_url