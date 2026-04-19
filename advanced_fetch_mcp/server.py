from __future__ import annotations

import asyncio
from typing import Annotated, Any, Dict, Optional

from dotenv import load_dotenv
from fastmcp import Context, FastMCP
from pydantic import Field

from .browser import browser_manager
from .dsl import AdvancedFetchParams, FindInPageOptions
from .settings import ENV_FILE
from .workflow import execute_advanced_fetch

load_dotenv(ENV_FILE)

mcp = FastMCP("AdvancedFetchMCP")


def _build_request_payload(
    *,
    mode: str,
    wait_for: float,
    require_user_intervention: bool,
    markdownify: bool,
    scope: str,
    selector: Optional[str],
    strip: Optional[list[str]],
    keep_media: bool,
    prompt: Optional[str],
    find_in_page: Optional[FindInPageOptions],
    evaluateJS: Optional[str],
    max_length: int,
    refresh_cache: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "mode": mode,
        "wait_for": wait_for,
        "require_user_intervention": require_user_intervention,
        "max_length": max_length,
        "refresh_cache": refresh_cache,
    }
    if evaluateJS is not None:
        payload["evaluateJS"] = evaluateJS
        return payload

    payload.update(
        {
            "markdownify": markdownify,
            "scope": scope,
            "selector": selector,
            "strip": strip or [],
            "keep_media": keep_media,
            "prompt": prompt,
            "find_in_page": find_in_page,
        }
    )
    return payload


@mcp.tool()
async def advanced_fetch(
    url: Annotated[str, Field(description="目标网址。")],
    ctx: Context,
    mode: Annotated[str, Field(description="页面抓取方式。可选 dynamic 或 static。")] = "dynamic",
    wait_for: Annotated[float, Field(description="仅在 dynamic 模式下生效。页面导航完成后额外等待的秒数。")] = 0,
    require_user_intervention: Annotated[bool, Field(description="是否要求人工在浏览器里完成登录、验证或其他页面交互后再继续抓取。")] = False,
    markdownify: Annotated[bool, Field(description="是否把选中的页面范围转换成 Markdown 文本；false 时返回原始 HTML。")] = True,
    scope: Annotated[str, Field(description="基础范围。可选 full、body、content。")] = "content",
    selector: Annotated[Optional[str], Field(description="在基础范围内，再用 CSS selector 选出一个更小的子区域。")] = None,
    strip: Annotated[Optional[list[str]], Field(description="在当前范围内，按这些 CSS selector 删除节点。")] = None,
    keep_media: Annotated[bool, Field(description="是否保留图片、视频、音频、SVG 等媒体节点。")] = False,
    prompt: Annotated[Optional[str], Field(description="提取提示词。提供后，会先得到当前视图文本，再把这段文本交给模型整理。")] = None,
    find_in_page: Annotated[Optional[FindInPageOptions], Field(description="在当前提取文本里搜索，或按游标跳到指定位置。")] = None,
    evaluateJS: Annotated[Optional[str], Field(description="在真实页面上下文中执行 JavaScript，并返回脚本结果。")] = None,
    max_length: Annotated[int, Field(description="文本结果长度上限。普通提取、prompt 和 evaluateJS 会按这个长度截断；搜索模式下它表示结果窗口大小。")] = 20000,
    refresh_cache: Annotated[bool, Field(description="是否忽略当前 URL 的已有缓存并重新抓取；重新抓到的结果仍会写回缓存。evaluateJS 模式忽略缓存。")] = False,
) -> Dict[str, Any]:
    request_payload = _build_request_payload(
        mode=mode,
        wait_for=wait_for,
        require_user_intervention=require_user_intervention,
        markdownify=markdownify,
        scope=scope,
        selector=selector,
        strip=strip,
        keep_media=keep_media,
        prompt=prompt,
        find_in_page=find_in_page,
        evaluateJS=evaluateJS,
        max_length=max_length,
        refresh_cache=refresh_cache,
    )
    request = AdvancedFetchParams(**request_payload)
    return await execute_advanced_fetch(url=url, ctx=ctx, request=request)


def cleanup():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        loop.create_task(browser_manager.close())
    else:
        asyncio.run(browser_manager.close())
