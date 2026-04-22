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
    speed_priority: float = 0.8,
    intelligence_priority: float = 0.5,
) -> Dict[str, Any]:
    text = source_text[:PROMPT_INPUT_MAX_CHARS]
    if ctx is None:
        raise RuntimeError("prompt 功能需要可用的 MCP 上下文。")

    model_preferences = None
    if model is not None or speed_priority != 0.8 or intelligence_priority != 0.5:
        hints: list[ModelHint] = []
        if model:
            hints.append(ModelHint(name=model))
        model_preferences = ModelPreferences(
            hints=hints if hints else None,
            speedPriority=speed_priority,
            intelligencePriority=intelligence_priority,
        )

    response = await ctx.sample(
        f"{prompt}\n\n以下是网页文本：\n{text}",
        model_preferences=model_preferences,
    )
    if hasattr(response, "text"):
        return {"value": response.text}
    return {"value": str(response)}
