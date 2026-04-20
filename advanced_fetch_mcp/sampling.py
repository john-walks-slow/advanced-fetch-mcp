from __future__ import annotations

from typing import Any, Dict

from .settings import PROMPT_INPUT_MAX_CHARS


async def run_prompt_extraction(*, ctx: Any, source_text: str, prompt: str) -> Dict[str, Any]:
    text = source_text[:PROMPT_INPUT_MAX_CHARS]
    if ctx is None:
        raise RuntimeError("prompt 功能需要可用的 MCP 上下文。")

    response = await ctx.sample(
        f"{prompt}\n\n以下是网页文本：\n{text}",
    )
    if hasattr(response, "text"):
        return {"value": response.text}
    return {"value": str(response)}
