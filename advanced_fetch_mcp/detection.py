from __future__ import annotations

import json
from typing import Tuple

from playwright.async_api import Page

from .settings import INTERVENTION_BUTTON_ID, INTERVENTION_TIMEOUT_SECONDS, logger


def build_intervention_script() -> str:
    payload = json.dumps({"button_id": INTERVENTION_BUTTON_ID}, ensure_ascii=False)
    return f"""
(() => {{
  const cfg = {payload};
  const install = () => {{
    if (document.getElementById(cfg.button_id)) return;
    const btn = document.createElement('button');
    btn.id = cfg.button_id;
    btn.textContent = '我已完成页面操作';
    btn.title = '当你确认登录、验证或手动操作已经完成后，点击这里继续抓取';
    btn.style.position = 'fixed';
    btn.style.right = '16px';
    btn.style.bottom = '16px';
    btn.style.zIndex = '2147483647';
    btn.style.padding = '10px 14px';
    btn.style.borderRadius = '10px';
    btn.style.border = 'none';
    btn.style.background = '#111827';
    btn.style.color = '#ffffff';
    btn.style.fontSize = '14px';
    btn.style.cursor = 'pointer';
    btn.addEventListener('click', () => {{
      window.__ADVANCED_FETCH_INTERVENTION_DONE__ = true;
    }});
    document.documentElement.appendChild(btn);
  }};
  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', install, {{ once: true }});
  }} else {{
    install();
  }}
}})();
"""


async def wait_for_intervention_end(page: Page) -> Tuple[str, str, str]:
    reason = "timeout"
    try:
        await page.wait_for_function(
            "() => window.__ADVANCED_FETCH_INTERVENTION_DONE__ === true",
            timeout=INTERVENTION_TIMEOUT_SECONDS * 1000,
        )
        reason = "user_marked_ready"
    except Exception:
        if page.is_closed():
            reason = "page_closed"

    try:
        html = await page.content()
    except Exception:
        html = ""
    try:
        final_url = page.url
    except Exception:
        final_url = ""

    logger.info("[Intervention] 结束原因: %s", reason)
    return html, final_url, reason
