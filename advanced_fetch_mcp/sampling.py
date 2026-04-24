from __future__ import annotations

from typing import Any, Dict, Optional

from fastmcp.utilities.types import ModelPreferences
from mcp.types import ModelHint

from .settings import PROMPT_INPUT_MAX_CHARS


async def run_prompt_extraction(
    *,
    ctx: Any,
    source_text: str,
    prompt: str,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    text = source_text[:PROMPT_INPUT_MAX_CHARS]
    if ctx is None:
        raise RuntimeError("prompt 功能需要可用的 MCP 上下文。")

    model_preferences = None
    if model is not None:
        model_preferences = ModelPreferences(
            hints=[ModelHint(name=model)],
            speedPriority=0.8,
            intelligencePriority=0.5,
        )

    response = await ctx.sample(
        f"{prompt}\n\n以下是网页文本：\n{text}",
        model_preferences=model_preferences,
    )
    if hasattr(response, "text"):
        return {"value": response.text}
    return {"value": str(response)}
