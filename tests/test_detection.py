"""测试 detection.py 的用户介入检测逻辑。"""

import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from advanced_fetch_mcp.detection import (
    build_intervention_script,
    wait_for_intervention_end,
    INTERVENTION_BUTTON_ID,
)


class BuildInterventionScriptTests(unittest.TestCase):
    def test_script_contains_button_id(self):
        """脚本应包含正确的 button_id 配置。"""
        script = build_intervention_script()
        expected_payload = json.dumps({"button_id": INTERVENTION_BUTTON_ID}, ensure_ascii=False)
        self.assertIn(expected_payload, script)

    def test_script_contains_button_creation(self):
        """脚本应创建带有正确 ID 的按钮。"""
        script = build_intervention_script()
        self.assertIn(f"btn.id = cfg.button_id", script)
        self.assertIn(f"document.getElementById(cfg.button_id)", script)

    def test_script_sets_window_flag_on_click(self):
        """点击按钮应设置全局标记。"""
        script = build_intervention_script()
        self.assertIn("__ADVANCED_FETCH_INTERVENTION_DONE__", script)
        self.assertIn("window.__ADVANCED_FETCH_INTERVENTION_DONE__ = true", script)

    def test_script_has_fixed_position_styles(self):
        """按钮应有固定定位样式确保可见。"""
        script = build_intervention_script()
        self.assertIn("position = 'fixed'", script)
        self.assertIn("zIndex = '2147483647'", script)  # 最高层级

    def test_script_handles_dom_content_loaded(self):
        """脚本应处理 DOM 加载状态。"""
        script = build_intervention_script()
        self.assertIn("document.readyState === 'loading'", script)
        self.assertIn("DOMContentLoaded", script)


class WaitForInterventionEndTests(unittest.IsolatedAsyncioTestCase):
    async def test_user_marked_ready_returns_correct_reason(self):
        """用户点击完成按钮后应返回 user_marked_ready。"""
        page = MagicMock()
        page.is_closed.return_value = False
        page.content = AsyncMock(return_value="<html><body>Done</body></html>")
        page.url = "https://example.com/final"
        # wait_for_function 成功表示用户点击了完成按钮
        page.wait_for_function = AsyncMock()

        html, final_url, reason = await wait_for_intervention_end(page)

        self.assertEqual(reason, "user_marked_ready")
        self.assertIn("Done", html)
        self.assertEqual(final_url, "https://example.com/final")

    async def test_timeout_returns_timeout_reason(self):
        """超时应返回 timeout 原因。"""
        page = MagicMock()
        page.is_closed.return_value = False
        page.content = AsyncMock(return_value="<html><body>Partial</body></html>")
        page.url = "https://example.com/partial"

        # 模拟 wait_for_function 超时抛异常
        page.wait_for_function = AsyncMock(side_effect=Exception("Timeout"))

        html, final_url, reason = await wait_for_intervention_end(page)

        self.assertEqual(reason, "timeout")
        self.assertIn("Partial", html)

    async def test_page_closed_returns_page_closed_reason(self):
        """页面关闭后应返回 page_closed 原因。"""
        page = MagicMock()
        page.is_closed.return_value = True
        page.content = AsyncMock(return_value="")
        page.url = ""

        # 模拟 wait_for_function 抛异常且页面已关闭
        page.wait_for_function = AsyncMock(side_effect=Exception("Timeout"))

        html, final_url, reason = await wait_for_intervention_end(page)

        self.assertEqual(reason, "page_closed")

    async def test_returns_empty_content_on_page_failure(self):
        """获取页面内容失败时应返回空字符串。"""
        page = MagicMock()
        page.is_closed.return_value = False
        page.wait_for_function = AsyncMock(side_effect=Exception("Timeout"))
        page.content = AsyncMock(side_effect=Exception("Page gone"))
        page.url = ""

        html, final_url, reason = await wait_for_intervention_end(page)

        self.assertEqual(html, "")
        self.assertEqual(final_url, "")
        self.assertEqual(reason, "timeout")