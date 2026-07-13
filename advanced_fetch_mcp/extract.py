from __future__ import annotations

import base64
import re
from typing import Any, Dict
from urllib.parse import urljoin, urlparse, urlunparse

import requests
import trafilatura
from lxml import html as lxml_html
from markdownify import markdownify

from .params import ViewConfig
from .settings import FIND_SNIPPET_MAX_CHARS, MAX_FIND_MATCHES, MAX_LINKS_COUNT, logger

MatchSummary = Dict[str, str]

_IMAGE_MAX_SIZE = 5 * 1024 * 1024  # 5MB
_IMAGE_DOWNLOAD_TIMEOUT = 10


def _normalize_html_input(html: str | None) -> str:
    return "" if html is None else html


def _is_empty_html(html: str | None) -> bool:
    return not _normalize_html_input(html).strip()


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


def _download_image_as_base64(img_url: str) -> tuple[str | None, str | None]:
    """Download image and return (base64_data, mime_type) or (None, None) on failure."""
    try:
        resp = requests.get(img_url, timeout=_IMAGE_DOWNLOAD_TIMEOUT, stream=True)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "image/png")
        data = resp.content
        if len(data) > _IMAGE_MAX_SIZE:
            logger.warning("Image too large (%d bytes), skipping: %s", len(data), img_url)
            return None, None
        b64 = base64.b64encode(data).decode("ascii")
        return b64, content_type
    except Exception as exc:
        logger.warning("Failed to download image %s: %s", img_url, exc)
        return None, None


def _collect_images_from_html(html: str, base_url: str | None) -> list[dict[str, Any]]:
    """Collect all img tags with src, alt, and optional figure caption."""
    try:
        doc = lxml_html.fromstring(html)
    except Exception:
        return []

    images: list[dict[str, Any]] = []
    for img in doc.xpath(".//img"):
        src = img.get("src", "").strip()
        if not src:
            continue
        if base_url:
            src = urljoin(base_url, src)
        alt = img.get("alt", "").strip()

        # Look for figure/figcaption
        caption = ""
        parent = img.getparent()
        if parent is not None and parent.tag == "a":
            parent = parent.getparent()
        if parent is not None and parent.tag == "figure":
            figcap = parent.findtext(".//figcaption", "").strip()
            if figcap:
                caption = figcap

        images.append({"src": src, "alt": alt, "caption": caption or alt})

    return images


def _strip_images_from_html(html: str) -> str:
    """Remove img/picture/source/svg/canvas, keep alt text as inline text."""
    try:
        root = lxml_html.fromstring(html)
    except Exception:
        return re.sub(r"<img[^>]*>", "", html, flags=re.IGNORECASE)

    for img in root.xpath(".//img"):
        alt = (img.get("alt") or "").strip()
        parent = img.getparent()
        if parent is not None:
            if alt:
                # Replace img with its alt text
                parent.replace(img, lxml_html.Element("span"))
                # Set text content
                img.getparent().text = f"[{alt}]"
            else:
                parent.remove(img)

    _remove_nodes(root, ".//picture | .//source | .//svg | .//canvas")
    return lxml_html.tostring(root, encoding="unicode", method="html")


def _render_full_view(html: str, output_format: str, render_images: bool) -> str:
    """Render full page content using markdownify."""
    body = _extract_body_node(html)
    if body is None:
        return ""

    # Remove script/style/noscript/template
    _remove_nodes(body, ".//script | .//style | .//noscript | .//template")

    if not render_images:
        _remove_nodes(body, ".//img | .//picture | .//source | .//svg | .//canvas")

    body_html = lxml_html.tostring(body, encoding="unicode", method="html")

    if output_format == "html":
        return body_html

    try:
        return markdownify(body_html, heading_style="ATX", bullets="-").strip()
    except Exception:
        return _extract_body_text(body_html) or trafilatura.html2txt(body_html) or ""


def _render_article_view(html: str, output_format: str, render_images: bool) -> str:
    """Render article main content using trafilatura."""
    kwargs: dict[str, Any] = {
        "output_format": output_format,
        "include_comments": False,
        "include_tables": True,
        "include_images": render_images,
        "include_links": True,
        "include_formatting": output_format == "markdown",
        "deduplicate": True,
        "favor_precision": False,
        "favor_recall": True,
    }

    extracted = trafilatura.extract(html, **kwargs)
    if extracted:
        return extracted

    # Fallback chain
    fallback_kwargs = {**kwargs, "fast": True}
    extracted = trafilatura.extract(html, **fallback_kwargs)
    if extracted:
        return extracted

    postbody, baseline_text, _ = trafilatura.baseline(html)
    if baseline_text:
        if output_format == "html" and postbody is not None:
            return lxml_html.tostring(postbody, encoding="unicode")
        return baseline_text

    if output_format == "html":
        return html

    fallback_text = trafilatura.html2txt(html)
    return fallback_text or ""


def _embed_images_in_result(
    result: str,
    original_html: str,
    base_url: str | None,
    output_format: str,
) -> str:
    """Download images and embed as base64 data URIs in the rendered result."""
    images = _collect_images_from_html(original_html, base_url)
    if not images:
        return result

    # Build a mapping: original URL → data URI
    uri_map: dict[str, str] = {}
    for img in images:
        if img["src"] in uri_map:
            continue
        b64, mime = _download_image_as_base64(img["src"])
        if b64:
            uri_map[img["src"]] = f"data:{mime};base64,{b64}"
        else:
            uri_map[img["src"]] = img["src"]  # keep original on failure

    if output_format == "markdown":
        # Replace ![alt](url) patterns
        def _replace_md(match: re.Match[str]) -> str:
            alt = match.group(1)
            url = match.group(2).strip()
            resolved = uri_map.get(url, url)
            return f"![{alt}]({resolved})"

        result = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _replace_md, result)

    return result


def render_view(
    html: str,
    view_config: ViewConfig,
    base_url: str | None = None,
) -> str:
    """Render HTML to text/markdown/html based on the given render configuration.

    Args:
        html: The raw HTML content.
        view_config: Rendering configuration (output_format, markdown_engine).
        base_url: Base URL for resolving relative image URLs.

    Returns:
        Rendered text content.
    """
    html = _normalize_html_input(html)
    if _is_empty_html(html):
        return ""

    engine = view_config.markdown_engine
    output_format = view_config.output_format

    if engine == "full":
        result = _render_full_view(html, output_format, view_config.render_images)
    else:
        result = _render_article_view(html, output_format, view_config.render_images)

    if view_config.render_images and result:
        result = _embed_images_in_result(result, html, base_url, output_format)

    return result


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


_SKIPPED_PROTOCOLS = {"javascript:", "mailto:", "tel:", "data:", "sms:", "fax:", "file:"}


def _is_skipped_href(href: str) -> bool:
    """Check if this href should be skipped (non-http protocols or fragment-only)."""
    stripped = href.strip()
    if not stripped:
        return True
    if stripped.startswith("#"):
        return True
    lower = stripped.lower()
    for proto in _SKIPPED_PROTOCOLS:
        if lower.startswith(proto):
            return True
    return False


def _make_relative_href(url: str, base: str) -> str:
    """If url is same-origin as base, return a path-relative href; otherwise return absolute."""
    u = urlparse(url)
    b = urlparse(base)
    if u.scheme == b.scheme and u.netloc == b.netloc:
        result = urlunparse(("", "", u.path, u.params, u.query, u.fragment))
        return result or "/"
    return url


def _get_link_text(a_node) -> str:
    """Get the visible text for a link anchor.

    Returns the text content, or the alt text of a child image if the link contains one.
    """
    # Check if the link contains only an image
    children = a_node.getchildren()
    if len(children) == 1 and children[0].tag == "img":
        alt = (children[0].get("alt") or "").strip()
        if alt:
            return alt
    return (a_node.text_content() or "").strip()


def extract_links(
    html: str,
    base_url: str | None,
    rendered_text: str,
    limit: int = MAX_LINKS_COUNT,
) -> Dict[str, Any]:
    """Extract all external links from HTML, deduplicate, and filter against rendered text.

    Args:
        html: Raw HTML content.
        base_url: Base URL for resolving relative links.
        rendered_text: Rendered page text used for dedup (links already visible in text are excluded).
        limit: Maximum number of links to return.

    Returns:
        Dict with "links", "links_total", "links_truncated" keys.
    """
    if not html or not html.strip():
        return {"links": [], "links_total": 0, "links_truncated": False}

    body = _extract_body_node(html)
    if body is None:
        return {"links": [], "links_total": 0, "links_truncated": False}

    seen_abs: set[str] = set()
    collected: list[dict[str, str]] = []
    base = base_url or ""

    for a in body.xpath(".//a[@href]"):
        raw_href = a.get("href", "").strip()
        if _is_skipped_href(raw_href):
            continue

        abs_url = urljoin(base, raw_href)
        if not abs_url or abs_url in seen_abs:
            continue
        seen_abs.add(abs_url)

        # Filter: if abs_url appears in rendered text, skip
        if abs_url in rendered_text:
            continue

        text = _get_link_text(a)
        href = _make_relative_href(abs_url, base) if base else abs_url

        collected.append({
            "href": href,
            "text": text,
            "abs_url": abs_url,
        })

    total = len(collected)
    truncated = total > limit
    links = collected[:limit]

    return {
        "links": links,
        "links_total": total,
        "links_truncated": truncated,
    }
