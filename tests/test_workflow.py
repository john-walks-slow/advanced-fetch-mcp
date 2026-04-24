import unittest
from unittest.mock import AsyncMock, patch

from advanced_fetch_mcp.fetch import FetchResult
from advanced_fetch_mcp.params import AdvancedFetchParams
from advanced_fetch_mcp.settings import MAX_FIND_MATCHES
from advanced_fetch_mcp.workflow import FIND_MATCHES_WARNING, execute_advanced_fetch


class WorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_result_is_markdown_view(self):
        request = AdvancedFetchParams(url="https://example.com")
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html="<main>Hello<img src='x'/></main>",
                        final_url="https://example.com/final",
                    )
                ),
            ),
            patch("advanced_fetch_mcp.workflow.render_view", return_value="Hello"),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertIn("Hello", result["result"])
        self.assertNotIn("img", result["result"])

    async def test_sampling_result_becomes_primary_result(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="sampling",
            sampling={"prompt": "提取标题"},
        )
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html="<main>Hello</main>", final_url="https://example.com/final"
                    )
                ),
            ),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
            patch(
                "advanced_fetch_mcp.workflow.run_prompt_extraction",
                new=AsyncMock(return_value={"value": "标题：Hello"}),
            ),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertEqual(result["result"], "标题：Hello")

    async def test_find_returns_minimal_match_summaries(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="find",
            find={"query": "refund"},
            max_length=18,
        )
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html="<main>prefix refund suffix more refund tail</main>",
                        final_url="https://example.com/final",
                    )
                ),
            ),
            patch("advanced_fetch_mcp.workflow.render_view", return_value="prefix refund suffix more refund tail"),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertTrue(result["found"])
        self.assertEqual(set(result["matches"][0].keys()), {"snippet", "cursor"})
        self.assertEqual(result["matches_total"], 2)

    async def test_cursor_continues_from_render_cursor(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            render={"cursor": 8},
            max_length=8,
        )
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html="<main>0123456789abcdef</main>",
                        final_url="https://example.com/final",
                    )
                ),
            ),
            patch("advanced_fetch_mcp.workflow.render_view", return_value="0123456789abcdef"),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertEqual(result["result"], "89abcdef")
        self.assertNotIn("matches", result)

    async def test_find_then_cursor_jump_to_match(self):
        initial = AdvancedFetchParams(
            url="https://example.com",
            operation="find",
            find={"query": "refund"},
            max_length=12,
        )
        html = "<main>a refund b c refund d e refund f</main>"
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html=html, final_url="https://example.com/final"
                    )
                ),
            ),
            patch("advanced_fetch_mcp.workflow.render_view", return_value="a refund b c refund d e refund f"),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
        ):
            first = await execute_advanced_fetch(ctx=object(), request=initial)

        third_cursor = first["matches"][2]["cursor"]
        follow = AdvancedFetchParams(
            url="https://example.com",
            render={"cursor": third_cursor},
            max_length=12,
        )
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html=html, final_url="https://example.com/final"
                    )
                ),
            ),
            patch("advanced_fetch_mcp.workflow.render_view", return_value="a refund b c refund d e refund f"),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
        ):
            jumped = await execute_advanced_fetch(ctx=object(), request=follow)

        self.assertIn("refund", jumped["result"])

    async def test_find_limits_matches_to_current_default(self):
        html = "<main>" + " ".join(["refund"] * (MAX_FIND_MATCHES + 4)) + "</main>"
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="find",
            find={"query": "refund"},
            max_length=20,
        )
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html=html, final_url="https://example.com/final"
                    )
                ),
            ),
            patch(
                "advanced_fetch_mcp.workflow.render_view",
                return_value=" ".join(["refund"] * (MAX_FIND_MATCHES + 4)),
            ),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertEqual(len(result["matches"]), MAX_FIND_MATCHES)
        self.assertTrue(result["matches_truncated"])
        self.assertIn(FIND_MATCHES_WARNING, result["warnings"])

    async def test_find_limit_overrides_default_match_cap(self):
        html = "<main>" + " ".join(["refund"] * (MAX_FIND_MATCHES + 4)) + "</main>"
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="find",
            find={"query": "refund", "limit": 2},
            max_length=20,
        )
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html=html, final_url="https://example.com/final"
                    )
                ),
            ),
            patch(
                "advanced_fetch_mcp.workflow.render_view",
                return_value=" ".join(["refund"] * (MAX_FIND_MATCHES + 4)),
            ),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertEqual(len(result["matches"]), 2)
        self.assertEqual(result["matches_total"], MAX_FIND_MATCHES + 4)
        self.assertTrue(result["matches_truncated"])

    async def test_find_start_index_skips_earlier_matches(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="find",
            find={"query": "refund", "start_index": 1, "limit": 1},
            max_length=20,
        )
        rendered = "A refund B refund C"
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html=f"<main>{rendered}</main>",
                        final_url="https://example.com/final",
                    )
                ),
            ),
            patch("advanced_fetch_mcp.workflow.render_view", return_value=rendered),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertEqual(len(result["matches"]), 1)
        self.assertEqual(result["matches_total"], 2)
        self.assertEqual(result["matches"][0]["cursor"], rendered.rfind("refund"))
        self.assertEqual(result["next_cursor"], rendered.rfind("refund"))
        self.assertTrue(result["matches_truncated"])

    async def test_find_snippet_max_chars_overrides_default(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="find",
            find={"query": "refund", "snippet_max_chars": 30},
            max_length=20,
        )
        rendered = "prefix words before refund trailing words after"
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html=f"<main>{rendered}</main>",
                        final_url="https://example.com/final",
                    )
                ),
            ),
            patch("advanced_fetch_mcp.workflow.render_view", return_value=rendered),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertLessEqual(len(result["matches"][0]["snippet"]), 32)

    async def test_find_start_index_beyond_total_returns_empty_page(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="find",
            find={"query": "refund", "start_index": 5},
            max_length=20,
        )
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html="<main>refund here</main>",
                        final_url="https://example.com/final",
                    )
                ),
            ),
            patch("advanced_fetch_mcp.workflow.render_view", return_value="refund here"),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertTrue(result["found"])
        self.assertEqual(result["matches_total"], 1)
        self.assertEqual(result["matches"], [])
        self.assertTrue(result["matches_truncated"])
        self.assertNotIn("next_cursor", result)

    async def test_view_skips_cache_by_default(self):
        request = AdvancedFetchParams(url="https://example.com")
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch") as get_cache_mock,
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html="<main>new</main>", final_url="https://fresh"
                    )
                ),
            ) as fetch_mock,
            patch("advanced_fetch_mcp.workflow.store_cached_fetch") as store_cache_mock,
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        get_cache_mock.assert_not_called()
        fetch_mock.assert_awaited_once()
        store_cache_mock.assert_called_once_with(
            "https://example.com",
            "dynamic",
            "https://fresh",
            "<main>new</main>",
        )
        self.assertEqual(result["final_url"], "https://fresh")

    async def test_find_prefers_cached_html(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="find",
            find={"query": "cached"},
        )
        with (
            patch(
                "advanced_fetch_mcp.workflow.get_cached_fetch",
                return_value=("https://cached", "<main>cached value</main>"),
            ) as get_cache_mock,
            patch("advanced_fetch_mcp.workflow.fetch_url", new=AsyncMock()) as fetch_mock,
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        get_cache_mock.assert_called_once_with("https://example.com", "dynamic")
        fetch_mock.assert_not_awaited()
        self.assertEqual(result["final_url"], "https://cached")
        self.assertTrue(result["cache_hit"])

    async def test_eval_returns_stringified_result(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="eval",
            eval={"script": "return 123;"},
        )
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch") as get_cache_mock,
            patch(
                "advanced_fetch_mcp.workflow.evaluate_script_on_page",
                new=AsyncMock(
                    return_value=type(
                        "EvalResultStub",
                        (),
                        {
                            "value": 123,
                            "fetch_result": FetchResult(
                                html="",
                                final_url="https://example.com/final",
                            ),
                        },
                    )()
                ),
            ),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        get_cache_mock.assert_not_called()
        self.assertEqual(result["result"], "123")

    async def test_eval_skips_prefetch_and_uses_eval_final_url(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="eval",
            eval={"script": "document.title"},
        )
        with (
            patch("advanced_fetch_mcp.workflow.fetch_url", new=AsyncMock()) as fetch_mock,
            patch(
                "advanced_fetch_mcp.workflow.evaluate_script_on_page",
                new=AsyncMock(
                    return_value=type(
                        "EvalResultStub",
                        (),
                        {
                            "value": "Example",
                            "fetch_result": FetchResult(
                                html="",
                                final_url="https://example.com/eval-final",
                                intervention_ended_by="user_marked_ready",
                            ),
                        },
                    )()
                ),
            ),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)

        fetch_mock.assert_not_awaited()
        self.assertEqual(result["final_url"], "https://example.com/eval-final")
        self.assertEqual(result["intervention_ended_by"], "user_marked_ready")

    async def test_intervention_metadata_is_exposed(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            fetch={"require_user_intervention": True},
        )
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html="<main>x</main>",
                        final_url="https://example.com/final",
                        intervention_ended_by="user_marked_ready",
                    )
                ),
            ),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertEqual(result["intervention_ended_by"], "user_marked_ready")

    async def test_eval_object_is_json_stringified(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="eval",
            eval={"script": "return ({ title: document.title });"},
        )
        with (
            patch(
                "advanced_fetch_mcp.workflow.evaluate_script_on_page",
                new=AsyncMock(
                    return_value=type(
                        "EvalResultStub",
                        (),
                        {
                            "value": {"title": "Example"},
                            "fetch_result": FetchResult(
                                html="",
                                final_url="https://example.com/final",
                            ),
                        },
                    )()
                ),
            ),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertIn('"title": "Example"', result["result"])

    async def test_find_no_match_keeps_matches_total_zero(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="find",
            find={"query": "refund"},
            max_length=20,
        )
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html="<main>hello world</main>",
                        final_url="https://example.com/final",
                    )
                ),
            ),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertFalse(result["found"])
        self.assertEqual(result["matches_total"], 0)

    async def test_sampling_failure_falls_back_to_rendered_view(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="sampling",
            sampling={"prompt": "提炼一下"},
        )
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html="<main>Hello</main>", final_url="https://example.com/final"
                    )
                ),
            ),
            patch("advanced_fetch_mcp.workflow.render_view", return_value="Hello"),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
            patch(
                "advanced_fetch_mcp.workflow.run_prompt_extraction",
                new=AsyncMock(side_effect=RuntimeError("llm down")),
            ),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertIn("Hello", result["result"])
        self.assertIn("warnings", result)

    async def test_find_no_match_returns_found_false_and_no_cursor(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="find",
            find={"query": "refund"},
            max_length=20,
        )
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html="<main>hello world</main>",
                        final_url="https://example.com/final",
                    )
                ),
            ),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertFalse(result["found"])
        self.assertEqual(result["result"], "")
        self.assertNotIn("next_cursor", result)
