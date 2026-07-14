from __future__ import annotations

import asyncio
import json
import os
from typing import Annotated, List, Union

import requests
from fastmcp import Context, FastMCP
from fastmcp.utilities.types import Image
from mcp.types import ImageContent, TextContent
from pydantic import Field

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
from .settings import IGNORE_SSL_ERRORS, USER_AGENT, get_requests_proxies
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
        result_dict = {
            "success": True,
            "output_to_file": output_path,
            "duration_seconds": result_dict.get("duration_seconds"),
        }

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


def _infer_image_format(content_type: str) -> str:
    """Infer MCP-compatible image format from HTTP Content-Type header."""
    ct = content_type.lower()
    if "jpeg" in ct or "jpg" in ct:
        return "jpeg"
    if "gif" in ct:
        return "gif"
    if "webp" in ct:
        return "webp"
    if "png" in ct:
        return "png"
    if "svg" in ct:
        return "svg+xml"
    return "png"


ReadImageTimeoutParam = Annotated[
    float,
    Field(
        default=30.0,
        ge=1.0,
        description=schema_text(
            "获取图片的超时秒数。",
            "Timeout in seconds for fetching images.",
        ),
    ),
]

ReadImageUrlParam = Annotated[
    Union[str, List[str]],
    Field(
        description=schema_text(
            "图片 URL，可以传入单个 URL 或 URL 列表。",
            "Image URL, or a list of image URLs.",
        )
    ),
]


@mcp.tool()
async def read_image(
    ctx: Context,
    url: ReadImageUrlParam,
    timeout: ReadImageTimeoutParam = 30.0,
) -> List[Union[TextContent, ImageContent]]:
    """获取并显示一张或多张图片。

    传入图片 URL 即可获取并以图片形式展示结果。
    """
    urls = [url] if isinstance(url, str) else url
    results: List[Union[TextContent, ImageContent]] = []

    if not urls:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"success": False, "error": "No URLs provided."},
                    ensure_ascii=False,
                ),
            )
        ]

    for img_url in urls:
        try:
            resp = requests.get(
                img_url,
                timeout=timeout,
                headers={"User-Agent": USER_AGENT},
                proxies=get_requests_proxies(img_url),
                verify=not IGNORE_SSL_ERRORS,
            )
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "image/png")
            fmt = _infer_image_format(content_type)
            results.append(Image(data=resp.content, format=fmt))
        except Exception as e:
            results.append(
                TextContent(
                    type="text",
                    text=f"Failed to fetch image {img_url}: {e}",
                )
            )

    return results


DownloadOverwriteParam = Annotated[
    bool,
    Field(
        default=False,
        description=schema_text(
            "若为 false（默认）且文件已存在则报错；设为 true 则覆盖已有文件。",
            "If false (default) and the file already exists, return an error. Set to true to overwrite.",
        ),
    ),
]


@mcp.tool()
async def download(
    ctx: Context,
    url: str = Field(description=schema_text("下载源 URL。", "Source URL to download from.")),
    file_path: str = Field(description=schema_text("本地保存路径。", "Local file path to save to.")),
    overwrite: DownloadOverwriteParam = False,
    timeout: float = Field(
        default=120.0,
        ge=1.0,
        description=schema_text("下载超时秒数。", "Download timeout in seconds."),
    ),
) -> TextContent:
    """从 URL 下载文件到本地路径。

    支持流式下载大文件，自动创建父目录。
    """
    # Resolve to absolute path to mitigate path traversal
    abs_path = os.path.abspath(file_path)

    if not overwrite and os.path.exists(abs_path):
        return TextContent(
            type="text",
            text=json.dumps(
                {
                    "success": False,
                    "error": f"File already exists: {abs_path}. Set overwrite=true to overwrite.",
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

    dir_path = os.path.dirname(abs_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            proxies=get_requests_proxies(url),
            verify=not IGNORE_SSL_ERRORS,
            stream=True,
        )
        resp.raise_for_status()

        file_size = 0
        with open(abs_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    file_size += len(chunk)

        return TextContent(
            type="text",
            text=json.dumps(
                {
                    "success": True,
                    "file_path": abs_path,
                    "size": file_size,
                    "content_type": resp.headers.get("content-type", ""),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        # Clean up partial file on failure
        if os.path.exists(abs_path):
            try:
                os.remove(abs_path)
            except Exception:
                pass
        return TextContent(
            type="text",
            text=json.dumps(
                {"success": False, "error": str(e)},
                ensure_ascii=False,
                indent=2,
            ),
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
