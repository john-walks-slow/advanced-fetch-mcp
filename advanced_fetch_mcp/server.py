from __future__ import annotations

import asyncio
from typing import Any, Dict

from fastmcp import Context, FastMCP

from .browser import browser_manager
from .params import (
    AdvancedFetchParams,
    CursorParam,
    EvaluateJsParam,
    ExtractPromptParam,
    ExtraElementsParam,
    FindInPageParam,
    FindWithRegexParam,
    MaxLengthParam,
    ModeParam,
    OutputFormatParam,
    RequireInterventionParam,
    StrategyParam,
    TimeoutParam,
    UrlParam,
    WaitForParam,
    schema_text,
)
from .workflow import execute_advanced_fetch


mcp = FastMCP("AdvancedFetchMCP")


@mcp.tool()
async def advanced_fetch(
    ctx: Context,
    url: UrlParam,
    mode: ModeParam,
    wait_for: WaitForParam,
    timeout: TimeoutParam,
    output_format: OutputFormatParam,
    strategy: StrategyParam,
    extra_elements: ExtraElementsParam,
    cursor: CursorParam,
    max_length: MaxLengthParam,
    find_in_page: FindInPageParam,
    find_with_regex: FindWithRegexParam,
    extract_prompt: ExtractPromptParam,
    evaluate_js: EvaluateJsParam,
    require_user_intervention: RequireInterventionParam,
) -> Dict[str, Any]:
    """快速、强大、节省 Token 的网页抓取工具。"""
    advanced_fetch.__doc__ = schema_text(
        "快速、强大、节省 Token 的网页抓取工具。",
        "Fast, powerful, token-efficient web fetching tool.",
    )
    params_dict = {
        k: v for k, v in locals().items() if k in AdvancedFetchParams.model_fields
    }
    request = AdvancedFetchParams.model_validate(params_dict)
    return await execute_advanced_fetch(ctx=ctx, request=request)


def cleanup():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        loop.create_task(browser_manager.close())
    else:
        asyncio.run(browser_manager.close())
