from __future__ import annotations

import json
import re
from typing import Any, Dict

from bs4 import BeautifulSoup, Tag
from markdownify import markdownify
import trafilatura

from .params import RenderConfig
from .settings import CORE_REMOVE_TAGS, FIND_SNIPPET_MAX_CHARS, MAX_FIND_MATCHES

MatchSummary = Dict[str, str]


def apply_strip_selectors(root: Tag, strip_selectors: list[str]) -> Tag:
    """按 CSS selectors 剔除节点。"""
    for selector in strip_selectors:
        try:
            for tag in root.select(selector):
                tag.decompose()
        except Exception:
            continue
    return root


def prepare_body(soup: BeautifulSoup, view: RenderConfig) -> Tag:
    """用于 strategy=none，返回处理后的 body。"""
    root: Tag = soup.body or soup

    # 移除 script/style 等基础噪音
    for tag_name in CORE_REMOVE_TAGS:
        for tag in root.find_all(tag_name):
            tag.decompose()

    # 按 strip_selectors 剔除节点
    apply_strip_selectors(root, view.strip_selectors)

    return root


def render_view(html: str, view: RenderConfig) -> str:
    strategy = view.strategy
    want_markdown = view.output_format == "markdown"
    strip_selectors = view.strip_selectors

    # strategy=none 时返回完整 body（不智能提取）
    if strategy == "none":
        soup = BeautifulSoup(html, "html.parser")
        prepared_root = prepare_body(soup, view)
        if want_markdown:
            return markdownify(str(prepared_root))
        return str(prepared_root)

    # strategy=strict/loose 用 trafilatura 智能提取
    output_format = "markdown" if want_markdown else "txt"
    favor_precision = strategy == "strict"
    favor_recall = strategy == "loose"

    # include_images: 如果 strip_selectors 包含 img，则不保留图片
    include_images = "img" not in strip_selectors

    extracted = trafilatura.extract(
        html,
        output_format=output_format,
        include_comments=False,
        include_tables=True,
        include_images=include_images,
        favor_precision=favor_precision,
        favor_recall=favor_recall,
    )
    if extracted:
        return extracted

    # trafilatura 失败，fallback 到 body 处理
    soup = BeautifulSoup(html, "html.parser")
    prepared_root = prepare_body(soup, view)
    if want_markdown:
        return markdownify(str(prepared_root))
    return str(prepared_root)


def _window_start_for_match(match_start: int, max_length: int) -> int:
    return max(0, match_start - max_length // 4)


def _build_match_summary(
    full_text: str, match: re.Match[str], max_length: int, text_offset: int = 0
) -> MatchSummary:
    # match.start() 是相对于 search_text 的位置，需要加上 text_offset 得到绝对位置
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

    # 从 text_offset 位置开始搜索
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

    # 最多返回 MAX_FIND_MATCHES 个
    matches_truncated = matches_total > MAX_FIND_MATCHES
    matches = [
        _build_match_summary(
            full_text=full_text, match=match, max_length=max_length, text_offset=search_start
        )
        for match in found_matches[:MAX_FIND_MATCHES]
    ]

    # next_cursor: 第一个 match 的文本位置（用于续读）
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