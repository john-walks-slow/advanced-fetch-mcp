from __future__ import annotations

import json
import re
from typing import Any, Dict

from bs4 import BeautifulSoup, Tag
from markdownify import markdownify
import trafilatura

from .settings import CONTENT_ROOT_SELECTORS, CORE_REMOVE_TAGS, FIND_SNIPPET_MAX_CHARS, MAX_FIND_MATCHES, MEDIA_REMOVE_TAGS

MatchSummary = Dict[str, str]


def build_view_config(config: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "markdownify": bool(config.get("markdownify", True)),
        "scope": config.get("scope", "content"),
        "selector": config.get("selector"),
        "strip": list(config.get("strip", [])),
        "keep_media": bool(config.get("keep_media", False)),
    }


def prepare_root(soup: BeautifulSoup, view: Dict[str, Any]) -> Tag:
    """用于 scope=body/full 或 trafilatura 失败时的 fallback。"""
    root: Tag = soup

    # 合并所有要移除的标签，一次性遍历
    all_remove_tags = set(CORE_REMOVE_TAGS)
    if not view.get("keep_media", False):
        all_remove_tags.update(MEDIA_REMOVE_TAGS)
    for tag_name in all_remove_tags:
        for tag in root.find_all(tag_name):
            tag.decompose()

    # scope 选择（content 在 render_view 已由 trafilatura 处理）
    scope = view.get("scope") or "content"
    if scope == "content":
        selected = root.select_one(CONTENT_ROOT_SELECTORS)
        if selected is None:
            selected = root.body or root
        if selected is not root:
            root = selected
    elif scope == "body":
        selected = root.body or root
        if selected is not root:
            root = selected
    elif scope != "full":
        raise ValueError(f"Unsupported scope: {scope}")

    # selector 也直接用
    selector = view.get("selector")
    if selector:
        try:
            selected = root.select_one(selector)
        except Exception:
            selected = None
        if selected is not None and selected is not root:
            root = selected

    for css_selector in view.get("strip", []):
        try:
            for tag in root.select(css_selector):
                tag.decompose()
        except Exception:
            continue

    return root


def render_view(html: str, view: Dict[str, Any]) -> str:
    scope = view.get("scope") or "content"
    want_markdown = view.get("markdownify", True)
    keep_media = view.get("keep_media", False)

    # scope=content 时优先用 trafilatura 智能提取（自动剔除广告/噪音）
    if scope == "content":
        output_format = "markdown" if want_markdown else "txt"
        extracted = trafilatura.extract(
            html,
            output_format=output_format,
            include_comments=False,
            include_tables=True,
            include_images=keep_media,
            favor_precision=True,  # 精确模式，避免误删正文
        )
        if extracted:
            return extracted
        # trafilatura 失败，fallback 到 selector 逻辑

    # scope=body/full 或 trafilatura 失败时，用原有逻辑
    soup = BeautifulSoup(html, "html.parser")
    prepared_root = prepare_root(soup, view)
    if want_markdown:
        return markdownify(str(prepared_root))
    return str(prepared_root)


def _window_start_for_match(match_start: int, max_length: int) -> int:
    return max(0, match_start - max_length // 4)


def _build_match_summary(full_text: str, match: re.Match[str], max_length: int, text_offset: int = 0) -> MatchSummary:
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
        _build_match_summary(full_text=full_text, match=match, max_length=max_length, text_offset=search_start)
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
