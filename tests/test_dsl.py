import unittest
from unittest.mock import patch

from pydantic import ValidationError

from advanced_fetch_mcp.params import AdvancedFetchParams
from advanced_fetch_mcp.settings import DEFAULT_MAX_LENGTH


class DSLTests(unittest.TestCase):
    def test_defaults(self):
        request = AdvancedFetchParams(url="https://example.com")
        self.assertEqual(request.operation, "view")
        self.assertEqual(request.fetch.mode, "dynamic")
        self.assertEqual(request.fetch.wait_for, "auto")
        self.assertEqual(request.render.output_format, "markdown")
        self.assertIsNone(request.render.strategy)
        self.assertEqual(request.render.include_elements, ["tables", "formatting"])
        self.assertEqual(request.max_length, DEFAULT_MAX_LENGTH)

    def test_find_requires_find_object(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="find",
            find={"query": "x"},
        )
        self.assertEqual(request.operation, "find")
        self.assertEqual(request.find.query, "x")

        with self.assertRaises(ValidationError):
            AdvancedFetchParams(url="https://example.com", operation="find")

    def test_eval_is_exclusive(self):
        with self.assertRaises(ValidationError):
            AdvancedFetchParams(
                url="https://example.com",
                operation="eval",
                eval={"script": "return 1"},
                sampling={"prompt": "x"},
            )
        with self.assertRaises(ValidationError):
            AdvancedFetchParams(
                url="https://example.com",
                operation="eval",
                eval={"script": "return 1"},
                find={"query": "x"},
            )

    def test_eval_requires_dynamic(self):
        with self.assertRaises(ValidationError):
            AdvancedFetchParams(
                url="https://example.com",
                operation="eval",
                fetch={"mode": "static"},
                eval={"script": "return 1"},
            )

    def test_sampling_respects_feature_flag(self):
        with patch("advanced_fetch_mcp.params.ENABLE_PROMPT_EXTRACTION", False):
            with self.assertRaises(ValidationError):
                AdvancedFetchParams(
                    url="https://example.com",
                    operation="sampling",
                    sampling={"prompt": "提取"},
                )

    def test_render_config_is_derived(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            render={
                "output_format": "html",
                "strategy": "loose",
                "include_elements": ["links", "images"],
            },
        )
        view = request.to_render_config()
        self.assertEqual(view.output_format, "html")
        self.assertEqual(view.strategy, "loose")
        self.assertEqual(view.include_elements, ["links", "images"])

    def test_cursor_is_only_valid_for_view_and_find(self):
        with self.assertRaises(ValidationError):
            AdvancedFetchParams(
                url="https://example.com",
                operation="sampling",
                render={"cursor": 5},
                sampling={"prompt": "提取"},
            )

    def test_max_length_is_top_level_and_render_forbids_it(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            max_length=321,
        )
        self.assertEqual(request.max_length, 321)

        with self.assertRaises(ValidationError):
            AdvancedFetchParams(
                url="https://example.com",
                render={"max_length": 123},
            )
