from __future__ import annotations

import asyncio
from typing import Any, Dict

from dotenv import load_dotenv
from fastmcp import Context, FastMCP

from .browser import browser_manager
from .params import (
    AdvancedFetchParams,
    CursorParam,
    EvaluateJsParam,
    ExtractPromptParam,
    FindInPageParam,
    FindWithRegexParam,
    MaxLengthParam,
    ModeParam,
    OutputFormatParam,
    RefreshCacheParam,
    RequireInterventionParam,
    StrategyParam,
    StripSelectorsParam,
    TimeoutParam,
    UrlParam,
    WaitForParam,
)
from .settings import ENV_FILE
from .workflow import execute_advanced_fetch

load_dotenv(ENV_FILE)

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
    strip_selectors: StripSelectorsParam,
    cursor: CursorParam,
    max_length: MaxLengthParam,
    find_in_page: FindInPageParam,
    find_with_regex: FindWithRegexParam,
    extract_prompt: ExtractPromptParam,
    evaluate_js: EvaluateJsParam,
    require_user_intervention: RequireInterventionParam,
    refresh_cache: RefreshCacheParam,
) -> Dict[str, Any]:
    """快速、强大、节省 Token 的动态网页抓取工具。"""
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
