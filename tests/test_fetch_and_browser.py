import unittest
from unittest.mock import AsyncMock, patch

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
            result = await fetch_url("https://example.com", "static", 0, True)
        mock_dynamic.assert_awaited_once()
        self.assertEqual(result.final_url, "u")

    async def test_require_user_intervention_uses_dynamic_flow(self):
        with patch(
            "advanced_fetch_mcp.fetch.dynamic_fetch",
            new=AsyncMock(return_value=FetchResult(html="x", final_url="u")),
        ) as mock_dynamic:
            result = await fetch_url("https://example.com", "dynamic", 0, True)
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
