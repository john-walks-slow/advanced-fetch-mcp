import unittest
from unittest.mock import patch

from pydantic import ValidationError

from advanced_fetch_mcp.dsl import AdvancedFetchParams, FindInPageOptions


class DSLTests(unittest.TestCase):
    def test_defaults(self):
        request = AdvancedFetchParams()
        self.assertEqual(request.mode, "dynamic")
        self.assertEqual(request.scope, "content")
        self.assertEqual(request.strip, [])
        self.assertFalse(request.keep_media)

    def test_find_requires_query_or_cursor(self):
        with self.assertRaises(ValidationError):
            FindInPageOptions()

    def test_find_query_and_cursor_are_mutually_exclusive(self):
        with self.assertRaises(ValidationError):
            FindInPageOptions(query="x", cursor="1f")

    def test_find_cursor_does_not_need_regex(self):
        with self.assertRaises(ValidationError):
            FindInPageOptions(cursor="1f", regex=True)

    def test_evaluate_js_is_exclusive(self):
        with self.assertRaises(ValidationError):
            AdvancedFetchParams(evaluateJS="return 1", prompt="x")

    def test_evaluate_js_requires_dynamic(self):
        with self.assertRaises(ValidationError):
            AdvancedFetchParams(mode="static", evaluateJS="return 1")

    def test_prompt_and_find_are_mutually_exclusive(self):
        with self.assertRaises(ValidationError):
            AdvancedFetchParams(prompt="x", find_in_page=FindInPageOptions(query="y"))

    def test_prompt_respects_feature_flag(self):
        with patch("advanced_fetch_mcp.dsl.ENABLE_PROMPT_EXTRACTION", False):
            with self.assertRaises(ValidationError):
                AdvancedFetchParams(prompt="提取")
