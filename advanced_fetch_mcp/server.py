from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import find_dotenv, load_dotenv


def _load_project_dotenv() -> Optional[Path]:
    """
    Load .env before importing any local modules that read environment variables.

    Priority:
    1. Current working directory (.env next to the directory passed via `uv --directory`)
    2. dotenv's cwd-based discovery
    3. Package-adjacent fallback
    """
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        load_dotenv(cwd_env, override=False)
        return cwd_env

    discovered = find_dotenv(filename=".env", usecwd=True)
    if discovered:
        load_dotenv(discovered, override=False)
        return Path(discovered)

    package_env = Path(__file__).resolve().parent.parent / ".env"
    if package_env.exists():
        load_dotenv(package_env, override=False)
        return package_env

    return None


_LOADED_DOTENV_PATH = _load_project_dotenv()

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
from .settings import logger
from .workflow import execute_advanced_fetch

if _LOADED_DOTENV_PATH is not None:
    logger.info("[Config] 已加载 .env: %s", _LOADED_DOTENV_PATH)
else:
    logger.info("[Config] 未找到 .env，继续使用系统环境变量")

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
