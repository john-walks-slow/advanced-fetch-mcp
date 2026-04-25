from __future__ import annotations

import re
from typing import Any, Dict, Set

import trafilatura
from lxml import html as lxml_html
from markdownify import markdownify

from .params import RenderConfig
from .settings import FIND_SNIPPET_MAX_CHARS, MAX_FIND_MATCHES

MatchSummary = Dict[str, str]


def _normalize_html_input(html: str | None) -> str:
    return "" if html is None else html


def _is_empty_html(html: str | None) -> bool:
    return not _normalize_html_input(html).strip()


def _normalize_strategy(strategy: str | None) -> str:
    return "default" if strategy in {None, "default"} else strategy


def _extract_body_html(html: str) -> str:
    try:
        document = lxml_html.fromstring(html)
        body = document.find(".//body")
        target = body if body is not None else document
        return lxml_html.tostring(target, encoding="unicode", method="html")
    except Exception:
        return html


def _extract_body_node(html: str):
    try:
        document = lxml_html.fromstring(html)
        body = document.find(".//body")
        return body if body is not None else document
    except Exception:
        return None


def _extract_body_text(html: str) -> str:
    try:
        target = _extract_body_node(html)
        if target is None:
            return ""
        chunks = [chunk.strip() for chunk in target.itertext() if chunk and chunk.strip()]
        return "\n\n".join(chunks)
    except Exception:
        return ""


def _remove_nodes(target, xpath: str) -> None:
    for node in target.xpath(xpath):
        try:
            node.drop_tree()
        except Exception:
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)


def _unwrap_nodes(target, xpath: str) -> None:
    for node in target.xpath(xpath):
        try:
            node.drop_tag()
        except Exception:
            continue


def _filter_markdownify_html(html: str, include_elements: list[str]) -> str:
    body = _extract_body_node(html)
    if body is None:
        return html

    extras = set(include_elements)
    _remove_nodes(body, ".//script | .//style | .//noscript | .//template")

    if "comments" not in extras:
        for node in body.xpath(".//comment()"):
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)

    if "images" not in extras:
        _remove_nodes(body, ".//img | .//picture | .//source | .//svg | .//canvas")

    if "links" not in extras:
        _unwrap_nodes(body, ".//a")

    if "tables" not in extras:
        _unwrap_nodes(body, ".//table | .//thead | .//tbody | .//tfoot | .//tr | .//th | .//td | .//caption")

    if "formatting" not in extras:
        _unwrap_nodes(
            body,
            ".//strong | .//b | .//em | .//i | .//u | .//mark | .//small | .//sub | .//sup | .//code | .//kbd | .//var | .//samp | .//del | .//ins | .//pre | .//blockquote | .//h1 | .//h2 | .//h3 | .//h4 | .//h5 | .//h6",
        )

    return lxml_html.tostring(body, encoding="unicode", method="html")


def _render_markdownify_view(html: str, view: RenderConfig) -> str:
    filtered_html = _filter_markdownify_html(html, view.include_elements)
    if view.output_format == "html":
        return filtered_html

    try:
        return markdownify(
            filtered_html,
            heading_style="ATX",
            bullets="-",
        ).strip()
    except Exception:
        return _extract_body_text(filtered_html) or trafilatura.html2txt(filtered_html) or ""


def _build_trafilatura_kwargs(view: RenderConfig) -> Dict[str, Any]:
    extras: Set[str] = set(view.include_elements)
    strategy = _normalize_strategy(view.strategy)
    return {
        "output_format": view.output_format,
        "include_comments": "comments" in extras,
        "include_tables": "tables" in extras,
        "include_images": "images" in extras,
        "include_links": "links" in extras,
        "include_formatting": view.output_format == "markdown" or "formatting" in extras,
        "favor_precision": strategy == "strict",
        "favor_recall": strategy == "loose",
        "deduplicate": True,
    }


def render_view(html: str, view: RenderConfig, engine: str = "trafilatura") -> str:
    html = _normalize_html_input(html)
    if _is_empty_html(html):
        return ""

    if engine == "markdownify":
        return _render_markdownify_view(html, view)

    strategy = _normalize_strategy(view.strategy)

    primary_kwargs = _build_trafilatura_kwargs(view)

    attempts: list[Dict[str, Any]] = [primary_kwargs]

    if strategy == "strict":
        attempts.append(
            {
                **primary_kwargs,
                "favor_precision": False,
                "favor_recall": False,
            }
        )

    if strategy != "loose":
        attempts.append(
            {
                **primary_kwargs,
                "favor_precision": False,
                "favor_recall": True,
            }
        )

    attempts.append(
        {
            **primary_kwargs,
            "fast": True,
            "favor_precision": False,
            "favor_recall": True,
        }
    )

    seen_attempts: set[tuple[tuple[str, Any], ...]] = set()
    for kwargs in attempts:
        signature = tuple(sorted(kwargs.items()))
        if signature in seen_attempts:
            continue
        seen_attempts.add(signature)
        extracted = trafilatura.extract(html, **kwargs)
        if extracted:
            return extracted

    postbody, baseline_text, _ = trafilatura.baseline(html)
    if baseline_text:
        if view.output_format == "html" and postbody is not None:
            return lxml_html.tostring(postbody, encoding="unicode")
        return baseline_text

    if view.output_format == "html":
        return html

    fallback_text = trafilatura.html2txt(html)
    return fallback_text or ""


def render_auto_wait_text(html: str) -> str:
    """用于 wait_for=auto：只关心可抽取正文文本是否趋于稳定。"""
    html = _normalize_html_input(html)
    if _is_empty_html(html):
        return ""

    extracted = trafilatura.extract(
        html,
        output_format="txt",
        include_comments=False,
        include_tables=False,
        include_images=False,
        include_links=False,
        include_formatting=False,
        favor_precision=True,
        favor_recall=False,
        deduplicate=True,
    )
    if extracted:
        return re.sub(r"\s+", " ", extracted).strip()

    fallback_text = trafilatura.html2txt(html) or ""
    return re.sub(r"\s+", " ", fallback_text).strip()


def _build_match_summary(
    full_text: str,
    match: re.Match[str],
    snippet_max_chars: int = FIND_SNIPPET_MAX_CHARS,
) -> MatchSummary:
    absolute_start = match.start()
    absolute_end = match.end()
    max_chars = max(1, snippet_max_chars)
    match_length = max(1, absolute_end - absolute_start)
    core_length = min(max_chars, match_length)
    remaining_context = max(0, max_chars - core_length)
    left_context = remaining_context // 2
    right_context = remaining_context - left_context
    snippet_start = max(0, absolute_start - left_context)
    snippet_end = min(len(full_text), absolute_end + right_context)
    current_length = snippet_end - snippet_start

    if current_length < max_chars:
        expand_left = min(snippet_start, max_chars - current_length)
        snippet_start -= expand_left
        current_length = snippet_end - snippet_start
        expand_right = min(len(full_text) - snippet_end, max_chars - current_length)
        snippet_end += expand_right

    snippet = full_text[snippet_start:snippet_end]
    if snippet_start > 0:
        snippet = "…" + snippet
    if snippet_end < len(full_text):
        snippet = snippet + "…"
    cursor = encode_cursor(absolute_start)
    return {
        "snippet": snippet,
        "cursor": cursor,
    }


def encode_cursor(offset: int) -> int:
    return max(0, offset)


def search_in_text(
    full_text: str,
    query: str,
    use_regex: bool,
    match_limit: int | None = None,
    snippet_max_chars: int | None = None,
    start_index: int = 0,
) -> Dict[str, Any]:
    if use_regex:
        try:
            regex = re.compile(query, re.IGNORECASE)
        except re.error:
            regex = re.compile(re.escape(query), re.IGNORECASE)
    else:
        regex = re.compile(re.escape(query), re.IGNORECASE)

    found_matches = list(regex.finditer(full_text))
    matches_total = len(found_matches)
    if not found_matches:
        return {
            "text": "",
            "found": False,
            "matches": [],
            "matches_total": 0,
            "matches_truncated": False,
            "next_cursor": None,
        }

    effective_start_index = max(0, start_index)
    effective_limit = MAX_FIND_MATCHES if match_limit is None else max(1, match_limit)
    effective_snippet_max_chars = (
        FIND_SNIPPET_MAX_CHARS
        if snippet_max_chars is None
        else max(1, snippet_max_chars)
    )
    returned_matches = found_matches[
        effective_start_index : effective_start_index + effective_limit
    ]
    matches_truncated = (
        effective_start_index > 0
        or effective_start_index + len(returned_matches) < matches_total
    )
    matches = [
        _build_match_summary(
            full_text=full_text,
            match=match,
            snippet_max_chars=effective_snippet_max_chars,
        )
        for match in returned_matches
    ]

    first = matches[0] if matches else None
    next_cursor = first["cursor"] if first else None

    return {
        "text": "",
        "found": True,
        "matches": matches,
        "matches_total": matches_total,
        "matches_truncated": matches_truncated,
        "next_cursor": next_cursor,
    }


def continue_in_text(full_text: str, cursor: int, max_length: int) -> Dict[str, Any]:
    start = max(0, cursor)
    if start >= len(full_text):
        return {
            "text": "",
            "next_cursor": None,
        }
    end = min(len(full_text), start + max_length)
    next_cursor = encode_cursor(end) if end < len(full_text) else None
    return {
        "text": full_text[start:end],
        "next_cursor": next_cursor,
    }
