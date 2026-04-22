from __future__ import annotations

import asyncio
from typing import Any, Dict

from fastmcp import Context, FastMCP

from .browser import browser_manager
from .params import (
    AdvancedFetchParams,
    EvalParam,
    FetchParam,
    FindParam,
    MaxLengthParam,
    OperationParam,
    RenderParam,
    SamplingParam,
    UrlParam,
    schema_text,
)
from .workflow import execute_advanced_fetch


mcp = FastMCP("AdvancedFetchMCP")


@mcp.tool()
async def advanced_fetch(
    ctx: Context,
    url: UrlParam,
    operation: OperationParam,
    fetch: FetchParam,
    render: RenderParam,
    max_length: MaxLengthParam,
    find: FindParam,
    sampling: SamplingParam,
    eval: EvalParam,
) -> Dict[str, Any]:
    params_dict = {
        k: v for k, v in locals().items() if k in AdvancedFetchParams.model_fields
    }
    request = AdvancedFetchParams.model_validate(params_dict)
    return await execute_advanced_fetch(ctx=ctx, request=request)


advanced_fetch.__doc__ = schema_text(
    "快速、强大、节省 Token 的网页抓取工具。",
    "Fast, powerful, token-efficient web fetching tool.",
)


def cleanup():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        loop.create_task(browser_manager.close())
    else:
        asyncio.run(browser_manager.close())
