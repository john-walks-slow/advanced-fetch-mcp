from __future__ import annotations

import json
from typing import Any, Dict, Tuple

from .dsl import AdvancedFetchParams
from .extract import build_view_config, continue_in_text, render_view, search_in_text
from .fetch import (
    FetchResult,
    evaluate_script_on_page,
    fetch_url,
    get_cached_fetch,
    store_cached_fetch,
)
from .sampling import run_prompt_extraction
from .settings import DEFAULT_MAX_LENGTH, MAX_FIND_MATCHES, logger

FIND_MATCHES_WARNING = f"命中数量过多，仅返回前 {MAX_FIND_MATCHES} 个 matches 摘要。"


def _serialize_result_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list, bool, int, float)):
        try:
            return json.dumps(value, ensure_ascii=False, indent=2)
        except Exception:
            return str(value)
    return str(value)


def _truncate_text_middle(value: str, max_length: int) -> Tuple[str, bool]:
    if len(value) <= max_length:
        return value, False
    omitted = len(value) - max_length
    long_marker = f"<{omitted} chars truncated...>"
    short_marker = f"<{omitted}>"
    marker = long_marker if max_length >= len(long_marker) + 2 else short_marker
    if max_length <= len(marker):
        return marker[:max_length], True
    remaining = max_length - len(marker)
    head = max(1, remaining // 2)
    tail = max(1, remaining - head)
    if head + tail > len(value):
        tail = max(0, len(value) - head)
    return value[:head] + marker + value[-tail:] if tail else value[:head] + marker, True


def _build_warnings(fetch_result: FetchResult) -> list[str]:
    warnings: list[str] = []
    if fetch_result.timed_out:
        stage = fetch_result.timeout_stage or "unknown"
        if stage == "static_request":
            warnings.append("静态请求超时，已返回当前可得结果。")
        else:
            warnings.append(f"抓取等待在 {stage} 阶段超时，已直接返回当前已加载内容。")
    if fetch_result.intervention_ended_by == "timeout":
        warnings.append("人工介入等待超时，已返回当前页面内容。")
    if fetch_result.intervention_ended_by == "page_closed":
        warnings.append("浏览器页面已关闭，已返回当前可得内容。")
    return warnings


def _build_public_result(
    *,
    fetch_result: FetchResult,
    result_payload: Any,
    warnings: list[str],
    truncated: bool,
    find_result: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "success": True,
        "final_url": fetch_result.final_url,
        "result": result_payload,
    }
    if fetch_result.timed_out:
        result["timed_out"] = True
        if fetch_result.timeout_stage:
            result["timeout_stage"] = fetch_result.timeout_stage
    if fetch_result.intervention_ended_by:
        result["intervention_ended_by"] = fetch_result.intervention_ended_by
    if truncated:
        result["truncated"] = True
    if warnings:
        result["warnings"] = warnings

    if find_result is not None:
        result["found"] = find_result["found"]
        if find_result.get("matches"):
            result["matches"] = find_result["matches"]
        if "matches_total" in find_result:
            result["matches_total"] = find_result["matches_total"]
        if find_result.get("matches_truncated"):
            result["matches_truncated"] = True
        if find_result.get("next_cursor") is not None:
            result["next_cursor"] = find_result["next_cursor"]

    return result


async def execute_advanced_fetch(
    *,
    url: str,
    ctx: Any,
    request: AdvancedFetchParams,
) -> Dict[str, Any]:
    effective_max_length = request.max_length or DEFAULT_MAX_LENGTH

    cache_allowed = request.evaluateJS is None
    cached = (
        get_cached_fetch(
            url,
            request.mode,
            request.wait_for,
            request.require_user_intervention,
        )
        if cache_allowed and not request.refresh_cache
        else None
    )

    if cached is not None:
        final_url, html = cached
        fetch_result = FetchResult(html=html, final_url=final_url)
        logger.info("[Tool] 命中缓存")
    else:
        fetch_result = await fetch_url(
            url,
            request.mode,
            request.wait_for,
            request.require_user_intervention,
        )
        if request.evaluateJS is None:
            store_cached_fetch(
                url,
                request.mode,
                request.wait_for,
                request.require_user_intervention,
                fetch_result.final_url,
                fetch_result.html,
            )

    warnings = _build_warnings(fetch_result)

    if request.evaluateJS is not None:
        value = await evaluate_script_on_page(
            url=fetch_result.final_url,
            wait_for=request.wait_for,
            require_user_intervention=request.require_user_intervention,
            script=request.evaluateJS,
        )
        result_text, truncated = _truncate_text_middle(
            _serialize_result_value(value),
            effective_max_length,
        )
        return _build_public_result(
            fetch_result=fetch_result,
            result_payload=result_text,
            warnings=warnings,
            truncated=truncated,
        )

    view = build_view_config(request.model_dump())
    rendered = render_view(fetch_result.html, view)

    if request.find_in_page is not None:
        if request.find_in_page.query is not None:
            find_result = search_in_text(
                rendered,
                request.find_in_page.query,
                effective_max_length,
                request.find_in_page.regex,
            )
        else:
            find_result = continue_in_text(
                rendered,
                request.find_in_page.cursor or "",
                effective_max_length,
            )
        if find_result["matches_truncated"]:
            warnings.append(FIND_MATCHES_WARNING)
        return _build_public_result(
            fetch_result=fetch_result,
            result_payload=find_result["text"],
            warnings=warnings,
            truncated=False,
            find_result=find_result,
        )

    if request.prompt is not None:
        try:
            prompt_output = await run_prompt_extraction(
                ctx=ctx,
                source_text=rendered,
                prompt=request.prompt,
            )
            result_text = (
                ""
                if prompt_output.get("value") is None
                else str(prompt_output["value"])
            )
        except Exception as exc:
            logger.warning("[Prompt] 失败，回退到原始视图文本：%s", exc)
            warnings.append(f"prompt 处理失败，已回退到原始文本：{exc}")
            result_text = rendered
        result_text, truncated = _truncate_text_middle(result_text, effective_max_length)
        return _build_public_result(
            fetch_result=fetch_result,
            result_payload=result_text,
            warnings=warnings,
            truncated=truncated,
        )

    result_text, truncated = _truncate_text_middle(rendered, effective_max_length)
    return _build_public_result(
        fetch_result=fetch_result,
        result_payload=result_text,
        warnings=warnings,
        truncated=truncated,
    )
