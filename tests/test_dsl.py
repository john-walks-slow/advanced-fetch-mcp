import unittest
from unittest.mock import patch

from pydantic import ValidationError

from advanced_fetch_mcp.dsl import AdvancedFetchParams


class DSLTests(unittest.TestCase):
    def test_defaults(self):
        request = AdvancedFetchParams(url="https://example.com")
        self.assertEqual(request.mode, "dynamic")
        self.assertEqual(request.scope, "content")
        self.assertEqual(request.strip, [])
        self.assertFalse(request.keep_media)

    def test_find_in_page_optional(self):
        AdvancedFetchParams(url="https://example.com")  # 无 find_in_page，正常
        AdvancedFetchParams(url="https://example.com", find_in_page="x")  # 有 find_in_page，正常

    def test_find_with_regex_needs_query(self):
        with self.assertRaises(ValidationError):
            AdvancedFetchParams(url="https://example.com", find_with_regex=True)  # 有 regex 无 query，失败

    def test_evaluate_js_is_exclusive(self):
        with self.assertRaises(ValidationError):
            AdvancedFetchParams(url="https://example.com", evaluateJS="return 1", prompt="x")
        with self.assertRaises(ValidationError):
            AdvancedFetchParams(url="https://example.com", evaluateJS="return 1", find_in_page="x")

    def test_evaluate_js_requires_dynamic(self):
        with self.assertRaises(ValidationError):
            AdvancedFetchParams(url="https://example.com", mode="static", evaluateJS="return 1")

    def test_prompt_and_find_in_page_are_mutually_exclusive(self):
        with self.assertRaises(ValidationError):
            AdvancedFetchParams(url="https://example.com", prompt="x", find_in_page="y")

    def test_prompt_respects_feature_flag(self):
        with patch("advanced_fetch_mcp.dsl.ENABLE_PROMPT_EXTRACTION", False):
            with self.assertRaises(ValidationError):
                AdvancedFetchParams(url="https://example.com", prompt="提取")