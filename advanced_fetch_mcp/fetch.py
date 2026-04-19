from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Literal, Optional, Tuple, Any

import requests
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from .browser import browser_manager
from .detection import build_intervention_script, wait_for_intervention_end
from .params import FetchMode
from .settings import (
    DEFAULT_TIMEOUT_SECONDS,
    NAVIGATION_TIMEOUT_MS,
    NETWORK_IDLE_TIMEOUT_MS,
    STATIC_FETCH_TIMEOUT_SECONDS,
    USER_AGENT,
    logger,
)

TimeoutStage = Literal["goto", "networkidle", "static_request"]


@dataclass(slots=True)
class FetchResult:
    html: str
    final_url: str
    timed_out: bool = False
    timeout_stage: Optional[TimeoutStage] = None
    intervention_ended_by: Optional[str] = None


_FETCH_CACHE: dict[tuple[str, FetchMode], Tuple[str, str]] = {}
_FUNCTION_LIKE_SCRIPT_RE = re.compile(
    r"^\s*(?:async\s+)?(?:function\b|\([^)]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)"
)


def _cache_key(url: str, mode: FetchMode) -> tuple[str, FetchMode]:
    return (url, mode)


def get_cached_fetch(url: str, mode: FetchMode) -> Optional[Tuple[str, str]]:
    return _FETCH_CACHE.get(_cache_key(url, mode))


def store_cached_fetch(url: str, mode: FetchMode, final_url: str, html: str) -> None:
    _FETCH_CACHE[_cache_key(url, mode)] = (final_url, html)


def static_fetch(url: str, timeout: Optional[float] = None) -> FetchResult:
    effective_timeout = timeout if timeout is not None else STATIC_FETCH_TIMEOUT_SECONDS
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=effective_timeout,
        )
        response.raise_for_status()
        return FetchResult(html=response.text, final_url=response.url)
    except requests.Timeout:
        logger.warning(
            "[StaticFetch] 请求超时，返回空内容并标记 timeout_stage=static_request"
        )
        return FetchResult(
            html="",
            final_url=url,
            timed_out=True,
            timeout_stage="static_request",
        )


def _build_page_evaluate_script(script: str) -> str:
    stripped = script.strip()
    if _FUNCTION_LIKE_SCRIPT_RE.match(stripped):
        return stripped
    if "return" in stripped or "\n" in stripped or ";" in stripped:
        return f"() => {{\n{script}\n}}"
    return f"() => (\n{script}\n)"


async def _capture_current_page(page: Page) -> Tuple[str, str]:
    try:
        html = await page.content()
    except Exception:
        html = ""
    try:
        final_url = page.url
    except Exception:
        final_url = ""
    return html, final_url


async def dynamic_fetch(
    url: str,
    wait_for: float = 0,
    require_user_intervention: bool = False,
    timeout: Optional[float] = None,
) -> FetchResult:
    effective_timeout_ms = (
        int(timeout * 1000) if timeout is not None else NAVIGATION_TIMEOUT_MS
    )
    network_idle_timeout_ms = (
        int(timeout * 1000) if timeout is not None else NETWORK_IDLE_TIMEOUT_MS
    )
    context = None
    page: Optional[Page] = None
    timed_out = False
    timeout_stage: Optional[TimeoutStage] = None
    intervention_ended_by: Optional[str] = None

    try:
        headless = False if require_user_intervention else True
        context = await browser_manager.get_context(headless=headless)

        if require_user_intervention:
            await context.add_init_script(build_intervention_script())

        page = await context.new_page()

        goto_completed = False
        try:
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=effective_timeout_ms,
            )
            goto_completed = True
        except PlaywrightTimeoutError:
            timed_out = True
            timeout_stage = "goto"
            logger.warning("[DynamicFetch] goto 超时，立即抓取当前内容")
        except Exception as exc:
            logger.warning("[DynamicFetch] goto 失败，立即抓取当前内容：%s", exc)

        if goto_completed:
            if wait_for > 0:
                await asyncio.sleep(wait_for)
            try:
                await page.wait_for_load_state(
                    "networkidle",
                    timeout=network_idle_timeout_ms,
                )
            except PlaywrightTimeoutError:
                timed_out = True
                timeout_stage = "networkidle"
                logger.warning("[DynamicFetch] networkidle 超时，立即抓取当前内容")
            except Exception as exc:
                logger.warning(
                    "[DynamicFetch] 等待 networkidle 失败，立即抓取当前内容：%s", exc
                )

        if require_user_intervention:
            html, final_url, intervention_ended_by = await wait_for_intervention_end(
                page
            )
            if not html:
                html, final_url = await _capture_current_page(page)
        else:
            html, final_url = await _capture_current_page(page)

        return FetchResult(
            html=html,
            final_url=final_url,
            timed_out=timed_out,
            timeout_stage=timeout_stage,
            intervention_ended_by=intervention_ended_by,
        )
    finally:
        if page and not page.is_closed():
            try:
                await page.close()
            except Exception:
                pass


async def fetch_url(
    url: str,
    mode: FetchMode,
    wait_for: float,
    require_user_intervention: bool,
    timeout: Optional[float] = None,
) -> FetchResult:
    if mode == "dynamic" or require_user_intervention:
        return await dynamic_fetch(url, wait_for, require_user_intervention, timeout)
    return static_fetch(url, timeout)


async def evaluate_script_on_page(
    *,
    url: str,
    wait_for: float,
    require_user_intervention: bool,
    script: str,
    timeout: Optional[float] = None,
) -> Any:
    effective_timeout_ms = (
        int(timeout * 1000) if timeout is not None else NAVIGATION_TIMEOUT_MS
    )
    network_idle_timeout_ms = (
        int(timeout * 1000) if timeout is not None else NETWORK_IDLE_TIMEOUT_MS
    )
    page: Optional[Page] = None
    context = None

    try:
        headless = False if require_user_intervention else True
        context = await browser_manager.get_context(headless=headless)

        if require_user_intervention:
            await context.add_init_script(build_intervention_script())

        page = await context.new_page()
        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=effective_timeout_ms,
        )
        if wait_for > 0:
            await asyncio.sleep(wait_for)
        try:
            await page.wait_for_load_state(
                "networkidle",
                timeout=network_idle_timeout_ms,
            )
        except Exception:
            pass

        if require_user_intervention:
            await wait_for_intervention_end(page)

        return await page.evaluate(_build_page_evaluate_script(script))
    finally:
        if page and not page.is_closed():
            try:
                await page.close()
            except Exception:
                pass
