import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from advanced_fetch_mcp.browser import BrowserManager, _copy_profile_template
from advanced_fetch_mcp.fetch import FetchResult, fetch_url


class FetchAndBrowserTests(unittest.IsolatedAsyncioTestCase):
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
