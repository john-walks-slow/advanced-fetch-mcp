import unittest
from unittest.mock import patch

from pydantic import ValidationError

from advanced_fetch_mcp.params import AdvancedFetchParams
from advanced_fetch_mcp.settings import (
    AUTO_WAIT_MIN_CONTENT_LENGTH,
    AUTO_WAIT_MIN_STABLE_SECONDS,
    DEFAULT_MAX_LENGTH,
    FETCH_TIMEOUT_SECONDS,
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
        self.assertEqual(request.view.output_format, "markdown")
        self.assertEqual(request.view.markdown_engine, "article")
        self.assertFalse(request.view.render_images)
        self.assertEqual(request.max_length, DEFAULT_MAX_LENGTH)
        self.assertIsNone(request.view.cursor)

    def test_find_requires_find_object(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="find",
            find={"query": "x"},
        )
        self.assertEqual(request.operation, "find")
        self.assertEqual(request.find.query, "x")
        self.assertEqual(request.find.limit, MAX_FIND_MATCHES)
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
                "start_index": 2,
            },
        )
        self.assertEqual(request.find.limit, 3)
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

    def test_view_config_is_derived(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            view={
                "output_format": "html",
                "markdown_engine": "full",
                "render_images": True,
            },
        )
        cfg = request.to_view_config()
        self.assertEqual(cfg.output_format, "html")
        self.assertEqual(cfg.markdown_engine, "full")

    def test_view_allows_explicit_article_engine(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            view={"markdown_engine": "article"},
        )
        self.assertEqual(request.view.markdown_engine, "article")

    def test_view_allows_explicit_full_engine(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            view={"markdown_engine": "full"},
        )
        self.assertEqual(request.view.markdown_engine, "full")

    def test_cursor_is_only_valid_for_view(self):
        with self.assertRaises(ValidationError):
            AdvancedFetchParams(
                url="https://example.com",
                operation="sampling",
                view={"cursor": 5},
                sampling={"prompt": "提取"},
            )

        with self.assertRaises(ValidationError):
            AdvancedFetchParams(
                url="https://example.com",
                operation="find",
                view={"cursor": 5},
                find={"query": "x"},
            )

    def test_max_length_is_top_level(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            max_length=321,
        )
        self.assertEqual(request.max_length, 321)

    def test_view_forbids_old_params(self):
        with self.assertRaises(ValidationError):
            AdvancedFetchParams(
                url="https://example.com",
                view={"engine": "trafilatura"},
            )

        with self.assertRaises(ValidationError):
            AdvancedFetchParams(
                url="https://example.com",
                view={"strategy": "strict"},
            )

        with self.assertRaises(ValidationError):
            AdvancedFetchParams(
                url="https://example.com",
                view={"include_elements": ["tables"]},
            )
