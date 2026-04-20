from __future__ import annotations

from typing import Any, Dict

from .extract import continue_in_text, render_view, search_in_text
from .fetch import (
    FetchResult,
    evaluate_script_on_page,
    fetch_url,
    get_cached_fetch,
    store_cached_fetch,
)
from .params import AdvancedFetchParams
from .sampling import run_prompt_extraction
from .settings import MAX_FIND_MATCHES, logger

FIND_MATCHES_WARNING = f"命中数量过多，仅返回前 {MAX_FIND_MATCHES} 个 matches 摘要。"
CACHE_HIT_WARNING = (
    "本次结果使用了缓存。若需刷新缓存，请发起一次不带 render.cursor 的非 find 请求。"
)


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
    truncated: bool = False,
    cache_hit: bool = False,
    next_cursor: int | None = None,
    find_result: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "success": True,
        "final_url": fetch_result.final_url,
        "result": result_payload,
    }
    if cache_hit:
        result["cache_hit"] = True
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

    return result


async def execute_advanced_fetch(
    *,
    ctx: Any,
    request: AdvancedFetchParams,
) -> Dict[str, Any]:
    url = request.url

    skip_cache = request.should_skip_cache
    cached = get_cached_fetch(url, request.fetch.mode) if not skip_cache else None
    cache_hit = cached is not None

    if cached is not None:
        final_url, html = cached
        fetch_result = FetchResult(html=html, final_url=final_url)
        logger.info("[Tool] 命中缓存")
    else:
        fetch_result = await fetch_url(
            url,
            request.fetch.mode,
            request.fetch.wait_for,
            request.fetch.require_user_intervention,
            request.fetch.timeout,
        )
        store_cached_fetch(url, request.fetch.mode, fetch_result.final_url, fetch_result.html)

    warnings = _build_warnings(fetch_result)
    if cache_hit:
        warnings.append(CACHE_HIT_WARNING)

    if request.operation == "eval":
        value = await evaluate_script_on_page(
            url=fetch_result.final_url,
            wait_for=request.fetch.wait_for,
            require_user_intervention=request.fetch.require_user_intervention,
            script=request.eval.script if request.eval else "",
            timeout=request.fetch.timeout,
        )
        return _build_public_result(
            fetch_result=fetch_result,
            result_payload=value,
            warnings=warnings,
            cache_hit=cache_hit,
        )

    rendered = render_view(fetch_result.html, request.to_render_config())

    if request.operation == "find":
        text_offset = request.render.cursor or 0
        find_result = search_in_text(
            rendered,
            request.find.query if request.find else "",
            request.find.regex if request.find else False,
            text_offset,
        )
        if find_result["matches_truncated"]:
            warnings.append(FIND_MATCHES_WARNING)
        return _build_public_result(
            fetch_result=fetch_result,
            result_payload=find_result["text"],
            warnings=warnings,
            cache_hit=cache_hit,
            next_cursor=find_result.get("next_cursor"),
            find_result=find_result,
        )

    if request.render.cursor is not None:
        continue_result = continue_in_text(
            rendered,
            request.render.cursor,
            request.render.max_length,
        )
        return _build_public_result(
            fetch_result=fetch_result,
            result_payload=continue_result["text"],
            warnings=warnings,
            cache_hit=cache_hit,
            next_cursor=continue_result.get("next_cursor"),
        )

    if request.operation == "sampling":
        try:
            prompt_output = await run_prompt_extraction(
                ctx=ctx,
                source_text=rendered,
                prompt=request.sampling.prompt if request.sampling else "",
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
        return _build_public_result(
            fetch_result=fetch_result,
            result_payload=result_text,
            warnings=warnings,
            cache_hit=cache_hit,
        )

    view_result = continue_in_text(rendered, 0, request.render.max_length)
    return _build_public_result(
        fetch_result=fetch_result,
        result_payload=view_result["text"],
        warnings=warnings,
        truncated=view_result.get("next_cursor") is not None,
        cache_hit=cache_hit,
        next_cursor=view_result.get("next_cursor"),
    )
