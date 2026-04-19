import unittest
from unittest.mock import AsyncMock, patch

from advanced_fetch_mcp.dsl import AdvancedFetchParams
from advanced_fetch_mcp.fetch import FetchResult
from advanced_fetch_mcp.workflow import execute_advanced_fetch


class WorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_result_is_markdown_view(self):
        request = AdvancedFetchParams(url="https://example.com")
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch("advanced_fetch_mcp.workflow.fetch_url", new=AsyncMock(return_value=FetchResult(html="<main>Hello<img src='x'/></main>", final_url="https://example.com/final"))),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertIn("Hello", result["result"])
        self.assertNotIn("img", result["result"])

    async def test_prompt_becomes_primary_result(self):
        request = AdvancedFetchParams(url="https://example.com", prompt="提取标题")
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch("advanced_fetch_mcp.workflow.fetch_url", new=AsyncMock(return_value=FetchResult(html="<main>Hello</main>", final_url="https://example.com/final"))),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
            patch("advanced_fetch_mcp.workflow.run_prompt_extraction", new=AsyncMock(return_value={"value": "标题：Hello"})),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertEqual(result["result"], "标题：Hello")

    async def test_find_returns_minimal_match_summaries(self):
        request = AdvancedFetchParams(url="https://example.com", find_in_page="refund", max_length=18)
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch("advanced_fetch_mcp.workflow.fetch_url", new=AsyncMock(return_value=FetchResult(html="<main>prefix refund suffix more refund tail</main>", final_url="https://example.com/final"))),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertTrue(result["found"])
        self.assertEqual(set(result["matches"][0].keys()), {"snippet", "cursor"})
        self.assertEqual(result["matches_total"], 2)

    async def test_cursor_continues_from_position(self):
        request = AdvancedFetchParams(url="https://example.com", cursor=8, max_length=8)
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch("advanced_fetch_mcp.workflow.fetch_url", new=AsyncMock(return_value=FetchResult(html="<main>0123456789abcdef</main>", final_url="https://example.com/final"))),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertEqual(result["result"], "89abcdef")
        self.assertNotIn("matches", result)

    async def test_find_then_cursor_jump_to_match(self):
        initial = AdvancedFetchParams(url="https://example.com", find_in_page="refund", max_length=12)
        html = "<main>a refund b c refund d e refund f</main>"
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch("advanced_fetch_mcp.workflow.fetch_url", new=AsyncMock(return_value=FetchResult(html=html, final_url="https://example.com/final"))),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
        ):
            first = await execute_advanced_fetch(ctx=object(), request=initial)

        third_cursor = first["matches"][2]["cursor"]
        follow = AdvancedFetchParams(url="https://example.com", cursor=third_cursor, max_length=12)
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch("advanced_fetch_mcp.workflow.fetch_url", new=AsyncMock(return_value=FetchResult(html=html, final_url="https://example.com/final"))),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
        ):
            jumped = await execute_advanced_fetch(ctx=object(), request=follow)

        self.assertIn("refund", jumped["result"])

    async def test_find_limits_matches_to_eight(self):
        html = "<main>" + " ".join(["refund"] * 12) + "</main>"
        request = AdvancedFetchParams(url="https://example.com", find_in_page="refund", max_length=20)
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch("advanced_fetch_mcp.workflow.fetch_url", new=AsyncMock(return_value=FetchResult(html=html, final_url="https://example.com/final"))),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertEqual(len(result["matches"]), 8)
        self.assertTrue(result["matches_truncated"])

    async def test_refresh_cache_true_bypasses_existing_cache_and_rewrites_cache(self):
        request = AdvancedFetchParams(url="https://example.com", refresh_cache=True)
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=("https://cached", "<main>old</main>")) as get_cache_mock,
            patch("advanced_fetch_mcp.workflow.fetch_url", new=AsyncMock(return_value=FetchResult(html="<main>new</main>", final_url="https://fresh"))) as fetch_mock,
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
        self.assertIn("new", result["result"])

    async def test_evaluate_js_returns_stringified_result(self):
        request = AdvancedFetchParams(url="https://example.com", evaluateJS="return 123;")
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch("advanced_fetch_mcp.workflow.fetch_url", new=AsyncMock(return_value=FetchResult(html="<main>x</main>", final_url="https://example.com/final"))),
            patch("advanced_fetch_mcp.workflow.evaluate_script_on_page", new=AsyncMock(return_value=123)),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertEqual(result["result"], "123")

    async def test_intervention_metadata_is_exposed(self):
        request = AdvancedFetchParams(url="https://example.com", require_user_intervention=True)
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch("advanced_fetch_mcp.workflow.fetch_url", new=AsyncMock(return_value=FetchResult(html="<main>x</main>", final_url="https://example.com/final", intervention_ended_by="user_marked_ready"))),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertEqual(result["intervention_ended_by"], "user_marked_ready")

    async def test_evaluate_js_object_is_json_stringified(self):
        request = AdvancedFetchParams(url="https://example.com", evaluateJS="return ({ title: document.title });")
        with (
            patch("advanced_fetch_mcp.workflow.fetch_url", new=AsyncMock(return_value=FetchResult(html="<main>x</main>", final_url="https://example.com/final"))),
            patch("advanced_fetch_mcp.workflow.evaluate_script_on_page", new=AsyncMock(return_value={"title": "Example"})),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertIn('"title": "Example"', result["result"])

    async def test_find_no_match_keeps_matches_total_zero(self):
        request = AdvancedFetchParams(url="https://example.com", find_in_page="refund", max_length=20)
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch("advanced_fetch_mcp.workflow.fetch_url", new=AsyncMock(return_value=FetchResult(html="<main>hello world</main>", final_url="https://example.com/final"))),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertFalse(result["found"])
        self.assertEqual(result["matches_total"], 0)

    async def test_refresh_cache_false_prefers_cached_html(self):
        request = AdvancedFetchParams(url="https://example.com", refresh_cache=False)
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=("https://cached", "<main>cached</main>")) as get_cache_mock,
            patch("advanced_fetch_mcp.workflow.fetch_url", new=AsyncMock()) as fetch_mock,
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        get_cache_mock.assert_called_once_with("https://example.com", "dynamic")
        fetch_mock.assert_not_awaited()
        self.assertEqual(result["final_url"], "https://cached")

    async def test_require_user_intervention_skips_cache(self):
        request = AdvancedFetchParams(url="https://example.com", require_user_intervention=True)
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=("https://cached", "<main>cached</main>")) as get_cache_mock,
            patch("advanced_fetch_mcp.workflow.fetch_url", new=AsyncMock(return_value=FetchResult(html="<main>fetched</main>", final_url="https://fetched"))) as fetch_mock,
            patch("advanced_fetch_mcp.workflow.store_cached_fetch") as store_cache_mock,
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        get_cache_mock.assert_not_called()
        fetch_mock.assert_awaited_once()
        store_cache_mock.assert_not_called()
        self.assertEqual(result["final_url"], "https://fetched")

    async def test_evaluate_js_skips_cache(self):
        request = AdvancedFetchParams(url="https://example.com", evaluateJS="return 1")
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch") as get_cache_mock,
            patch("advanced_fetch_mcp.workflow.fetch_url", new=AsyncMock(return_value=FetchResult(html="<main>x</main>", final_url="https://example.com/final"))),
            patch("advanced_fetch_mcp.workflow.evaluate_script_on_page", new=AsyncMock(return_value=1)),
        ):
            await execute_advanced_fetch(ctx=object(), request=request)
        get_cache_mock.assert_not_called()

    async def test_prompt_failure_falls_back_to_rendered_view(self):
        request = AdvancedFetchParams(url="https://example.com", prompt="提炼一下")
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch("advanced_fetch_mcp.workflow.fetch_url", new=AsyncMock(return_value=FetchResult(html="<main>Hello</main>", final_url="https://example.com/final"))),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
            patch("advanced_fetch_mcp.workflow.run_prompt_extraction", new=AsyncMock(side_effect=RuntimeError("llm down"))),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertIn("Hello", result["result"])
        self.assertIn("warnings", result)

    async def test_find_no_match_returns_found_false_and_no_cursor(self):
        request = AdvancedFetchParams(url="https://example.com", find_in_page="refund", max_length=20)
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch", return_value=None),
            patch("advanced_fetch_mcp.workflow.fetch_url", new=AsyncMock(return_value=FetchResult(html="<main>hello world</main>", final_url="https://example.com/final"))),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch"),
        ):
            result = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertFalse(result["found"])
        self.assertEqual(result["result"], "")
        self.assertNotIn("next_cursor", result)