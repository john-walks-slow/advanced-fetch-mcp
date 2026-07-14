from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from typing import Annotated, Dict, List, Union

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
from .fetch import _inject_auth_storage_cookies
from .settings import IGNORE_SSL_ERRORS, USER_AGENT, get_requests_proxies, logger
from .workflow import execute_advanced_fetch


mcp = FastMCP("AdvancedFetchMCP")


async def _execute_multi_url(
    ctx: Context,
    request: AdvancedFetchParams,
) -> List[Union[TextContent, ImageContent]]:
    """Fetch multiple URLs in parallel and aggregate results."""
    urls: List[str] = request.url  # type: ignore[assignment]
    _t0 = time.monotonic()

    async def _run_single(single_url: str) -> Dict:
        single_request = request.model_copy(
            update={"url": single_url, "output_to_file": None}
        )
        try:
            result_dict, screenshot_bytes = await execute_advanced_fetch(
                ctx=ctx, request=single_request
            )
            if screenshot_bytes:
                result_dict["screenshot"] = base64.b64encode(screenshot_bytes).decode(
                    "utf-8"
                )
            result_dict["url"] = single_url
            return result_dict
        except Exception as exc:
            logger.warning("[MultiURL] URL %s 失败: %s", single_url, exc)
            return {
                "success": False,
                "url": single_url,
                "error": str(exc),
            }

    raw_results = await asyncio.gather(
        *[_run_single(u) for u in urls], return_exceptions=True
    )

    results: List[Dict] = []
    for idx, item in enumerate(raw_results):
        if isinstance(item, BaseException):
            results.append({"success": False, "url": urls[idx], "error": str(item)})
        else:
            results.append(item)

    succeeded = sum(1 for r in results if r.get("success"))
    failed = len(results) - succeeded

    result_dict: Dict = {
        "success": True,
        "results": results,
        "results_total": len(results),
        "results_succeeded": succeeded,
        "results_failed": failed,
        "duration_seconds": time.monotonic() - _t0,
    }

    # output_to_file at aggregate level
    if request.output_to_file:
        output_path = request.output_to_file
        dir_path = os.path.dirname(output_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)
        result_dict = {
            "success": True,
            "output_to_file": output_path,
            "duration_seconds": result_dict["duration_seconds"],
        }

    # Collect screenshots as Image blocks
    screenshots_b64: List[str] = []
    for r in results:
        ss = r.pop("screenshot", None)
        if ss:
            screenshots_b64.append(ss)

    blocks: List[Union[TextContent, ImageContent]] = [
        TextContent(
            type="text", text=json.dumps(result_dict, ensure_ascii=False, indent=2)
        )
    ]
    for ss_b64 in screenshots_b64:
        blocks.append(Image(data=base64.b64decode(ss_b64), format="png"))

    return blocks


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

    # Multi-URL: parallel batch processing
    if isinstance(request.url, list):
        return await _execute_multi_url(ctx=ctx, request=request)

    # Single URL path (unchanged)
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
    "读取网页内容。支持需要鉴权的网站和动态网站。",
    "Read web page content. Supports authenticated sites and dynamic websites.",
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
            with requests.Session() as session:
                session.trust_env = False
                session.headers["User-Agent"] = USER_AGENT
                _inject_auth_storage_cookies(session)
                resp = session.get(
                    img_url,
                    timeout=timeout,
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
        with requests.Session() as session:
            session.trust_env = False
            session.headers["User-Agent"] = USER_AGENT
            _inject_auth_storage_cookies(session)
            resp = session.get(
                url,
                timeout=timeout,
                proxies=get_requests_proxies(url),
                verify=not IGNORE_SSL_ERRORS,
                stream=True,
            )
            resp.raise_for_status()

            file_size = 0
            content_type = resp.headers.get("content-type", "")
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
                    "content_type": content_type,
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
            except OSError:
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
