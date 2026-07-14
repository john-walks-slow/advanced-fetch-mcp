from __future__ import annotations

import asyncio
import os
import shutil
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Optional

from playwright.async_api import Browser, BrowserContext, Playwright, async_playwright

from .settings import (
    AUTH_STORAGE_STATE_PATH,
    BROWSER_CHANNEL,
    BROWSER_COLOR_SCHEME,
    BROWSER_LOCALE,
    BROWSER_TIMEZONE_ID,
    BROWSER_VIEWPORT_HEIGHT,
    BROWSER_VIEWPORT_WIDTH,
    ENABLE_DYNAMIC_PROXY,
    USER_AGENT,
    IGNORE_SSL_ERRORS,
    get_no_proxy,
    get_proxy_url,
    logger,
)
from .stealth import apply_auth_stealth


def _proxy_settings():
    if not ENABLE_DYNAMIC_PROXY:
        return None

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


def _base_browser_kwargs(*, headless: bool) -> dict:
    kwargs = {
        "headless": headless,
        "proxy": _proxy_settings(),
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
        ],
    }
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


def _launch_variants(*, headless: bool) -> list[dict]:
    primary = _base_browser_kwargs(headless=headless)
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


async def _launch_browser_with_fallback(pw: Playwright, *, headless: bool) -> Browser:
    launch_errors: list[Exception] = []

    for index, kwargs in enumerate(_launch_variants(headless=headless), start=1):
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


@dataclass(slots=True)
class BrowserManager:
    """管理 Playwright 浏览器实例的生命周期。

    核心策略：
    - Playwright 实例 + 一个 headless 浏览器在进程内长期复用（lazy init）
    - 每次请求创建一个独立的 BrowserContext（加载 storage_state 实现鉴权继承）
    - 请求结束后 Context 关闭，浏览器保持存活
    - Elicit 场景创建临时 headful 浏览器，操作完成后销毁
    """
    _pw: Optional[Playwright] = None
    _browser: Optional[Browser] = None
    _pw_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _browser_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _store_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def _ensure_playwright(self) -> Playwright:
        if self._pw is not None:
            return self._pw
        async with self._pw_lock:
            if self._pw is not None:
                return self._pw
            self._pw = await async_playwright().start()
            logger.info("[Browser] Playwright 已启动")
        return self._pw

    async def _ensure_browser_headless(self) -> Browser:
        """获取或创建长期复用的 headless 浏览器，带崩溃自动恢复。"""
        if self._browser is not None:
            try:
                if self._browser.is_connected():
                    return self._browser
                logger.warning("[Browser] 浏览器连接已断开，准备重建")
            except Exception:
                logger.warning("[Browser] 检测到浏览器不可用，准备重建")
            self._browser = None

        async with self._browser_lock:
            if self._browser is not None:
                return self._browser
            pw = await self._ensure_playwright()
            self._browser = await _launch_browser_with_fallback(pw, headless=True)
            logger.info("[Browser] 无头浏览器已就绪")
        return self._browser

    def _make_context_kwargs(self) -> dict:
        kwargs = _base_context_kwargs()
        if AUTH_STORAGE_STATE_PATH.exists():
            kwargs["storage_state"] = str(AUTH_STORAGE_STATE_PATH)
        return kwargs

    async def _save_storage_state_atomic(self, context: Optional[BrowserContext]) -> None:
        """原子写入 storage_state，避免并发写竞争。"""
        if context is None:
            return
        try:
            if context.is_closed():
                return
        except Exception:
            return
        async with self._store_lock:
            tmp = AUTH_STORAGE_STATE_PATH.with_suffix(".tmp")
            try:
                AUTH_STORAGE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
                await context.storage_state(path=str(tmp))
                os.replace(str(tmp), str(AUTH_STORAGE_STATE_PATH))
            except Exception as exc:
                logger.warning("[Browser] 持久化 storage_state 出错: %s", exc)
                try:
                    os.remove(str(tmp))
                except FileNotFoundError:
                    pass

    @asynccontextmanager
    async def open_session(self, *, apply_stealth: bool = True) -> AsyncIterator[BrowserContext]:
        """普通请求：从长期复用的 headless 浏览器创建上下文。

        请求结束后自动保存 storage_state 并关闭上下文。
        """
        browser = await self._ensure_browser_headless()
        context: Optional[BrowserContext] = None
        try:
            kwargs = self._make_context_kwargs()
            context = await browser.new_context(**kwargs)
            if apply_stealth:
                await apply_auth_stealth(context)
            yield context
        finally:
            if context is not None:
                await self._save_storage_state_atomic(context)
                try:
                    await context.close()
                except Exception as exc:
                    logger.warning("[Browser] 关闭 context 出错: %s", exc)

    @asynccontextmanager
    async def open_elicit_session(self) -> AsyncIterator[BrowserContext]:
        """Elicit 请求：创建临时 headful 浏览器+上下文。

        用户完成人机验证或登录后自动保存 storage_state，
        然后关闭上下文和浏览器（Playwright 实例保持存活）。
        """
        pw = await self._ensure_playwright()
        elicit_browser: Optional[Browser] = None
        context: Optional[BrowserContext] = None
        try:
            elicit_browser = await _launch_browser_with_fallback(pw, headless=False)
            kwargs = self._make_context_kwargs()
            context = await elicit_browser.new_context(**kwargs)
            yield context
        finally:
            if context is not None:
                await self._save_storage_state_atomic(context)
                try:
                    await context.close()
                except Exception as exc:
                    logger.warning("[Browser] 关闭 elicit context 出错: %s", exc)
            if elicit_browser is not None:
                try:
                    await elicit_browser.close()
                except Exception as exc:
                    logger.warning("[Browser] 关闭 elicit browser 出错: %s", exc)

    async def close(self):
        """关闭主浏览器并停止 Playwright。"""
        if self._browser is not None:
            try:
                await self._browser.close()
                logger.info("[Browser] 主浏览器已关闭")
            except Exception as exc:
                logger.warning("[Browser] 关闭主浏览器出错: %s", exc)
            self._browser = None
        if self._pw is not None:
            try:
                await self._pw.stop()
                logger.info("[Browser] Playwright 已停止")
            except Exception as exc:
                logger.warning("[Browser] 停止 Playwright 出错: %s", exc)
            self._pw = None


browser_manager = BrowserManager()
