"""测试 sampling.py 的 LLM prompt 提取逻辑。"""

import unittest
from unittest.mock import AsyncMock, MagicMock

from advanced_fetch_mcp.sampling import run_prompt_extraction
from advanced_fetch_mcp.settings import PROMPT_INPUT_MAX_CHARS


class RunPromptExtractionTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_text_from_response(self):
        """应返回 response.text 作为结果。"""
        ctx = MagicMock()
        ctx.sample = AsyncMock()
        response = MagicMock()
        response.text = "提取结果：标题是 Hello"
        ctx.sample.return_value = response

        result = await run_prompt_extraction(
            ctx=ctx,
            source_text="这是网页文本内容",
            prompt="提取标题",
        )

        self.assertEqual(result["value"], "提取结果：标题是 Hello")

    async def test_returns_stringified_response_without_text_attr(self):
        """response 没有 text 属性时应 str() 转换。"""
        ctx = MagicMock()
        ctx.sample = AsyncMock()
        ctx.sample.return_value = "直接字符串"

        result = await run_prompt_extraction(
            ctx=ctx,
            source_text="文本",
            prompt="提取",
        )

        self.assertEqual(result["value"], "直接字符串")

    async def test_truncates_long_source_text(self):
        """长文本应截断到 PROMPT_INPUT_MAX_CHARS。"""
        ctx = MagicMock()
        ctx.sample = AsyncMock()
        response = MagicMock()
        response.text = "结果"
        ctx.sample.return_value = response

        long_text = "x" * (PROMPT_INPUT_MAX_CHARS + 5000)
        await run_prompt_extraction(
            ctx=ctx,
            source_text=long_text,
            prompt="提取",
        )

        call_prompt = ctx.sample.await_args.args[0]
        text_part = call_prompt.split("\n\n以下是网页文本：\n", 1)[1]
        self.assertEqual(len(text_part), PROMPT_INPUT_MAX_CHARS)

    async def test_raises_error_when_ctx_is_none(self):
        """ctx 为 None 时应抛出 RuntimeError。"""
        with self.assertRaises(RuntimeError) as cm:
            await run_prompt_extraction(
                ctx=None,
                source_text="文本",
                prompt="提取",
            )
        self.assertIn("MCP 上下文", str(cm.exception))

    async def test_includes_prompt_and_text_in_sample_call(self):
        """sample 调用应包含 prompt 和文本。"""
        ctx = MagicMock()
        ctx.sample = AsyncMock()
        response = MagicMock()
        response.text = "结果"
        ctx.sample.return_value = response

        await run_prompt_extraction(
            ctx=ctx,
            source_text="网页内容",
            prompt="请提取标题",
        )

        call_prompt = ctx.sample.await_args.args[0]
        self.assertIn("请提取标题", call_prompt)
        self.assertIn("以下是网页文本：", call_prompt)
        self.assertIn("网页内容", call_prompt)
