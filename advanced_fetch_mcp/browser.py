from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from playwright.async_api import BrowserContext, Playwright, async_playwright

from .settings import BROWSER_CHANNEL, BROWSER_PROFILE_DIR, BROWSER_PROFILE_TEMPLATE_DIR, USER_AGENT, env_flag, logger

_SUPPORTED_CHANNELS = {"chrome", "msedge"}
_PROFILE_IGNORE_NAMES = {
    "SingletonLock",
    "SingletonSocket",
    "SingletonCookie",
    "DevToolsActivePort",
    "lockfile",
}
_PROFILE_MIGRATION_NAMES = {
    "Cookies",
    "Network",
    "Local Storage",
    "Session Storage",
    "IndexedDB",
    "Service Worker",
    "Storage",
    "WebStorage",
    "Login Data",
    "Web Data",
    "Preferences",
    "Secure Preferences",
}


def _proxy_settings():
    proxy_url = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
    no_proxy = os.getenv("NO_PROXY") or os.getenv("no_proxy")
    if env_flag("BROWSER_USE_PROXY") and proxy_url:
        return {"server": proxy_url, "bypass": no_proxy}
    return None


def _validated_channel() -> str:
    channel = (BROWSER_CHANNEL or "chrome").strip().lower()
    if channel not in _SUPPORTED_CHANNELS:
        raise RuntimeError("BROWSER_CHANNEL 只支持 chrome 或 msedge。")
    return channel


def _copy_profile_tree_if_missing(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        if child.name in _PROFILE_IGNORE_NAMES:
            continue
        target = dst / child.name
        if child.is_dir():
            if not target.exists():
                shutil.copytree(child, target, ignore=shutil.ignore_patterns(*_PROFILE_IGNORE_NAMES))
            else:
                _copy_profile_tree_if_missing(child, target)
        else:
            if not target.exists():
                shutil.copy2(child, target)


def _copy_profile_template(src: Path, dst: Path) -> None:
    if not src.exists():
        raise RuntimeError(f"BROWSER_PROFILE_TEMPLATE_DIR 不存在: {src}")
    dst.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        if child.name in _PROFILE_IGNORE_NAMES:
            continue
        if child.name not in _PROFILE_MIGRATION_NAMES:
            continue
        target = dst / child.name
        if child.is_dir():
            if not target.exists():
                shutil.copytree(child, target, ignore=shutil.ignore_patterns(*_PROFILE_IGNORE_NAMES))
            else:
                _copy_profile_tree_if_missing(child, target)
        else:
            if not target.exists():
                shutil.copy2(child, target)


@dataclass
class BrowserManager:
    _persistent_playwright: Optional[Playwright] = None
    _persistent_context: Optional[BrowserContext] = None
    _persistent_headless: Optional[bool] = None

    async def get_context(self, *, headless: bool) -> BrowserContext:
        if self._persistent_context is not None and self._persistent_headless == headless:
            return self._persistent_context

        if self._persistent_context is not None:
            try:
                await self._persistent_context.close()
            except Exception:
                pass
            self._persistent_context = None

        if self._persistent_playwright is not None:
            try:
                await self._persistent_playwright.stop()
            except Exception:
                pass
            self._persistent_playwright = None

        profile_dir = Path(BROWSER_PROFILE_DIR).expanduser()
        if BROWSER_PROFILE_TEMPLATE_DIR:
            _copy_profile_template(Path(BROWSER_PROFILE_TEMPLATE_DIR).expanduser(), profile_dir)
        else:
            profile_dir.mkdir(parents=True, exist_ok=True)

        self._persistent_playwright = await async_playwright().start()
        self._persistent_context = await self._persistent_playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            proxy=_proxy_settings(),
            channel=_validated_channel(),
            user_agent=USER_AGENT,
        )
        self._persistent_headless = headless
        logger.info("[Browser] 已启动浏览器配置目录: %s", profile_dir)
        return self._persistent_context

    async def close(self):
        if self._persistent_context is not None:
            try:
                await self._persistent_context.close()
            except Exception as exc:
                logger.warning("[Browser] 关闭持久化上下文出错: %s", exc)
            self._persistent_context = None

        if self._persistent_playwright is not None:
            try:
                await self._persistent_playwright.stop()
            except Exception as exc:
                logger.warning("[Browser] 停止持久化 Playwright 出错: %s", exc)
            self._persistent_playwright = None

        self._persistent_headless = None


browser_manager = BrowserManager()
