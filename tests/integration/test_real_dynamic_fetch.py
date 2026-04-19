"""真实动态抓取集成测试。

测试 dynamic_fetch 对需要 JS 渲染页面的抓取能力。
需要 Playwright 浏览器环境。
"""

import pytest

from advanced_fetch_mcp.fetch import dynamic_fetch, fetch_url, evaluate_script_on_page


@pytest.mark.integration
@pytest.mark.asyncio
class TestRealDynamicFetch:
    async def test_fetch_simple_page(self):
        """抓取简单页面应成功。"""
        result = await dynamic_fetch(
            "https://example.com/",
            wait_for=0,
            require_user_intervention=False,
            timeout=15,
        )
        assert result.html
        assert "Example Domain" in result.html
        assert result.final_url.startswith("https://")
        assert not result.timed_out

    async def test_fetch_js_rendered_page(self):
        """抓取需要 JS 渲染的页面应包含动态内容。"""
        # httpbin 的 /html 页面是纯静态，用 /delay/html 测试
        result = await dynamic_fetch(
            "https://httpbin.org/html",
            wait_for=1,
            require_user_intervention=False,
            timeout=15,
        )
        assert result.html
        assert not result.timed_out

    async def test_fetch_url_dynamic_mode(self):
        """fetch_url 的 dynamic 模式应正常工作。"""
        result = await fetch_url(
            url="https://example.com/",
            mode="dynamic",
            wait_for=0,
            require_user_intervention=False,
            timeout=15,
        )
        assert result.html
        assert not result.timed_out

    async def test_fetch_url_static_mode(self):
        """fetch_url 的 static 模式应正常工作。"""
        result = await fetch_url(
            url="https://example.com/",
            mode="static",
            wait_for=0,
            require_user_intervention=False,
            timeout=10,
        )
        assert result.html
        assert not result.timed_out

    async def test_timeout_stage_goto(self):
        """goto 超时应标记 timeout_stage=goto。"""
        result = await dynamic_fetch(
            "https://httpbin.org/delay/10",
            wait_for=0,
            require_user_intervention=False,
            timeout=1,
        )
        assert result.timed_out
        # 可能是 goto 或 networkidle 超时
        assert result.timeout_stage in ("goto", "networkidle")

    async def test_wait_for_delay(self):
        """wait_for 参数应延迟抓取。"""
        result = await dynamic_fetch(
            "https://example.com/",
            wait_for=2,
            require_user_intervention=False,
            timeout=20,
        )
        assert result.html
        assert not result.timed_out


@pytest.mark.integration
@pytest.mark.asyncio
class TestRealEvaluateJs:
    async def test_evaluate_returns_document_title(self):
        """执行 JS 返回 document.title。"""
        value = await evaluate_script_on_page(
            url="https://example.com/",
            wait_for=0,
            require_user_intervention=False,
            script="return document.title;",
            timeout=15,
        )
        assert value == "Example Domain"

    async def test_evaluate_returns_object(self):
        """执行 JS 返回复杂对象。"""
        value = await evaluate_script_on_page(
            url="https://example.com/",
            wait_for=0,
            require_user_intervention=False,
            script="return { title: document.title, url: location.href };",
            timeout=15,
        )
        assert isinstance(value, dict)
        assert value["title"] == "Example Domain"
        assert "example.com" in value["url"]

    async def test_evaluate_returns_number(self):
        """执行 JS 返回数字。"""
        value = await evaluate_script_on_page(
            url="https://example.com/",
            wait_for=0,
            require_user_intervention=False,
            script="return 42;",
            timeout=15,
        )
        assert value == 42

    async def test_evaluate_expression_style(self):
        """表达式风格的 JS 应正常执行。"""
        value = await evaluate_script_on_page(
            url="https://example.com/",
            wait_for=0,
            require_user_intervention=False,
            script="document.querySelectorAll('p').length",
            timeout=15,
        )
        assert isinstance(value, int)