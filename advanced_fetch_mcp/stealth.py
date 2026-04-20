from __future__ import annotations

from functools import lru_cache
from typing import Optional

from playwright.async_api import BrowserContext

from .settings import BROWSER_LOCALE, ENABLE_AUTH_STEALTH, USER_AGENT, logger

try:
    from playwright_stealth import Stealth
except Exception:  # pragma: no cover - optional dependency
    Stealth = None


def _language_overrides() -> tuple[str, ...]:
    locale = (BROWSER_LOCALE or "en-US").replace("_", "-")
    parts = [locale]
    base = locale.split("-", 1)[0]
    if base and base not in parts:
        parts.append(base)
    if "en-US" not in parts:
        parts.append("en-US")
    if "en" not in parts:
        parts.append("en")
    return tuple(parts)


@lru_cache(maxsize=1)
def _build_stealth() -> Optional[object]:
    if not ENABLE_AUTH_STEALTH:
        return None
    if Stealth is None:
        logger.warning(
            "[Browser] 未安装 playwright-stealth，auth 模式将继续运行，但不会启用 stealth。可执行: pip install playwright-stealth"
        )
        return None
    return Stealth(
        init_scripts_only=True,
        navigator_languages_override=_language_overrides(),
        navigator_user_agent_override=USER_AGENT,
    )


async def apply_auth_stealth(context: BrowserContext) -> bool:
    stealth = _build_stealth()
    if stealth is None:
        return False

    try:
        await stealth.apply_stealth_async(context)
        logger.info("[Browser] 已对 auth context 应用 stealth")
        return True
    except Exception as exc:
        logger.warning("[Browser] 应用 stealth 失败，继续以普通模式运行: %s", exc)
        return False
