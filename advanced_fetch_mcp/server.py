from __future__ import annotations

import asyncio
from typing import Any, Dict

from dotenv import load_dotenv
from fastmcp import Context, FastMCP

from .browser import browser_manager
from .dsl import AdvancedFetchParams
from .settings import ENV_FILE
from .workflow import execute_advanced_fetch

load_dotenv(ENV_FILE)

mcp = FastMCP("AdvancedFetchMCP")


@mcp.tool()
async def advanced_fetch(
    request: AdvancedFetchParams,
    ctx: Context,
) -> Dict[str, Any]:
    """网页抓取工具。"""
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