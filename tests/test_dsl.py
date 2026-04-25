import unittest
from unittest.mock import patch

from pydantic import ValidationError

from advanced_fetch_mcp.params import AdvancedFetchParams
from advanced_fetch_mcp.settings import (
    AUTO_WAIT_MIN_CONTENT_LENGTH,
    AUTO_WAIT_MIN_STABLE_SECONDS,
    DEFAULT_MAX_LENGTH,
    FETCH_TIMEOUT_SECONDS,
    FIND_SNIPPET_MAX_CHARS,
    MAX_FIND_MATCHES,
)


class DSLTests(unittest.TestCase):
    def test_defaults(self):
        request = AdvancedFetchParams(url="https://example.com")
        self.assertEqual(request.operation, "view")
        self.assertEqual(request.fetch.mode, "static")
        self.assertEqual(request.fetch.timeout, FETCH_TIMEOUT_SECONDS)
        self.assertEqual(request.fetch.min_stable_seconds, AUTO_WAIT_MIN_STABLE_SECONDS)
        self.assertEqual(request.fetch.min_content_length, AUTO_WAIT_MIN_CONTENT_LENGTH)
        self.assertEqual(request.render.engine, "trafilatura")
        self.assertEqual(request.render.output_format, "markdown")
        self.assertEqual(request.render.strategy, "default")
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
        self.assertEqual(request.find.limit, MAX_FIND_MATCHES)
        self.assertEqual(request.find.snippet_max_chars, FIND_SNIPPET_MAX_CHARS)
        self.assertEqual(request.find.start_index, 0)

        with self.assertRaises(ValidationError):
            AdvancedFetchParams(url="https://example.com", operation="find")

    def test_find_accepts_extended_paging_params(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="find",
            find={
                "query": "x",
                "limit": 3,
                "snippet_max_chars": 40,
                "start_index": 2,
            },
        )
        self.assertEqual(request.find.limit, 3)
        self.assertEqual(request.find.snippet_max_chars, 40)
        self.assertEqual(request.find.start_index, 2)

    def test_find_extended_paging_params_validate_ranges(self):
        with self.assertRaises(ValidationError):
            AdvancedFetchParams(
                url="https://example.com",
                operation="find",
                find={"query": "x", "limit": 0},
            )
        with self.assertRaises(ValidationError):
            AdvancedFetchParams(
                url="https://example.com",
                operation="find",
                find={"query": "x", "snippet_max_chars": 0},
            )
        with self.assertRaises(ValidationError):
            AdvancedFetchParams(
                url="https://example.com",
                operation="find",
                find={"query": "x", "start_index": -1},
            )

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
                "engine": "markdownify",
                "output_format": "html",
                "strategy": "default",
                "include_elements": ["links", "images"],
            },
        )
        view = request.to_render_config()
        self.assertEqual(view.output_format, "html")
        self.assertEqual(view.strategy, "default")
        self.assertEqual(view.include_elements, ["links", "images"])

    def test_render_strategy_accepts_explicit_default(self):
        default_request = AdvancedFetchParams(
            url="https://example.com",
            render={"strategy": "default"},
        )

        self.assertEqual(default_request.render.strategy, "default")

    def test_markdownify_engine_rejects_non_default_strategy(self):
        with self.assertRaises(ValidationError):
            AdvancedFetchParams(
                url="https://example.com",
                render={"engine": "markdownify", "strategy": "loose"},
            )

    def test_cursor_is_only_valid_for_view(self):
        with self.assertRaises(ValidationError):
            AdvancedFetchParams(
                url="https://example.com",
                operation="sampling",
                render={"cursor": 5},
                sampling={"prompt": "提取"},
            )

        with self.assertRaises(ValidationError):
            AdvancedFetchParams(
                url="https://example.com",
                operation="find",
                render={"cursor": 5},
                find={"query": "x"},
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

    def test_can_use_cache_true_for_find_operation(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="find",
            find={"query": "x"},
        )
        self.assertTrue(request.can_use_cache)

    def test_can_use_cache_true_for_cursor_continuation(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            render={"cursor": 100},
        )
        self.assertTrue(request.can_use_cache)

    def test_can_use_cache_false_for_view_without_cursor(self):
        request = AdvancedFetchParams(url="https://example.com")
        self.assertFalse(request.can_use_cache)

    def test_can_use_cache_false_for_sampling_operation(self):
        with patch("advanced_fetch_mcp.params.ENABLE_PROMPT_EXTRACTION", True):
            request = AdvancedFetchParams(
                url="https://example.com",
                operation="sampling",
                sampling={"prompt": "x"},
            )
        self.assertFalse(request.can_use_cache)
