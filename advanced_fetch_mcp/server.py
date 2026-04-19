from __future__ import annotations

import asyncio
from typing import Any, Dict

from dotenv import load_dotenv
from fastmcp import Context, FastMCP

from .browser import browser_manager
from .params import (
    AdvancedFetchParams,
    CursorParam,
    DEFAULT_FIND_WITH_REGEX,
    DEFAULT_MODE,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_REFRESH_CACHE,
    DEFAULT_REQUIRE_USER_INTERVENTION,
    DEFAULT_STRIP_SELECTORS,
    DEFAULT_STRATEGY,
    DEFAULT_WAIT_FOR,
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
from .settings import DEFAULT_MAX_LENGTH, ENV_FILE
from .workflow import execute_advanced_fetch

load_dotenv(ENV_FILE)

mcp = FastMCP("AdvancedFetchMCP")


@mcp.tool()
async def advanced_fetch(
    ctx: Context,
    url: UrlParam,
    mode: ModeParam = DEFAULT_MODE,
    wait_for: WaitForParam = DEFAULT_WAIT_FOR,
    timeout: TimeoutParam = None,
    output_format: OutputFormatParam = DEFAULT_OUTPUT_FORMAT,
    strategy: StrategyParam = DEFAULT_STRATEGY,
    strip_selectors: StripSelectorsParam = list(DEFAULT_STRIP_SELECTORS),
    cursor: CursorParam = None,
    max_length: MaxLengthParam = DEFAULT_MAX_LENGTH,
    find_in_page: FindInPageParam = None,
    find_with_regex: FindWithRegexParam = DEFAULT_FIND_WITH_REGEX,
    extract_prompt: ExtractPromptParam = None,
    evaluate_js: EvaluateJsParam = None,
    require_user_intervention: RequireInterventionParam = (
        DEFAULT_REQUIRE_USER_INTERVENTION
    ),
    refresh_cache: RefreshCacheParam = DEFAULT_REFRESH_CACHE,
) -> Dict[str, Any]:
    """网页抓取工具。"""
    request = AdvancedFetchParams(
        url=url,
        mode=mode,
        wait_for=wait_for,
        timeout=timeout,
        output_format=output_format,
        strategy=strategy,
        strip_selectors=strip_selectors,
        cursor=cursor,
        max_length=max_length,
        find_in_page=find_in_page,
        find_with_regex=find_with_regex,
        extract_prompt=extract_prompt,
        evaluate_js=evaluate_js,
        require_user_intervention=require_user_intervention,
        refresh_cache=refresh_cache,
    )
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