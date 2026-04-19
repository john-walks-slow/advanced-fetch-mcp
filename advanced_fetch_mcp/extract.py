from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from bs4 import BeautifulSoup, Tag
from markdownify import markdownify

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
    root: Tag = soup
    scope = view.get("scope") or "content"

    if scope == "full":
        pass
    elif scope == "body":
        for tag_name in CORE_REMOVE_TAGS:
            for tag in root.find_all(tag_name):
                tag.decompose()
        selected = root.body or root
        if selected is not root:
            root = BeautifulSoup(str(selected), "html.parser")
    elif scope == "content":
        for tag_name in CORE_REMOVE_TAGS:
            for tag in root.find_all(tag_name):
                tag.decompose()
        selected = root.select_one(CONTENT_ROOT_SELECTORS)
        if selected is None:
            selected = root.body or root
        if selected is not root:
            root = BeautifulSoup(str(selected), "html.parser")
    else:
        raise ValueError(f"Unsupported scope: {scope}")

    selector = view.get("selector")
    if selector:
        try:
            selected = root.select_one(selector)
        except Exception:
            selected = None
        if selected is not None and selected is not root:
            root = BeautifulSoup(str(selected), "html.parser")

    for css_selector in view.get("strip", []):
        try:
            for tag in root.select(css_selector):
                tag.decompose()
        except Exception:
            continue

    if not view.get("keep_media", False):
        for tag_name in MEDIA_REMOVE_TAGS:
            for tag in root.find_all(tag_name):
                tag.decompose()

    return root


def render_view(html: str, view: Dict[str, Any]) -> str:
    prepared_root = prepare_root(BeautifulSoup(html, "html.parser"), view)
    if view.get("markdownify", True):
        return markdownify(str(prepared_root))
    return str(prepared_root)


def _window_start_for_match(match_start: int, max_length: int) -> int:
    return max(0, match_start - max_length // 4)


def _build_match_summary(full_text: str, match: re.Match[str], max_length: int) -> MatchSummary:
    snippet_radius = max(20, FIND_SNIPPET_MAX_CHARS // 2)
    snippet_start = max(0, match.start() - snippet_radius)
    snippet_end = min(len(full_text), match.end() + snippet_radius)
    snippet = full_text[snippet_start:snippet_end]
    if snippet_start > 0:
        snippet = "…" + snippet
    if snippet_end < len(full_text):
        snippet = snippet + "…"
    cursor = encode_cursor(_window_start_for_match(match.start(), max_length))
    return {
        "snippet": snippet,
        "cursor": cursor,
    }


def encode_cursor(offset: int) -> str:
    return format(max(0, offset), "x")


def decode_cursor(cursor: str) -> int:
    value = (cursor or "").strip().lower()
    if not value:
        raise ValueError("cursor 不能为空。")
    try:
        return int(value, 16)
    except ValueError as exc:
        raise ValueError("cursor 非法。") from exc


def search_in_text(full_text: str, query: str, max_length: int, use_regex: bool) -> Dict[str, Any]:
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

    matches_truncated = matches_total > MAX_FIND_MATCHES
    matches = [
        _build_match_summary(full_text=full_text, match=match, max_length=max_length)
        for i, match in enumerate(found_matches[:MAX_FIND_MATCHES])
    ]
    first = matches[0]
    start = decode_cursor(first["cursor"])
    end = min(len(full_text), start + max_length)
    next_cursor = encode_cursor(end) if end < len(full_text) else None
    return {
        "text": full_text[start:end],
        "found": True,
        "matches": matches,
        "matches_total": matches_total,
        "matches_truncated": matches_truncated,
        "next_cursor": next_cursor,
    }


def continue_in_text(full_text: str, cursor: str, max_length: int) -> Dict[str, Any]:
    start = decode_cursor(cursor)
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
