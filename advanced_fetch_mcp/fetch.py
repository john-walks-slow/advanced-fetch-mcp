from __future__ import annotations

import asyncio
import random
import re
import time
from dataclasses import dataclass
from typing import Any, Literal, Optional, Tuple
from urllib.parse import urlparse

import requests
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from .browser import browser_manager
from .detection import build_intervention_script, wait_for_intervention_end
from .params import FetchMode
from .extract import render_auto_wait_text
from .settings import (
    FETCH_TIMEOUT_SECONDS,
    PER_SITE_RATE_LIMIT_SECONDS,
    USER_AGENT,
    IGNORE_SSL_ERRORS,
    get_requests_proxies,
    logger,
    AUTO_WAIT_POLL_INTERVAL_SECONDS,
    AUTO_WAIT_MIN_STABLE_SECONDS,
    AUTO_WAIT_SAMPLE_EDGE_CHARS,
)

TimeoutStage = Literal["goto", "static_request"]


@dataclass(slots=True)
class FetchResult:
    html: str
    final_url: str
    timed_out: bool = False
    timeout_stage: Optional[TimeoutStage] = None
    intervention_ended_by: Optional[str] = None


@dataclass(slots=True)
class EvalResult:
    value: Any
    fetch_result: FetchResult


class EvalInterventionClosedError(RuntimeError):
    pass


_FETCH_CACHE: dict[tuple[str, FetchMode], Tuple[float, str, str]] = {}
_FETCH_CACHE_MAX_SIZE = 100
_FETCH_CACHE_TTL_SECONDS = 300.0
_SITE_RATE_LIMIT_NEXT_ALLOWED_AT: dict[str, float] = {}
_SITE_RATE_LIMIT_LOCK = asyncio.Lock()
_SITE_RATE_LIMIT_MAX_JITTER_SECONDS = 0.15
_FUNCTION_LIKE_SCRIPT_RE = re.compile(
    r"^\s*(?:async\s+)?(?:function\b|\([^)]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)"
)


def _cache_key(url: str, mode: FetchMode) -> tuple[str, FetchMode]:
    return (url, mode)


def get_cached_fetch(url: str, mode: FetchMode) -> Optional[Tuple[str, str]]:
    entry = _FETCH_CACHE.get(_cache_key(url, mode))
    if entry is None:
        return None
    timestamp, final_url, html = entry
    if time.time() - timestamp > _FETCH_CACHE_TTL_SECONDS:
        del _FETCH_CACHE[_cache_key(url, mode)]
        return None
    return (final_url, html)


def store_cached_fetch(url: str, mode: FetchMode, final_url: str, html: str) -> None:
    if len(_FETCH_CACHE) >= _FETCH_CACHE_MAX_SIZE:
        oldest_key = min(_FETCH_CACHE.keys(), key=lambda k: _FETCH_CACHE[k][0])
        del _FETCH_CACHE[oldest_key]
    _FETCH_CACHE[_cache_key(url, mode)] = (time.time(), final_url, html)


async def _wait_for_site_rate_limit(url: str) -> None:
    if PER_SITE_RATE_LIMIT_SECONDS <= 0:
        return

    host = (urlparse(url).hostname or "").strip().lower()
    if not host:
        return

    while True:
        async with _SITE_RATE_LIMIT_LOCK:
            now = time.monotonic()
            next_allowed_at = _SITE_RATE_LIMIT_NEXT_ALLOWED_AT.get(host, 0.0)
            wait_seconds = next_allowed_at - now
            if wait_seconds <= 0:
                jitter_seconds = random.uniform(
                    0.0,
                    min(_SITE_RATE_LIMIT_MAX_JITTER_SECONDS, PER_SITE_RATE_LIMIT_SECONDS * 0.2),
                )
                _SITE_RATE_LIMIT_NEXT_ALLOWED_AT[host] = (
                    now + PER_SITE_RATE_LIMIT_SECONDS + jitter_seconds
                )
                return
        await asyncio.sleep(wait_seconds)


def static_fetch(url: str, timeout: Optional[float] = None) -> FetchResult:
    effective_timeout = timeout if timeout is not None else FETCH_TIMEOUT_SECONDS

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
    except requests.RequestException as exc:
        logger.warning("[StaticFetch] 请求失败：%s", exc)
        return FetchResult(
            html="",
            final_url=url,
            timed_out=False,
            timeout_stage=None,
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

    edge = AUTO_WAIT_SAMPLE_EDGE_CHARS
    return (
        current_text[:edge] == previous_text[:edge]
        and current_text[-edge:] == previous_text[-edge:]
    )


async def _wait_for_content_stable(
    page: Page,
    deadline: float,
    min_stable_seconds: Optional[float] = None,
    early_exit_min_length: Optional[int] = None,
) -> None:
    effective_min_stable = min_stable_seconds if min_stable_seconds is not None else AUTO_WAIT_MIN_STABLE_SECONDS
    previous_extracted_text: Optional[str] = None
    previous_url: Optional[str] = None
    stable_since: Optional[float] = None

    while True:
        current_extracted_text = await _sample_page_extracted_text(page)
        try:
            current_url = page.url
        except Exception:
            current_url = None

        now = time.monotonic()

        if previous_url is not None and current_url != previous_url:
            logger.info("[DynamicFetch] 检测到页面跳转: %s -> %s", previous_url, current_url)
            stable_since = None
            previous_extracted_text = None
        elif previous_extracted_text is not None:
            current_stripped = current_extracted_text.strip()
            previous_stripped = previous_extracted_text.strip()
            
            is_stable = (
                current_stripped == previous_stripped
                or _is_extracted_text_stable(current_extracted_text, previous_extracted_text)
            )
            
            if is_stable:
                if stable_since is None:
                    stable_since = now
                
                stable_duration = now - stable_since
                if stable_duration >= effective_min_stable:
                    if early_exit_min_length is not None and len(current_stripped) < early_exit_min_length:
                        pass
                    else:
                        if early_exit_min_length is not None:
                            logger.info("[DynamicFetch] 内容长度达标且稳定 (len=%d)", len(current_stripped))
                        else:
                            logger.info("[DynamicFetch] 正文已稳定")
                        return
            else:
                stable_since = None

        if now >= deadline:
            logger.info("[DynamicFetch] 总超时，返回当前页面")
            return

        previous_extracted_text = current_extracted_text
        previous_url = current_url
        await asyncio.sleep(AUTO_WAIT_POLL_INTERVAL_SECONDS)


async def dynamic_fetch(
    url: str,
    require_user_intervention: bool = False,
    min_stable_seconds: Optional[float] = None,
    early_exit_min_length: Optional[int] = None,
    timeout: Optional[float] = None,
) -> FetchResult:
    total_timeout = timeout if timeout is not None else FETCH_TIMEOUT_SECONDS
    deadline = time.monotonic() + total_timeout

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
            remaining = deadline - time.monotonic()
            goto_timeout_ms = max(1000, int(remaining * 0.4 * 1000))
            try:
                await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=goto_timeout_ms,
                )
                goto_completed = True
            except PlaywrightTimeoutError:
                timed_out = True
                timeout_stage = "goto"
                logger.warning("[DynamicFetch] goto 超时，立即抓取当前内容")
            except Exception as exc:
                logger.warning("[DynamicFetch] goto 失败，立即抓取当前内容：%s", exc)

            if goto_completed:
                await _wait_for_content_stable(page, deadline, min_stable_seconds, early_exit_min_length)

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
    require_user_intervention: bool,
    min_stable_seconds: Optional[float] = None,
    early_exit_min_length: Optional[int] = None,
    timeout: Optional[float] = None,
) -> FetchResult:
    await _wait_for_site_rate_limit(url)
    if mode == "dynamic" or require_user_intervention:
        return await dynamic_fetch(
            url=url,
            require_user_intervention=require_user_intervention,
            min_stable_seconds=min_stable_seconds,
            early_exit_min_length=early_exit_min_length,
            timeout=timeout,
        )
    return static_fetch(url, timeout)


async def evaluate_script_on_page(
    *,
    url: str,
    require_user_intervention: bool,
    min_stable_seconds: Optional[float] = None,
    script: str,
    timeout: Optional[float] = None,
) -> EvalResult:
    total_timeout = timeout if timeout is not None else FETCH_TIMEOUT_SECONDS
    deadline = time.monotonic() + total_timeout

    page: Optional[Page] = None
    headless = not require_user_intervention
    timed_out = False
    timeout_stage: Optional[TimeoutStage] = None
    intervention_ended_by: Optional[str] = None

    await _wait_for_site_rate_limit(url)

    async with browser_manager.open_session(
        headless=headless,
    ) as context:
        try:
            if require_user_intervention:
                await context.add_init_script(build_intervention_script())

            page = await context.new_page()

            goto_completed = False
            remaining = deadline - time.monotonic()
            goto_timeout_ms = max(1000, int(remaining * 0.4 * 1000))
            try:
                await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=goto_timeout_ms,
                )
                goto_completed = True
            except PlaywrightTimeoutError:
                timed_out = True
                timeout_stage = "goto"
                logger.warning("[EvalScript] goto 超时，尝试在当前页面执行脚本")
            except Exception as exc:
                logger.warning("[EvalScript] goto 失败：%s", exc)

            if goto_completed:
                await _wait_for_content_stable(page, deadline, min_stable_seconds, None)

            if require_user_intervention:
                _, _, intervention_ended_by = await wait_for_intervention_end(page)
                if intervention_ended_by == "page_closed":
                    raise EvalInterventionClosedError(
                        "浏览器页面已关闭，无法继续执行 eval 脚本。"
                    )

            value = await page.evaluate(_build_page_evaluate_script(script))
            _, final_url = await _capture_current_page(page)
            return EvalResult(
                value=value,
                fetch_result=FetchResult(
                    html="",
                    final_url=final_url,
                    timed_out=timed_out,
                    timeout_stage=timeout_stage,
                    intervention_ended_by=intervention_ended_by,
                ),
            )
        finally:
            if page and not page.is_closed():
                try:
                    await page.close()
                except Exception:
                    pass



