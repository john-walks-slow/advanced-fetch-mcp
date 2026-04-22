from __future__ import annotations

import os
import shutil
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Literal, Optional

from playwright.async_api import Browser, BrowserContext, Playwright, async_playwright

from .settings import (
    AUTH_STORAGE_STATE_PATH,
    BROWSER_CHANNEL,
    BROWSER_COLOR_SCHEME,
    BROWSER_LOCALE,
    BROWSER_PROFILE_DIR,
    BROWSER_SESSION_MODE,
    BROWSER_TIMEZONE_ID,
    BROWSER_VIEWPORT_HEIGHT,
    BROWSER_VIEWPORT_WIDTH,
    USER_AGENT,
    IGNORE_SSL_ERRORS,
    get_no_proxy,
    get_proxy_url,
    logger,
)
from .stealth import apply_auth_stealth

SessionMode = Literal["auth", "profile"]


def _proxy_settings():
    proxy_url = get_proxy_url()
    if not proxy_url:
        return None

    no_proxy = get_no_proxy()
    return {"server": proxy_url, "bypass": no_proxy} if no_proxy else {"server": proxy_url}


def _channel_name() -> Optional[str]:
    channel = (BROWSER_CHANNEL or "").strip()
    return channel or None


def _accept_language_header() -> Optional[str]:
    if not BROWSER_LOCALE:
        return None

    locale = BROWSER_LOCALE.replace("_", "-")
    base = locale.split("-", 1)[0]
    ordered = [locale]
    if base and base not in ordered:
        ordered.append(base)
    if "en-US" not in ordered:
        ordered.append("en-US")
    if "en" not in ordered:
        ordered.append("en")

    weighted = []
    for idx, item in enumerate(ordered):
        if idx == 0:
            weighted.append(item)
        else:
            weight = max(0.1, 1.0 - idx * 0.1)
            weighted.append(f"{item};q={weight:.1f}")
    return ",".join(weighted)


def _base_context_kwargs() -> dict:
    kwargs = {
        "color_scheme": BROWSER_COLOR_SCHEME,
        "viewport": {
            "width": BROWSER_VIEWPORT_WIDTH,
            "height": BROWSER_VIEWPORT_HEIGHT,
        },
        "device_scale_factor": 1,
        "ignore_https_errors": IGNORE_SSL_ERRORS,
    }
    if USER_AGENT:
        kwargs["user_agent"] = USER_AGENT
    if BROWSER_LOCALE:
        kwargs["locale"] = BROWSER_LOCALE
    if BROWSER_TIMEZONE_ID:
        kwargs["timezone_id"] = BROWSER_TIMEZONE_ID

    accept_language = _accept_language_header()
    if accept_language:
        kwargs["extra_http_headers"] = {
            "Accept-Language": accept_language,
        }
    return kwargs


def _base_browser_kwargs(*, headless: bool, session_mode: SessionMode) -> dict:
    kwargs = {
        "headless": headless,
        "proxy": _proxy_settings(),
    }
    if session_mode == "auth":
        kwargs["args"] = [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
        ]
    channel = _channel_name()
    if channel:
        kwargs["channel"] = channel
    return kwargs


def _system_browser_candidates(channel: Optional[str]) -> list[Path]:
    if not channel:
        return []
    normalized = channel.lower()

    if normalized.startswith("chrome"):
        if sys.platform.startswith("win"):
            roots = [
                os.getenv("PROGRAMFILES"),
                os.getenv("PROGRAMFILES(X86)"),
                os.getenv("LOCALAPPDATA"),
            ]
            return [
                Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe"
                for root in roots
                if root
            ]
        if sys.platform == "darwin":
            return [Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")]
        return [
            Path(path)
            for path in filter(
                None,
                [
                    shutil.which("google-chrome"),
                    shutil.which("google-chrome-stable"),
                    shutil.which("chrome"),
                    shutil.which("chromium-browser"),
                ],
            )
        ]

    if normalized.startswith("msedge"):
        if sys.platform.startswith("win"):
            roots = [
                os.getenv("PROGRAMFILES"),
                os.getenv("PROGRAMFILES(X86)"),
                os.getenv("LOCALAPPDATA"),
            ]
            return [
                Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
                for root in roots
                if root
            ]
        if sys.platform == "darwin":
            return [Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")]
        return [
            Path(path)
            for path in filter(
                None,
                [shutil.which("microsoft-edge"), shutil.which("microsoft-edge-stable")],
            )
        ]

    return []


def _launch_variants(*, headless: bool, session_mode: SessionMode) -> list[dict]:
    primary = _base_browser_kwargs(headless=headless, session_mode=session_mode)
    variants = [primary]

    channel = primary.get("channel")
    for executable in _system_browser_candidates(channel):
        if not executable.exists():
            continue
        fallback = dict(primary)
        fallback.pop("channel", None)
        fallback["executable_path"] = str(executable)
        variants.append(fallback)
        break

    return variants


async def _launch_browser_with_fallback(pw: Playwright, *, headless: bool, session_mode: SessionMode) -> Browser:
    launch_errors: list[Exception] = []

    for index, kwargs in enumerate(_launch_variants(headless=headless, session_mode=session_mode), start=1):
        try:
            browser = await pw.chromium.launch(**kwargs)
            if "executable_path" in kwargs:
                logger.info("[Browser] 已通过系统浏览器可执行文件启动: %s", kwargs["executable_path"])
            elif kwargs.get("channel"):
                logger.info("[Browser] 已通过 channel 启动浏览器: %s", kwargs["channel"])
            return browser
        except Exception as exc:
            launch_errors.append(exc)
            logger.warning("[Browser] 启动浏览器失败(尝试 %s): %s", index, exc)

    raise launch_errors[-1]


async def _launch_persistent_context_with_fallback(pw: Playwright, *, user_data_dir: str, headless: bool) -> BrowserContext:
    launch_errors: list[Exception] = []
    for index, kwargs in enumerate(_launch_variants(headless=headless, session_mode="profile"), start=1):
        persistent_kwargs = {"user_data_dir": user_data_dir, **kwargs, **_base_context_kwargs()}
        try:
            context = await pw.chromium.launch_persistent_context(**persistent_kwargs)
            if "executable_path" in persistent_kwargs:
                logger.info(
                    "[Browser] 已通过系统浏览器可执行文件启动 persistent profile: %s",
                    persistent_kwargs["executable_path"],
                )
            elif persistent_kwargs.get("channel"):
                logger.info(
                    "[Browser] 已通过 channel 启动 persistent profile: %s",
                    persistent_kwargs["channel"],
                )
            return context
        except Exception as exc:
            launch_errors.append(exc)
            logger.warning("[Browser] 启动 persistent profile 失败(尝试 %s): %s", index, exc)

    raise launch_errors[-1]


@dataclass(slots=True)
class BrowserManager:
    _shared_playwright: Optional[Playwright] = None
    _shared_profile_contexts: dict[tuple[str, str], BrowserContext] = field(default_factory=dict)

    async def _ensure_shared_playwright(self) -> Playwright:
        if self._shared_playwright is None:
            self._shared_playwright = await async_playwright().start()
        return self._shared_playwright

    async def _launch_browser(self, *, headless: bool) -> tuple[Playwright, Browser]:
        pw = await async_playwright().start()
        browser = await _launch_browser_with_fallback(pw, headless=headless, session_mode="auth")
        return pw, browser

    @asynccontextmanager
    async def _profile_headless_session(self, profile_dir: Path) -> AsyncIterator[BrowserContext]:
        key = ((_channel_name() or ""), str(profile_dir.resolve()))
        context = self._shared_profile_contexts.get(key)
        if context is None:
            pw = await self._ensure_shared_playwright()
            context = await _launch_persistent_context_with_fallback(
                pw,
                user_data_dir=str(profile_dir),
                headless=True,
            )
            self._shared_profile_contexts[key] = context
            logger.info("[Browser] 已启动共享 persistent profile: %s", profile_dir)
        yield context

    @asynccontextmanager
    async def _profile_headful_session(self, profile_dir: Path) -> AsyncIterator[BrowserContext]:
        pw = await async_playwright().start()
        context: Optional[BrowserContext] = None
        try:
            context = await _launch_persistent_context_with_fallback(
                pw,
                user_data_dir=str(profile_dir),
                headless=False,
            )
            logger.info("[Browser] 已启动临时 headful profile: %s", profile_dir)
            yield context
        finally:
            if context is not None:
                try:
                    await context.close()
                except Exception as exc:
                    logger.warning("[Browser] 关闭临时 profile context 出错: %s", exc)
            try:
                await pw.stop()
            except Exception as exc:
                logger.warning("[Browser] 停止临时 Playwright 出错: %s", exc)

    @asynccontextmanager
    async def _auth_session(self, *, headless: bool) -> AsyncIterator[BrowserContext]:
        pw, browser = await self._launch_browser(headless=headless)
        context: Optional[BrowserContext] = None
        try:
            context_kwargs = _base_context_kwargs()
            if AUTH_STORAGE_STATE_PATH.exists():
                context_kwargs["storage_state"] = str(AUTH_STORAGE_STATE_PATH)

            context = await browser.new_context(**context_kwargs)
            await apply_auth_stealth(context)
            yield context
        finally:
            if context is not None:
                try:
                    AUTH_STORAGE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
                    await context.storage_state(path=str(AUTH_STORAGE_STATE_PATH))
                    logger.info("[Browser] 已保存 auth storage_state: %s", AUTH_STORAGE_STATE_PATH)
                except Exception as exc:
                    logger.warning("[Browser] 持久化 auth storage_state 出错: %s", exc)

                try:
                    await context.close()
                except Exception as exc:
                    logger.warning("[Browser] 关闭 context 出错: %s", exc)

            try:
                await browser.close()
            except Exception as exc:
                logger.warning("[Browser] 关闭 browser 出错: %s", exc)

            try:
                await pw.stop()
            except Exception as exc:
                logger.warning("[Browser] 停止 Playwright 出错: %s", exc)

    @asynccontextmanager
    async def open_session(self, *, headless: bool) -> AsyncIterator[BrowserContext]:
        session_mode: SessionMode = BROWSER_SESSION_MODE
        if session_mode not in {"auth", "profile"}:
            raise RuntimeError(f"不支持的 session_mode: {session_mode}")

        if session_mode == "profile":
            profile_dir = Path(BROWSER_PROFILE_DIR).expanduser()
            profile_dir.mkdir(parents=True, exist_ok=True)

            if headless:
                async with self._profile_headless_session(profile_dir) as ctx:
                    yield ctx
            else:
                async with self._profile_headful_session(profile_dir) as ctx:
                    yield ctx
            return

        async with self._auth_session(headless=headless) as ctx:
            yield ctx

    async def close(self):
        for key, context in list(self._shared_profile_contexts.items()):
            try:
                await context.close()
            except Exception as exc:
                logger.warning("[Browser] 关闭共享 persistent context 出错(%s): %s", key, exc)
        self._shared_profile_contexts.clear()

        if self._shared_playwright is not None:
            try:
                await self._shared_playwright.stop()
            except Exception as exc:
                logger.warning("[Browser] 停止共享 Playwright 出错: %s", exc)
            self._shared_playwright = None


browser_manager = BrowserManager()
