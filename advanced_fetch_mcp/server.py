from __future__ import annotations

import asyncio
from typing import Any, Dict

from dotenv import load_dotenv
from fastmcp import Context, FastMCP

from .browser import browser_manager
from .params import (
    AdvancedFetchParams,
    CursorParam,
    EvaluateJSParam,
    FindInPageParam,
    FindWithRegexParam,
    KeepMediaParam,
    MaxLengthParam,
    MarkdownifyParam,
    ModeParam,
    PromptParam,
    RefreshCacheParam,
    RequireInterventionParam,
    StrategyParam,
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
    mode: ModeParam = "dynamic",
    wait_for: WaitForParam = 0,
    timeout: TimeoutParam = None,
    markdownify: MarkdownifyParam = True,
    strategy: StrategyParam = "strict",
    keep_media: KeepMediaParam = False,
    cursor: CursorParam = None,
    max_length: MaxLengthParam = DEFAULT_MAX_LENGTH,
    find_in_page: FindInPageParam = None,
    find_with_regex: FindWithRegexParam = False,
    prompt: PromptParam = None,
    evaluateJS: EvaluateJSParam = None,
    require_user_intervention: RequireInterventionParam = False,
    refresh_cache: RefreshCacheParam = False,
) -> Dict[str, Any]:
    """网页抓取工具。"""
    request = AdvancedFetchParams(
        url=url,
        mode=mode,
        wait_for=wait_for,
        timeout=timeout,
        markdownify=markdownify,
        strategy=strategy,
        keep_media=keep_media,
        cursor=cursor,
        max_length=max_length,
        find_in_page=find_in_page,
        find_with_regex=find_with_regex,
        prompt=prompt,
        evaluateJS=evaluateJS,
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
