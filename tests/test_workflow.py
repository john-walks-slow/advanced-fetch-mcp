import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastmcp.server.elicitation import (
    AcceptedElicitation,
    CancelledElicitation,
    DeclinedElicitation,
)

from advanced_fetch_mcp.fetch import FetchResult
from advanced_fetch_mcp.params import AdvancedFetchParams
from advanced_fetch_mcp.settings import MAX_FIND_MATCHES
from advanced_fetch_mcp.workflow import FIND_MATCHES_WARNING, execute_advanced_fetch

MOCK_REFID = "a1b2c3d4e5f6"


class WorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_result_is_markdown_view(self):
        request = AdvancedFetchParams(url="https://example.com")
        with (
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
            patch(
                "advanced_fetch_mcp.workflow.store_cached_fetch",
                return_value=MOCK_REFID,
            ),
        ):
            result, _ = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertIn("Hello", result["result"])
        self.assertNotIn("img", result["result"])
        self.assertEqual(result["refid"], MOCK_REFID)

    async def test_sampling_result_becomes_primary_result(self):
        with patch("advanced_fetch_mcp.params.ENABLE_PROMPT_EXTRACTION", True):
            request = AdvancedFetchParams(
                url="https://example.com",
                operation="sampling",
                sampling={"prompt": "提取标题"},
            )
        with (
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html="<main>Hello</main>", final_url="https://example.com/final"
                    )
                ),
            ),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch", return_value=MOCK_REFID),
            patch(
                "advanced_fetch_mcp.workflow.run_prompt_extraction",
                new=AsyncMock(return_value={"value": "标题：Hello"}),
            ),
        ):
            result, _ = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertEqual(result["result"], "标题：Hello")
        self.assertEqual(result["refid"], MOCK_REFID)

    async def test_find_returns_minimal_match_summaries(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="find",
            find={"query": "refund"},
            max_length=18,
        )
        with (
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html="<main>prefix refund suffix more refund tail</main>",
                        final_url="https://example.com/final",
                    )
                ),
            ),
            patch(
                "advanced_fetch_mcp.workflow.render_view",
                return_value="prefix refund suffix more refund tail",
            ),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch", return_value=MOCK_REFID),
        ):
            result, _ = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertTrue(result["found"])
        self.assertEqual(set(result["matches"][0].keys()), {"snippet", "cursor"})
        self.assertEqual(result["matches_total"], 2)
        self.assertEqual(result["refid"], MOCK_REFID)

    async def test_cursor_continues_from_view_cursor(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            cursor=8,
            max_length=8,
        )
        with (
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html="<main>0123456789abcdef</main>",
                        final_url="https://example.com/final",
                    )
                ),
            ),
            patch(
                "advanced_fetch_mcp.workflow.render_view",
                return_value="0123456789abcdef",
            ),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch", return_value=MOCK_REFID),
        ):
            result, _ = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertEqual(result["result"], "89abcdef")
        self.assertNotIn("matches", result)
        self.assertEqual(result["refid"], MOCK_REFID)

    async def test_find_then_cursor_jump_to_match(self):
        initial = AdvancedFetchParams(
            url="https://example.com",
            operation="find",
            find={"query": "refund"},
            max_length=12,
        )
        html = "<main>a refund b c refund d e refund f</main>"
        rendered = "a refund b c refund d e refund f"
        with (
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html=html, final_url="https://example.com/final"
                    )
                ),
            ),
            patch("advanced_fetch_mcp.workflow.render_view", return_value=rendered),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch", return_value=MOCK_REFID),
        ):
            first, _ = await execute_advanced_fetch(ctx=object(), request=initial)

        third_cursor = first["matches"][2]["cursor"]
        follow = AdvancedFetchParams(
            url="https://example.com",
            cursor=third_cursor,
            max_length=12,
        )
        with (
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html=html, final_url="https://example.com/final"
                    )
                ),
            ),
            patch("advanced_fetch_mcp.workflow.render_view", return_value=rendered),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch", return_value=MOCK_REFID + "2"),
        ):
            jumped, _ = await execute_advanced_fetch(ctx=object(), request=follow)

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
            patch("advanced_fetch_mcp.workflow.store_cached_fetch", return_value=MOCK_REFID),
        ):
            result, _ = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertEqual(len(result["matches"]), MAX_FIND_MATCHES)
        self.assertTrue(result["matches_truncated"])
        self.assertIn(FIND_MATCHES_WARNING, result["warnings"])
        self.assertEqual(result["refid"], MOCK_REFID)



    async def test_view_does_not_implicitly_cache(self):
        request = AdvancedFetchParams(url="https://example.com")
        with (
            patch(
                "advanced_fetch_mcp.workflow.get_cached_fetch_by_refid",
            ) as get_cache_mock,
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html="<main>new</main>", final_url="https://fresh"
                    )
                ),
            ) as fetch_mock,
            patch(
                "advanced_fetch_mcp.workflow.store_cached_fetch",
                return_value=MOCK_REFID,
            ) as store_cache_mock,
        ):
            result, _ = await execute_advanced_fetch(ctx=object(), request=request)
        get_cache_mock.assert_not_called()
        fetch_mock.assert_awaited_once()
        store_cache_mock.assert_called_once_with(
            "https://example.com",
            "static",
            "https://fresh",
            "<main>new</main>",
        )
        self.assertEqual(result["final_url"], "https://fresh")
        self.assertIn("refid", result)

    async def test_refid_uses_cached_html(self):
        refid_url = MOCK_REFID
        request = AdvancedFetchParams(url=refid_url)
        with (
            patch(
                "advanced_fetch_mcp.workflow._is_refid",
                return_value=True,
            ),
            patch(
                "advanced_fetch_mcp.workflow.get_cached_fetch_by_refid",
                return_value=("https://cached-url", "<main>cached value</main>"),
            ) as get_cache_mock,
            patch("advanced_fetch_mcp.workflow.fetch_url", new=AsyncMock()) as fetch_mock,
            patch("advanced_fetch_mcp.workflow.render_view", return_value="cached value"),
        ):
            result, _ = await execute_advanced_fetch(ctx=object(), request=request)
        get_cache_mock.assert_called_once_with(MOCK_REFID)
        fetch_mock.assert_not_awaited()
        self.assertEqual(result["final_url"], "https://cached-url")
        self.assertEqual(result["refid"], MOCK_REFID)

    async def test_expired_refid_raises_error(self):
        refid_url = MOCK_REFID
        request = AdvancedFetchParams(url=refid_url)
        with (
            patch(
                "advanced_fetch_mcp.workflow._is_refid",
                return_value=True,
            ),
            patch(
                "advanced_fetch_mcp.workflow.get_cached_fetch_by_refid",
                return_value=None,
            ),
        ):
            with self.assertRaises(ValueError) as cm:
                await execute_advanced_fetch(ctx=object(), request=request)
        self.assertIn("不存在或已过期", str(cm.exception))

    async def test_eval_returns_stringified_result(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="eval",
            eval={"script": "return 123;"},
            fetch={"mode": "dynamic"},
        )
        with (
            patch("advanced_fetch_mcp.workflow.get_cached_fetch_by_refid") as get_cache_mock,
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
            result, _ = await execute_advanced_fetch(ctx=object(), request=request)
        get_cache_mock.assert_not_called()
        self.assertEqual(result["result"], "123")
        self.assertNotIn("refid", result)

    async def test_eval_skips_prefetch_and_uses_eval_final_url(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="eval",
            eval={"script": "document.title"},
            fetch={"mode": "dynamic"},
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
                                elicit_ended_by="user_marked_ready",
                            ),
                        },
                    )()
                ),
            ),
        ):
            result, _ = await execute_advanced_fetch(ctx=object(), request=request)

        fetch_mock.assert_not_awaited()
        self.assertEqual(result["final_url"], "https://example.com/eval-final")
        self.assertEqual(result["elicit_ended_by"], "user_marked_ready")

    async def test_elicit_metadata_is_exposed(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="elicit",
            fetch={"mode": "dynamic"},
        )
        with (
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html="<main>x</main>",
                        final_url="https://example.com/final",
                        elicit_ended_by="user_marked_ready",
                    )
                ),
            ),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch", return_value=MOCK_REFID),
        ):
            result, _ = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertEqual(result["elicit_ended_by"], "user_marked_ready")

    async def test_elicit_accepted_proceeds(self):
        """用户确认 elicit → 继续打开浏览器，正常返回"""
        mock_ctx = AsyncMock()
        mock_ctx.elicit = AsyncMock(
            return_value=AcceptedElicitation[bool](data=True)
        )
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="elicit",
            fetch={"mode": "dynamic"},
        )
        with (
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html="<main>Hello</main>",
                        final_url="https://example.com/final",
                    )
                ),
            ),
            patch(
                "advanced_fetch_mcp.workflow.render_view",
                return_value="Hello",
            ),
            patch(
                "advanced_fetch_mcp.workflow.store_cached_fetch",
                return_value=MOCK_REFID,
            ),
        ):
            result, _ = await execute_advanced_fetch(ctx=mock_ctx, request=request)
        mock_ctx.elicit.assert_awaited_once()
        self.assertEqual(result["result"], "Hello")
        self.assertEqual(result["final_url"], "https://example.com/final")

    async def test_elicit_declined_returns_error(self):
        """用户拒绝 elicit → 返回 error，不打开浏览器"""
        mock_ctx = AsyncMock()
        mock_ctx.elicit = AsyncMock(return_value=DeclinedElicitation())
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="elicit",
            fetch={"mode": "dynamic"},
        )
        with (
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(),
            ),
        ):
            result, _ = await execute_advanced_fetch(ctx=mock_ctx, request=request)
        mock_ctx.elicit.assert_awaited_once()
        self.assertFalse(result["success"])
        self.assertIn("取消", result["error"])

    async def test_elicit_cancelled_returns_error(self):
        """用户取消 elicit → 返回 error，不打开浏览器"""
        mock_ctx = AsyncMock()
        mock_ctx.elicit = AsyncMock(return_value=CancelledElicitation())
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="elicit",
            fetch={"mode": "dynamic"},
        )
        with (
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(),
            ),
        ):
            result, _ = await execute_advanced_fetch(ctx=mock_ctx, request=request)
        mock_ctx.elicit.assert_awaited_once()
        self.assertFalse(result["success"])
        self.assertIn("取消", result["error"])

    async def test_elicit_not_supported_falls_back(self):
        """客户端不支持 elicit → fallback，直接开浏览器（原有行为）"""
        # ctx=object() 没有 elicit 方法，会触发 except 回退
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="elicit",
            fetch={"mode": "dynamic"},
        )
        with (
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html="<main>fallback ok</main>",
                        final_url="https://example.com/final",
                    )
                ),
            ),
            patch(
                "advanced_fetch_mcp.workflow.render_view",
                return_value="fallback ok",
            ),
            patch(
                "advanced_fetch_mcp.workflow.store_cached_fetch",
                return_value=MOCK_REFID,
            ),
        ):
            result, _ = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertEqual(result["result"], "fallback ok")
        self.assertEqual(result["final_url"], "https://example.com/final")

    async def test_eval_object_is_json_stringified(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="eval",
            eval={"script": "return ({ title: document.title });"},
            fetch={"mode": "dynamic"},
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
            result, _ = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertIn('"title": "Example"', result["result"])

    async def test_find_no_match_keeps_matches_total_zero(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            operation="find",
            find={"query": "refund"},
            max_length=20,
        )
        with (
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html="<main>hello world</main>",
                        final_url="https://example.com/final",
                    )
                ),
            ),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch", return_value=MOCK_REFID),
        ):
            result, _ = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertFalse(result["found"])
        self.assertEqual(result["matches_total"], 0)

    async def test_sampling_failure_falls_back_to_rendered_view(self):
        with patch("advanced_fetch_mcp.params.ENABLE_PROMPT_EXTRACTION", True):
            request = AdvancedFetchParams(
                url="https://example.com",
                operation="sampling",
                sampling={"prompt": "提炼一下"},
            )
        with (
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html="<main>Hello</main>", final_url="https://example.com/final"
                    )
                ),
            ),
            patch("advanced_fetch_mcp.workflow.render_view", return_value="Hello"),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch", return_value=MOCK_REFID),
            patch(
                "advanced_fetch_mcp.workflow.run_prompt_extraction",
                new=AsyncMock(side_effect=RuntimeError("llm down")),
            ),
        ):
            result, _ = await execute_advanced_fetch(ctx=object(), request=request)
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
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html="<main>hello world</main>",
                        final_url="https://example.com/final",
                    )
                ),
            ),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch", return_value=MOCK_REFID),
        ):
            result, _ = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertFalse(result["found"])
        self.assertEqual(result["result"], "")
        self.assertNotIn("next_cursor", result)

    async def test_view_with_links_includes_links_in_response(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            max_length=200,
        )
        mock_links_result = {
            "links": [
                {"href": "/page1", "text": "Page 1", "abs_url": "https://example.com/page1"},
            ],
            "links_total": 1,
            "links_truncated": False,
        }
        with (
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html="<main>Hello</main>",
                        final_url="https://example.com/final",
                    )
                ),
            ),
            patch("advanced_fetch_mcp.workflow.render_view", return_value="Hello"),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch", return_value=MOCK_REFID),
            patch(
                "advanced_fetch_mcp.workflow.extract_links",
                return_value=mock_links_result,
            ),
        ):
            result, _ = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertEqual(result["links"], mock_links_result["links"])
        self.assertEqual(result["links_total"], 1)
        self.assertNotIn("links_truncated", result)  # False → omitted

    async def test_view_with_links_returns_empty_when_no_links(self):
        request = AdvancedFetchParams(
            url="https://example.com",
            max_length=200,
        )
        with (
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html="<main>Hello</main>",
                        final_url="https://example.com/final",
                    )
                ),
            ),
            patch("advanced_fetch_mcp.workflow.render_view", return_value="Hello"),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch", return_value=MOCK_REFID),
        ):
            result, _ = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertEqual(result["links"], [])
        self.assertEqual(result["links_total"], 0)

    # ── Multi-URL ──────────────────────────────────────────

    def test_multi_url_empty_list_raises_error(self):
        with self.assertRaises(ValueError):
            AdvancedFetchParams(url=[])

    def test_multi_url_with_elicit_raises_error(self):
        with self.assertRaises(ValueError):
            AdvancedFetchParams(
                url=["https://a.com", "https://b.com"],
                operation="elicit",
                fetch={"mode": "dynamic"},
            )

    def test_multi_url_with_cursor_raises_error(self):
        with self.assertRaises(ValueError):
            AdvancedFetchParams(
                url=["https://a.com", "https://b.com"],
                cursor=5,
            )

    async def test_multi_url_parallel_success(self):
        from advanced_fetch_mcp.server import _execute_multi_url

        request = AdvancedFetchParams(
            url=["https://page1.com", "https://page2.com"],
            max_length=9999,
        )
        mock_results = [
            ({"success": True, "final_url": "https://page1.com", "result": "Page1 content"}, None),
            ({"success": True, "final_url": "https://page2.com", "result": "Page2 content"}, None),
        ]

        with (
            patch(
                "advanced_fetch_mcp.server.execute_advanced_fetch",
                new=AsyncMock(side_effect=mock_results),
            ),
        ):
            blocks = await _execute_multi_url(ctx=object(), request=request)

        self.assertEqual(len(blocks), 1)  # no screenshots → 1 Text block
        payload = json.loads(blocks[0].text)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["results_total"], 2)
        self.assertEqual(payload["results_succeeded"], 2)
        self.assertEqual(payload["results_failed"], 0)
        self.assertEqual(payload["results"][0]["result"], "Page1 content")
        self.assertEqual(payload["results"][1]["result"], "Page2 content")
        self.assertEqual(payload["results"][0]["url"], "https://page1.com")
        self.assertEqual(payload["results"][1]["url"], "https://page2.com")

    async def test_multi_url_partial_failure(self):
        from advanced_fetch_mcp.server import _execute_multi_url

        request = AdvancedFetchParams(
            url=["https://good.com", "https://bad.com"],
            max_length=9999,
        )
        mock_results = [
            ({"success": True, "final_url": "https://good.com", "result": "OK"}, None),
            Exception("Connection refused"),
        ]

        with (
            patch(
                "advanced_fetch_mcp.server.execute_advanced_fetch",
                new=AsyncMock(side_effect=mock_results),
            ),
        ):
            blocks = await _execute_multi_url(ctx=object(), request=request)

        payload = json.loads(blocks[0].text)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["results_total"], 2)
        self.assertEqual(payload["results_succeeded"], 1)
        self.assertEqual(payload["results_failed"], 1)
        self.assertTrue(payload["results"][0]["success"])
        self.assertFalse(payload["results"][1]["success"])

    async def test_multi_url_with_screenshots(self):
        from advanced_fetch_mcp.server import _execute_multi_url

        request = AdvancedFetchParams(
            url=["https://page1.com", "https://page2.com"],
            view={"with_screenshot": True},
            max_length=9999,
        )
        fake_png = b"fake_png_data_12345"
        mock_results = [
            (
                {"success": True, "final_url": "https://page1.com", "result": "A"},
                fake_png,
            ),
            (
                {"success": True, "final_url": "https://page2.com", "result": "B"},
                None,
            ),
        ]

        with (
            patch(
                "advanced_fetch_mcp.server.execute_advanced_fetch",
                new=AsyncMock(side_effect=mock_results),
            ),
        ):
            blocks = await _execute_multi_url(ctx=object(), request=request)

        # 1 TextContent + 1 Image (only page1 has screenshot)
        self.assertEqual(len(blocks), 2)
        payload = json.loads(blocks[0].text)
        self.assertEqual(payload["results_succeeded"], 2)
        # screenshot popped from result dict
        self.assertNotIn("screenshot", payload["results"][0])
        self.assertNotIn("screenshot", payload["results"][1])
        # Image block contains the fake PNG
        self.assertEqual(blocks[1].data, fake_png)

    async def test_single_url_workflow_unchanged(self):
        """Verify that a single string URL still produces the same workflow result shape."""
        request = AdvancedFetchParams(url="https://example.com")
        with (
            patch(
                "advanced_fetch_mcp.workflow.fetch_url",
                new=AsyncMock(
                    return_value=FetchResult(
                        html="<main>Hello</main>", final_url="https://example.com/final"
                    )
                ),
            ),
            patch("advanced_fetch_mcp.workflow.render_view", return_value="Hello"),
            patch("advanced_fetch_mcp.workflow.store_cached_fetch", return_value=MOCK_REFID),
        ):
            result, _ = await execute_advanced_fetch(ctx=object(), request=request)
        self.assertIn("Hello", result["result"])
        self.assertNotIn("results", result)  # not a multi-URL result
        self.assertIn("refid", result)

    async def test_multi_url_output_to_file(self):
        import tempfile

        from advanced_fetch_mcp.server import _execute_multi_url

        request = AdvancedFetchParams(
            url=["https://page1.com", "https://page2.com"],
            output_to_file="/tmp/non_existent_dir/test_output.json",
            max_length=9999,
        )
        mock_results = [
            ({"success": True, "final_url": "https://page1.com", "result": "Page1"}, None),
            ({"success": True, "final_url": "https://page2.com", "result": "Page2"}, None),
        ]

        with (
            patch(
                "advanced_fetch_mcp.server.execute_advanced_fetch",
                new=AsyncMock(side_effect=mock_results),
            ),
        ):
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
                tmp_path = tmp.name

            try:
                request.output_to_file = tmp_path
                blocks = await _execute_multi_url(ctx=object(), request=request)
                payload = json.loads(blocks[0].text)
                # Response is simplified for output_to_file
                self.assertTrue(payload["success"])
                self.assertEqual(payload["output_to_file"], tmp_path)
                # Verify file was written with full results
                with open(tmp_path, "r") as f:
                    written = json.load(f)
                self.assertIn("results", written)
                self.assertEqual(len(written["results"]), 2)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
