from __future__ import annotations

import re
from typing import Any, Dict, Set

import trafilatura
from lxml import html as lxml_html

from .params import RenderConfig
from .settings import FIND_SNIPPET_MAX_CHARS, MAX_FIND_MATCHES

MatchSummary = Dict[str, str]


def _build_trafilatura_kwargs(view: RenderConfig) -> Dict[str, Any]:
    extras: Set[str] = set(view.extra_elements)
    return {
        "output_format": view.output_format,
        "include_comments": "comments" in extras,
        "include_tables": "tables" in extras,
        "include_images": "images" in extras,
        "include_links": "links" in extras,
        "include_formatting": view.output_format == "markdown" or "formatting" in extras,
        "favor_precision": view.strategy == "strict",
        "favor_recall": view.strategy == "loose",
        "deduplicate": True,
    }


def render_view(html: str, view: RenderConfig) -> str:
    primary_kwargs = _build_trafilatura_kwargs(view)

    attempts: list[Dict[str, Any]] = [primary_kwargs]

    if view.strategy == "strict":
        attempts.append({
            **primary_kwargs,
            "favor_precision": False,
            "favor_recall": False,
        })

    if view.strategy != "loose":
        attempts.append({
            **primary_kwargs,
            "favor_precision": False,
            "favor_recall": True,
        })

    attempts.append({
        **primary_kwargs,
        "fast": True,
        "favor_precision": False,
        "favor_recall": True,
    })

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


def _window_start_for_match(match_start: int, max_length: int) -> int:
    return max(0, match_start - max_length // 4)


def _build_match_summary(
    full_text: str, match: re.Match[str], max_length: int, text_offset: int = 0
) -> MatchSummary:
    absolute_start = match.start() + text_offset
    snippet_radius = max(20, FIND_SNIPPET_MAX_CHARS // 2)
    snippet_start = max(0, absolute_start - snippet_radius)
    snippet_end = min(len(full_text), match.end() + text_offset + snippet_radius)
    snippet = full_text[snippet_start:snippet_end]
    if snippet_start > 0:
        snippet = "…" + snippet
    if snippet_end < len(full_text):
        snippet = snippet + "…"
    cursor = encode_cursor(_window_start_for_match(absolute_start, max_length))
    return {
        "snippet": snippet,
        "cursor": cursor,
    }


def encode_cursor(offset: int) -> int:
    return max(0, offset)


def search_in_text(
    full_text: str,
    query: str,
    max_length: int,
    use_regex: bool,
    text_offset: int = 0,
) -> Dict[str, Any]:
    if use_regex:
        try:
            regex = re.compile(query, re.IGNORECASE)
        except re.error:
            regex = re.compile(re.escape(query), re.IGNORECASE)
    else:
        regex = re.compile(re.escape(query), re.IGNORECASE)

    search_start = max(0, text_offset)
    search_text = full_text[search_start:]
    found_matches = list(regex.finditer(search_text))
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

    matches_truncated = matches_total > MAX_FIND_MATCHES
    matches = [
        _build_match_summary(
            full_text=full_text, match=match, max_length=max_length, text_offset=search_start
        )
        for match in found_matches[:MAX_FIND_MATCHES]
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
            "found": True,
            "matches": [],
            "matches_total": 0,
            "matches_truncated": False,
            "next_cursor": None,
        }
    end = min(len(full_text), start + max_length)
    next_cursor = encode_cursor(end) if end < len(full_text) else None
    return {
        "text": full_text[start:end],
        "found": True,
        "matches": [],
        "matches_total": 0,
        "matches_truncated": False,
        "next_cursor": next_cursor,
    }
