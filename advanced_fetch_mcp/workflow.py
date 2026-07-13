from __future__ import annotations

import json
from typing import Any, Dict, Tuple

from .extract import continue_in_text, extract_links, render_view, search_in_text
from .fetch import (
    FetchResult,
    _is_refid,
    evaluate_script_on_page,
    fetch_url,
    get_cached_fetch_by_refid,
    store_cached_fetch,
)
from .params import AdvancedFetchParams
from .sampling import run_prompt_extraction
from .settings import AUTO_WAIT_MIN_CONTENT_LENGTH, logger

FIND_MATCHES_WARNING = "命中数量过多，matches 已按请求参数或服务默认限制截断。"


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
    return (
        value[:head] + marker + value[-tail:] if tail else value[:head] + marker
    ), True


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
    refid: str | None = None,
    truncated: bool = False,
    next_cursor: int | None = None,
    find_result: Dict[str, Any] | None = None,
    links_result: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "success": True,
        "final_url": fetch_result.final_url,
        "result": result_payload,
    }
    if refid is not None:
        result["refid"] = refid
    if fetch_result.timed_out:
        result["timed_out"] = True
        if fetch_result.timeout_stage:
            result["timeout_stage"] = fetch_result.timeout_stage
    if fetch_result.intervention_ended_by:
        result["intervention_ended_by"] = fetch_result.intervention_ended_by
    if truncated:
        result["truncated"] = True
    if next_cursor is not None:
        result["next_cursor"] = next_cursor
    if warnings:
        result["warnings"] = warnings

    if find_result is not None:
        result["found"] = find_result["found"]
        result["matches"] = find_result.get("matches", [])
        if "matches_total" in find_result:
            result["matches_total"] = find_result["matches_total"]
        if find_result.get("matches_truncated"):
            result["matches_truncated"] = True

    if links_result is not None:
        result["links"] = links_result.get("links", [])
        if "links_total" in links_result:
            result["links_total"] = links_result["links_total"]
        if links_result.get("links_truncated"):
            result["links_truncated"] = True

    return result


async def execute_advanced_fetch(
    *,
    ctx: Any,
    request: AdvancedFetchParams,
) -> Dict[str, Any]:
    url = request.url
    require_intervention = request.operation == "request_human_action"

    if request.operation == "eval":
        eval_result = await evaluate_script_on_page(
            url=url,
            require_user_intervention=False,
            min_stable_seconds=request.fetch.min_stable_seconds,
            script=request.eval.script if request.eval else "",
            timeout=request.fetch.timeout,
        )
        warnings = _build_warnings(eval_result.fetch_result)
        result_text, truncated = _truncate_text_middle(
            _serialize_result_value(eval_result.value),
            request.max_length,
        )
        return _build_public_result(
            fetch_result=eval_result.fetch_result,
            result_payload=result_text,
            warnings=warnings,
            truncated=truncated,
        )

    # Check if url is a refid for cache reuse
    if _is_refid(url):
        cached = get_cached_fetch_by_refid(url)
        if cached is not None:
            final_url, html = cached
            fetch_result = FetchResult(html=html, final_url=final_url)
            logger.info("[Tool] 命中 refid 缓存")
            refid = url
        else:
            raise ValueError(
                f"refid '{url}' 不存在或已过期，请使用原始 URL 重新抓取。"
            )
    else:
        early_exit_min_length = (
            request.fetch.min_content_length
            if request.fetch.min_content_length is not None
            else AUTO_WAIT_MIN_CONTENT_LENGTH
        )
        fetch_result = await fetch_url(
            url,
            request.fetch.mode,
            require_intervention,
            request.fetch.min_stable_seconds,
            early_exit_min_length,
            request.fetch.timeout,
        )
        refid = store_cached_fetch(
            url, request.fetch.mode, fetch_result.final_url, fetch_result.html
        )

    warnings = _build_warnings(fetch_result)
    rendered = render_view(
        fetch_result.html, request.to_view_config(), base_url=fetch_result.final_url
    )

    # Extract links if view.links is configured
    links_result = None
    if request.view.links is not None:
        links_result = extract_links(
            html=fetch_result.html,
            base_url=fetch_result.final_url,
            rendered_text=rendered,
            limit=request.view.links.limit,
        )

    if request.operation == "find":
        find_result = search_in_text(
            rendered,
            request.find.query if request.find else "",
            request.find.regex if request.find else False,
            request.find.limit if request.find else None,
            None,
            request.find.start_index if request.find else 0,
        )
        if find_result["matches_truncated"]:
            warnings.append(FIND_MATCHES_WARNING)
        return _build_public_result(
            fetch_result=fetch_result,
            result_payload=find_result["text"],
            warnings=warnings,
            refid=refid,
            next_cursor=find_result.get("next_cursor"),
            find_result=find_result,
            links_result=links_result,
        )

    if request.view.cursor is not None:
        continue_result = continue_in_text(
            rendered,
            request.view.cursor,
            request.max_length,
        )
        return _build_public_result(
            fetch_result=fetch_result,
            result_payload=continue_result["text"],
            warnings=warnings,
            refid=refid,
            next_cursor=continue_result.get("next_cursor"),
            links_result=links_result,
        )

    if request.operation == "sampling":
        try:
            sampling_config = request.sampling
            prompt_output = await run_prompt_extraction(
                ctx=ctx,
                source_text=rendered,
                prompt=sampling_config.prompt if sampling_config else "",
                model=sampling_config.model if sampling_config else None,
            )
            result_text = (
                ""
                if prompt_output.get("value") is None
                else str(prompt_output["value"])
            )
        except Exception as exc:
            logger.warning("[Sampling] 失败，回退到原始视图文本：%s", exc)
            warnings.append(f"sampling 处理失败，已回退到原始文本：{exc}")
            result_text = rendered
        result_text, truncated = _truncate_text_middle(
            result_text,
            request.max_length,
        )
        return _build_public_result(
            fetch_result=fetch_result,
            result_payload=result_text,
            warnings=warnings,
            refid=refid,
            truncated=truncated,
            links_result=links_result,
        )

    view_result = continue_in_text(rendered, 0, request.max_length)
    return _build_public_result(
        fetch_result=fetch_result,
        result_payload=view_result["text"],
        warnings=warnings,
        refid=refid,
        truncated=view_result.get("next_cursor") is not None,
        next_cursor=view_result.get("next_cursor"),
        links_result=links_result,
    )
