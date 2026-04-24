import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from advanced_fetch_mcp.browser import BrowserManager
from advanced_fetch_mcp.fetch import (
    FetchResult,
    _FETCH_CACHE,
    _build_page_evaluate_script,
    fetch_url,
    get_cached_fetch,
    store_cached_fetch,
)


class FetchAndBrowserTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self):
        _FETCH_CACHE.clear()

    async def test_fetch_url_forces_dynamic_when_intervention_requested(self):
        with patch(
            "advanced_fetch_mcp.fetch.dynamic_fetch",
            new=AsyncMock(return_value=FetchResult(html="x", final_url="u")),
        ) as mock_dynamic:
            result = await fetch_url("https://example.com", "static", True)
        mock_dynamic.assert_awaited_once()
        self.assertEqual(result.final_url, "u")

    async def test_require_user_intervention_uses_dynamic_flow(self):
        with patch(
            "advanced_fetch_mcp.fetch.dynamic_fetch",
            new=AsyncMock(return_value=FetchResult(html="x", final_url="u")),
        ) as mock_dynamic:
            result = await fetch_url("https://example.com", "dynamic", True)
        mock_dynamic.assert_awaited_once()
        self.assertEqual(result.final_url, "u")

    async def test_open_session_rejects_invalid_session_mode(self):
        manager = BrowserManager()
        with patch("advanced_fetch_mcp.browser.BROWSER_SESSION_MODE", "invalid"):
            with self.assertRaises(RuntimeError):
                async with manager.open_session(headless=True):
                    pass

    def test_cache_is_partitioned_by_url_and_mode(self):
        store_cached_fetch(
            "https://example.com", "static", "https://static", "<main>static</main>"
        )
        self.assertEqual(
            get_cached_fetch("https://example.com", "static"),
            ("https://static", "<main>static</main>"),
        )
        self.assertIsNone(get_cached_fetch("https://example.com", "dynamic"))
        self.assertIsNone(get_cached_fetch("https://other.com", "static"))

    def test_evaluate_script_wraps_function_body_style_snippets(self):
        wrapped = _build_page_evaluate_script("return { title: document.title };")
        self.assertIn("() => {", wrapped)
        self.assertIn("return { title: document.title };", wrapped)

    def test_evaluate_script_keeps_function_style_snippets(self):
        script = "() => document.title"
        self.assertEqual(_build_page_evaluate_script(script), script)

    def test_evaluate_script_wraps_multiline_code(self):
        wrapped = _build_page_evaluate_script("const x = 1;\nreturn x;")
        self.assertIn("() => {", wrapped)
        self.assertIn("const x = 1;", wrapped)
        self.assertIn("return x;", wrapped)

    def test_evaluate_script_wraps_expression_without_return(self):
        wrapped = _build_page_evaluate_script("document.title")
        self.assertIn("() => (", wrapped)
        self.assertIn("document.title", wrapped)

    def test_evaluate_script_preserves_async_function(self):
        script = "async function() { return await fetch('/api'); }"
        self.assertEqual(_build_page_evaluate_script(script), script)

    def test_evaluate_script_preserves_arrow_function_with_params(self):
        script = "(el) => el.textContent"
        self.assertEqual(_build_page_evaluate_script(script), script)

    def test_static_fetch_returns_empty_on_timeout(self):
        from advanced_fetch_mcp.fetch import static_fetch

        result = static_fetch("https://httpbin.org/delay/5", timeout=0.1)
        self.assertTrue(result.timed_out)
        self.assertEqual(result.timeout_stage, "static_request")
        self.assertEqual(result.html, "")

    def test_static_fetch_returns_empty_on_connection_error(self):
        from advanced_fetch_mcp.fetch import static_fetch

        result = static_fetch("https://invalid.nonexistent.tld/page", timeout=0.5)
        self.assertFalse(result.timed_out)
        self.assertIsNone(result.timeout_stage)
        self.assertEqual(result.html, "")

    def test_proxy_settings_reads_http_proxy(self):
        import os
        from advanced_fetch_mcp.browser import _proxy_settings

        original = os.environ.get("HTTP_PROXY")
        os.environ["HTTP_PROXY"] = "http://proxy.example.com:8080"
        settings = _proxy_settings()
        if original:
            os.environ["HTTP_PROXY"] = original
        else:
            os.environ.pop("HTTP_PROXY", None)

        self.assertIsNotNone(settings)
        self.assertEqual(settings["server"], "http://proxy.example.com:8080")

    def test_proxy_settings_reads_https_proxy(self):
        import os
        from advanced_fetch_mcp.browser import _proxy_settings

        original_http = os.environ.get("HTTP_PROXY")
        original_https = os.environ.get("HTTPS_PROXY")
        os.environ["HTTP_PROXY"] = "http://proxy1.example.com:8080"
        os.environ["HTTPS_PROXY"] = "http://proxy2.example.com:8080"

        settings = _proxy_settings()

        if original_http:
            os.environ["HTTP_PROXY"] = original_http
        else:
            os.environ.pop("HTTP_PROXY", None)
        if original_https:
            os.environ["HTTPS_PROXY"] = original_https
        else:
            os.environ.pop("HTTPS_PROXY", None)

        self.assertEqual(settings["server"], "http://proxy2.example.com:8080")

    def test_proxy_settings_returns_none_without_env(self):
        import os
        from advanced_fetch_mcp.browser import _proxy_settings

        saved = {}
        for key in [
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "http_proxy",
            "https_proxy",
            "NO_PROXY",
            "no_proxy",
        ]:
            saved[key] = os.environ.get(key)
            os.environ.pop(key, None)

        settings = _proxy_settings()

        for key, value in saved.items():
            if value:
                os.environ[key] = value

        self.assertIsNone(settings)

    async def test_browser_manager_close_clears_shared_state(self):
        manager = BrowserManager()
        context = AsyncMock()
        playwright = AsyncMock()
        manager._shared_profile_contexts = {("chrome", "profile"): context}
        manager._shared_playwright = playwright

        await manager.close()

        context.close.assert_awaited_once()
        playwright.stop.assert_awaited_once()
        self.assertEqual(manager._shared_profile_contexts, {})
        self.assertIsNone(manager._shared_playwright)


class ShouldBypassProxyTests(unittest.TestCase):
    def test_bypass_matches_exact_host(self):
        from advanced_fetch_mcp.settings import should_bypass_proxy

        with patch("advanced_fetch_mcp.settings.get_no_proxy", return_value="localhost"):
            self.assertTrue(should_bypass_proxy("http://localhost/page"))

    def test_bypass_matches_domain_suffix(self):
        from advanced_fetch_mcp.settings import should_bypass_proxy

        with patch("advanced_fetch_mcp.settings.get_no_proxy", return_value=".example.com"):
            self.assertTrue(should_bypass_proxy("http://sub.example.com/page"))
            self.assertTrue(should_bypass_proxy("http://example.com/page"))

    def test_bypass_wildcard_matches_all(self):
        from advanced_fetch_mcp.settings import should_bypass_proxy

        with patch("advanced_fetch_mcp.settings.get_no_proxy", return_value="*"):
            self.assertTrue(should_bypass_proxy("http://any.host/page"))

    def test_no_bypass_when_not_in_no_proxy(self):
        from advanced_fetch_mcp.settings import should_bypass_proxy

        with patch("advanced_fetch_mcp.settings.get_no_proxy", return_value="localhost"):
            self.assertFalse(should_bypass_proxy("http://external.com/page"))

    def test_no_bypass_when_no_proxy_empty(self):
        from advanced_fetch_mcp.settings import should_bypass_proxy

        with patch("advanced_fetch_mcp.settings.get_no_proxy", return_value=None):
            self.assertFalse(should_bypass_proxy("http://localhost/page"))


class TruncateTextMiddleTests(unittest.TestCase):
    def test_no_truncation_when_short(self):
        from advanced_fetch_mcp.workflow import _truncate_text_middle

        result, truncated = _truncate_text_middle("short", 10)
        self.assertEqual(result, "short")
        self.assertFalse(truncated)

    def test_truncates_middle_when_long(self):
        from advanced_fetch_mcp.workflow import _truncate_text_middle

        text = "0123456789abcdefghij"
        result, truncated = _truncate_text_middle(text, 10)
        self.assertTrue(truncated)
        self.assertIn("<", result)
        self.assertTrue(len(result) <= 10)

    def test_returns_marker_when_max_length_equals_marker(self):
        from advanced_fetch_mcp.workflow import _truncate_text_middle

        text = "verylongtext"
        result, truncated = _truncate_text_middle(text, 3)
        self.assertTrue(truncated)
        self.assertEqual(len(result), 3)

    def test_handles_empty_text(self):
        from advanced_fetch_mcp.workflow import _truncate_text_middle

        result, truncated = _truncate_text_middle("", 10)
        self.assertEqual(result, "")
        self.assertFalse(truncated)


class EvaluateScriptOnPageTests(unittest.IsolatedAsyncioTestCase):
    async def test_handles_goto_timeout_gracefully(self):
        from advanced_fetch_mcp.fetch import evaluate_script_on_page
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError

        mock_page = MagicMock()
        mock_page.goto = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value="result")
        mock_page.is_closed = MagicMock(return_value=False)
        mock_page.close = AsyncMock()
        mock_page.content = AsyncMock(return_value="<html><body>test</body></html>")
        mock_page.url = "https://example.com"

        mock_context = MagicMock()
        mock_context.add_init_script = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_context
        mock_session_cm.__aexit__.return_value = None

        mock_manager = MagicMock()
        mock_manager.open_session = MagicMock(return_value=mock_session_cm)

        with patch("advanced_fetch_mcp.fetch.browser_manager", mock_manager):
            with patch("advanced_fetch_mcp.fetch._wait_for_content_stable", AsyncMock()):
                result = await evaluate_script_on_page(
                    url="https://example.com",
                    require_user_intervention=False,
                    script="document.title",
                    timeout=1.0,
                )

        self.assertEqual(result.value, "result")
        self.assertEqual(result.fetch_result.final_url, "https://example.com")
        self.assertTrue(result.fetch_result.timed_out)
        self.assertEqual(result.fetch_result.timeout_stage, "goto")

    async def test_eval_intervention_page_closed_raises_clear_error(self):
        from advanced_fetch_mcp.fetch import (
            EvalInterventionClosedError,
            evaluate_script_on_page,
        )

        mock_page = MagicMock()
        mock_page.goto = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value="result")
        mock_page.is_closed = MagicMock(return_value=True)
        mock_page.close = AsyncMock()

        mock_context = MagicMock()
        mock_context.add_init_script = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_context
        mock_session_cm.__aexit__.return_value = None

        mock_manager = MagicMock()
        mock_manager.open_session = MagicMock(return_value=mock_session_cm)

        with patch("advanced_fetch_mcp.fetch.browser_manager", mock_manager):
            with patch("advanced_fetch_mcp.fetch._wait_for_content_stable", AsyncMock()):
                with patch(
                    "advanced_fetch_mcp.fetch.wait_for_intervention_end",
                    new=AsyncMock(return_value=("", "", "page_closed")),
                ):
                    with self.assertRaises(EvalInterventionClosedError):
                        await evaluate_script_on_page(
                            url="https://example.com",
                            require_user_intervention=True,
                            script="document.title",
                            timeout=1.0,
                        )

        mock_page.evaluate.assert_not_awaited()
