from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any, Literal, Optional, Tuple

import requests
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from .browser import browser_manager
from .detection import build_intervention_script, wait_for_intervention_end
from .params import FetchMode, WaitForValue
from .extract import render_auto_wait_text
from .settings import (
    AUTO_WAIT_TIMEOUT_SECONDS,
    NAVIGATION_TIMEOUT_SECONDS,
    NETWORK_IDLE_TIMEOUT_SECONDS,
    STATIC_FETCH_TIMEOUT_SECONDS,
    USER_AGENT,
    IGNORE_SSL_ERRORS,
    get_requests_proxies,
    seconds_to_ms,
    logger,
)

TimeoutStage = Literal["goto", "networkidle", "static_request"]

_AUTO_WAIT_POLL_INTERVAL_SECONDS = 0.25
_AUTO_WAIT_STABLE_ROUNDS = 2
_AUTO_WAIT_SAMPLE_EDGE_CHARS = 200


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
        with requests.Session() as session:
            session.trust_env = False
            if USER_AGENT:
                session.headers["User-Agent"] = USER_AGENT

            response = session.get(
                url,
                timeout=effective_timeout,
                proxies=get_requests_proxies(url),
                verify=not IGNORE_SSL_ERRORS,
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


async def _sample_page_extracted_text(page: Page) -> str:
    html, _ = await _capture_current_page(page)
    return await asyncio.to_thread(render_auto_wait_text, html)


def _is_extracted_text_stable(current: str, previous: str) -> bool:
    current_text = current.strip()
    previous_text = previous.strip()
    if not current_text or not previous_text:
        return False
    if current_text == previous_text:
        return True

    previous_length = max(1, len(previous_text))
    length_delta = abs(len(current_text) - len(previous_text))
    if length_delta > max(48, int(previous_length * 0.03)):
        return False

    edge = _AUTO_WAIT_SAMPLE_EDGE_CHARS
    return (
        current_text[:edge] == previous_text[:edge]
        and current_text[-edge:] == previous_text[-edge:]
    )


async def _auto_wait_for_content(page: Page) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + AUTO_WAIT_TIMEOUT_SECONDS
    previous_extracted_text: Optional[str] = None
    stable_rounds = 0

    while True:
        current_extracted_text = await _sample_page_extracted_text(page)

        if previous_extracted_text is not None:
            stable_rounds = (
                stable_rounds + 1
                if _is_extracted_text_stable(current_extracted_text, previous_extracted_text)
                else 0
            )

        if stable_rounds >= _AUTO_WAIT_STABLE_ROUNDS:
            logger.info("[DynamicFetch] auto wait 结束：抽取结果已趋于稳定")
            return

        if loop.time() >= deadline:
            logger.info("[DynamicFetch] auto wait 到达超时上限，返回当前页面")
            return

        previous_extracted_text = current_extracted_text
        await asyncio.sleep(_AUTO_WAIT_POLL_INTERVAL_SECONDS)


async def _apply_post_load_wait(page: Page, wait_for: WaitForValue) -> None:
    if wait_for == "auto":
        await _auto_wait_for_content(page)
        return
    if wait_for > 0:
        await asyncio.sleep(wait_for)


async def dynamic_fetch(
    url: str,
    wait_for: WaitForValue = "auto",
    require_user_intervention: bool = False,
    timeout: Optional[float] = None,
) -> FetchResult:
    effective_timeout_ms = seconds_to_ms(
        timeout if timeout is not None else NAVIGATION_TIMEOUT_SECONDS
    )
    network_idle_timeout_ms = seconds_to_ms(
        timeout if timeout is not None else NETWORK_IDLE_TIMEOUT_SECONDS
    )

    page: Optional[Page] = None
    timed_out = False
    timeout_stage: Optional[TimeoutStage] = None
    intervention_ended_by: Optional[str] = None

    headless = not require_user_intervention

    async with browser_manager.open_session(
        headless=headless,
    ) as context:
        try:
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
                        "[DynamicFetch] 等待 networkidle 失败，立即抓取当前内容：%s",
                        exc,
                    )

                await _apply_post_load_wait(page, wait_for)

            if require_user_intervention:
                html, final_url, intervention_ended_by = (
                    await wait_for_intervention_end(page)
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
    wait_for: WaitForValue,
    require_user_intervention: bool,
    timeout: Optional[float] = None,
) -> FetchResult:
    if mode == "dynamic" or require_user_intervention:
        return await dynamic_fetch(
            url=url,
            wait_for=wait_for,
            require_user_intervention=require_user_intervention,
            timeout=timeout,
            )
    return static_fetch(url, timeout)


async def evaluate_script_on_page(
    *,
    url: str,
    wait_for: WaitForValue,
    require_user_intervention: bool,
    script: str,
    timeout: Optional[float] = None,
) -> Any:
    effective_timeout_ms = seconds_to_ms(
        timeout if timeout is not None else NAVIGATION_TIMEOUT_SECONDS
    )
    network_idle_timeout_ms = seconds_to_ms(
        timeout if timeout is not None else NETWORK_IDLE_TIMEOUT_SECONDS
    )

    page: Optional[Page] = None
    headless = not require_user_intervention

    async with browser_manager.open_session(
        headless=headless,
    ) as context:
        try:
            if require_user_intervention:
                await context.add_init_script(build_intervention_script())

            page = await context.new_page()
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=effective_timeout_ms,
            )

            try:
                await page.wait_for_load_state(
                    "networkidle",
                    timeout=network_idle_timeout_ms,
                )
            except Exception:
                pass

            await _apply_post_load_wait(page, wait_for)

            if require_user_intervention:
                await wait_for_intervention_end(page)

            return await page.evaluate(_build_page_evaluate_script(script))
        finally:
            if page and not page.is_closed():
                try:
                    await page.close()
                except Exception:
                    pass
