import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from advanced_fetch_mcp.browser import BrowserManager, _copy_profile_template
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
        with patch("advanced_fetch_mcp.fetch.dynamic_fetch", new=AsyncMock(return_value=FetchResult(html="x", final_url="u"))) as mock_dynamic:
            result = await fetch_url("https://example.com", "static", 0, True)
        mock_dynamic.assert_awaited_once()
        self.assertEqual(result.final_url, "u")

    async def test_require_user_intervention_uses_dynamic_flow(self):
        with patch("advanced_fetch_mcp.fetch.dynamic_fetch", new=AsyncMock(return_value=FetchResult(html="x", final_url="u"))) as mock_dynamic:
            result = await fetch_url("https://example.com", "dynamic", 0, True)
        mock_dynamic.assert_awaited_once()
        self.assertEqual(result.final_url, "u")

    async def test_persistent_context_rejects_invalid_channel(self):
        manager = BrowserManager()
        with patch("advanced_fetch_mcp.browser.BROWSER_CHANNEL", "firefox"):
            with self.assertRaises(RuntimeError):
                await manager.get_context(headless=True)

    def test_copy_profile_template_copies_selected_profile_data_only(self):
        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dst_dir:
            src = Path(src_dir)
            dst = Path(dst_dir)
            (src / "Cookies").write_text("cookies", encoding="utf-8")
            (src / "Preferences").write_text("prefs", encoding="utf-8")
            (src / "History").write_text("history", encoding="utf-8")
            (src / "SingletonLock").write_text("lock", encoding="utf-8")
            _copy_profile_template(src, dst)
            self.assertTrue((dst / "Cookies").exists())
            self.assertTrue((dst / "Preferences").exists())
            self.assertFalse((dst / "History").exists())
            self.assertFalse((dst / "SingletonLock").exists())

    def test_copy_profile_template_does_not_overwrite_existing_files(self):
        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dst_dir:
            src = Path(src_dir)
            dst = Path(dst_dir)
            (src / "Cookies").write_text("from-src", encoding="utf-8")
            (dst / "Cookies").write_text("from-dst", encoding="utf-8")
            _copy_profile_template(src, dst)
            self.assertEqual((dst / "Cookies").read_text(encoding="utf-8"), "from-dst")

    def test_copy_profile_template_fills_missing_nested_profile_entries(self):
        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dst_dir:
            src = Path(src_dir)
            dst = Path(dst_dir)
            (src / "Local Storage").mkdir()
            (src / "Local Storage" / "leveldb").mkdir()
            (src / "Local Storage" / "leveldb" / "000003.log").write_text("data", encoding="utf-8")
            (dst / "Local Storage").mkdir()
            _copy_profile_template(src, dst)
            self.assertTrue((dst / "Local Storage" / "leveldb" / "000003.log").exists())

    def test_cache_is_partitioned_by_url_and_mode(self):
        store_cached_fetch("https://example.com", "static", "https://static", "<main>static</main>")
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
        """多行代码应使用 {} 包裹。"""
        wrapped = _build_page_evaluate_script("const x = 1;\nreturn x;")
        self.assertIn("() => {", wrapped)
        self.assertIn("const x = 1;", wrapped)
        self.assertIn("return x;", wrapped)

    def test_evaluate_script_wraps_expression_without_return(self):
        """不含 return 的单行表达式应使用 () 包裹。"""
        wrapped = _build_page_evaluate_script("document.title")
        self.assertIn("() => (", wrapped)
        self.assertIn("document.title", wrapped)

    def test_evaluate_script_preserves_async_function(self):
        """async function 应保持原样。"""
        script = "async function() { return await fetch('/api'); }"
        self.assertEqual(_build_page_evaluate_script(script), script)

    def test_evaluate_script_preserves_arrow_function_with_params(self):
        """带参数的箭头函数应保持原样。"""
        script = "(el) => el.textContent"
        self.assertEqual(_build_page_evaluate_script(script), script)

    def test_static_fetch_returns_empty_on_timeout(self):
        """static_fetch 超时应返回空 HTML 并标记 timed_out。"""
        from advanced_fetch_mcp.fetch import static_fetch

        # 使用极短超时
        result = static_fetch("https://httpbin.org/delay/5", timeout=0.1)
        self.assertTrue(result.timed_out)
        self.assertEqual(result.timeout_stage, "static_request")
        self.assertEqual(result.html, "")

    def test_proxy_settings_reads_http_proxy(self):
        """_proxy_settings 应读取 HTTP_PROXY 环境变量。"""
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
        """_proxy_settings 应优先读取 HTTPS_PROXY。"""
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

        # HTTPS_PROXY 应优先
        self.assertEqual(settings["server"], "http://proxy2.example.com:8080")

    def test_proxy_settings_returns_none_without_env(self):
        """没有代理环境变量时应返回 None。"""
        import os
        from advanced_fetch_mcp.browser import _proxy_settings

        # 保存并清除所有代理环境变量
        saved = {}
        for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "NO_PROXY", "no_proxy"]:
            saved[key] = os.environ.get(key)
            os.environ.pop(key, None)

        settings = _proxy_settings()

        # 恢复
        for key, value in saved.items():
            if value:
                os.environ[key] = value

        self.assertIsNone(settings)

    async def test_browser_manager_close_clears_state(self):
        """BrowserManager.close() 应清除持久状态。"""
        manager = BrowserManager()
        manager._persistent_context = AsyncMock()
        manager._persistent_playwright = AsyncMock()
        manager._persistent_headless = True

        await manager.close()

        self.assertIsNone(manager._persistent_context)
        self.assertIsNone(manager._persistent_playwright)
        self.assertIsNone(manager._persistent_headless)
