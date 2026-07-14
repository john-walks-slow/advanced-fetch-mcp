from __future__ import annotations

import asyncio
import json
import os
from typing import List, Union

from fastmcp import Context, FastMCP
from fastmcp.utilities.types import Image
from mcp.types import ImageContent, TextContent

from .browser import browser_manager
from .params import (
    AdvancedFetchParams,
    ElicitParam,
    EvalParam,
    FetchParam,
    FindParam,
    OperationParam,
    SamplingParam,
    UrlParam,
    ViewParam,
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
    view: ViewParam,
    find: FindParam,
    sampling: SamplingParam,
    eval: EvalParam,
    elicit: ElicitParam = None,
) -> List[Union[TextContent, ImageContent]]:
    params_dict = {
        k: v for k, v in locals().items() if k in AdvancedFetchParams.model_fields
    }
    request = AdvancedFetchParams.model_validate(params_dict)

    if request.output_to_file:
        request.view.max_length = 10**9

    result_dict, screenshot_bytes = await execute_advanced_fetch(ctx=ctx, request=request)

    if request.output_to_file and result_dict.get("success"):
        output_path = request.output_to_file
        dir_path = os.path.dirname(output_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)
        result_dict = {"success": True, "output_to_file": output_path}

    blocks: List[Union[TextContent, ImageContent]] = [
        TextContent(type="text", text=json.dumps(result_dict, ensure_ascii=False, indent=2))
    ]
    if screenshot_bytes:
        blocks.append(Image(data=screenshot_bytes, format="png"))
    return blocks


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
