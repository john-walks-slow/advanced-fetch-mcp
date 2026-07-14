from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse, urlunparse

__all__ = [
    "is_same_origin",
    "is_skipped_href",
    "make_relative_url",
    "normalize_html_urls",
    "normalize_markdown_urls",
]

_SKIPPED_PROTOCOLS = {"javascript:", "mailto:", "tel:", "data:", "sms:", "fax:", "file:"}

# Match src="https://..." and href="https://..."
_RE_HTML_SRC_HREF = re.compile(
    r"""\b(?P<attr>src|href)\s*=\s*["'](?P<url>https?://[^"']+)["']""",
    re.IGNORECASE,
)

# Match srcset="..."
_RE_HTML_SRCSET = re.compile(
    r"""\bsrcset\s*=\s*["'](?P<value>[^"']+)["']""",
    re.IGNORECASE,
)

# Match individual URLs inside srcset value
_RE_SRCSET_URL = re.compile(r"https?://\S+", re.IGNORECASE)

# Match markdown links [text](url) and images ![alt](url)
_RE_MARKDOWN_URL = re.compile(
    r"(?P<image>!)?\[(?P<text>[^\]]*)\]\((?P<url>[^)]+)\)"
)


def is_same_origin(url: str, base: str) -> bool:
    """Check if url and base share the same scheme and netloc (case-insensitive for host)."""
    u = urlparse(url)
    b = urlparse(base)
    return u.scheme == b.scheme and u.netloc.lower() == b.netloc.lower()


def is_skipped_href(href: str) -> bool:
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


def make_relative_url(url: str, base: str) -> str:
    """If url is same-origin as base, return a path-relative URL; otherwise return absolute."""
    if not base:
        return url
    u = urlparse(url)
    b = urlparse(base)
    if u.scheme == b.scheme and u.netloc == b.netloc:
        result = urlunparse(("", "", u.path, u.params, u.query, u.fragment))
        return result or "/"
    return url


def _replace_src_href(match: re.Match, base: str) -> str:
    """Callback for _RE_HTML_SRC_HREF substitutions."""
    attr = match.group("attr")
    url = match.group("url")
    resolved = urljoin(base, url)
    if is_same_origin(resolved, base):
        return f'{attr}="{make_relative_url(resolved, base)}"'
    return match.group(0)


def _replace_srcset(match: re.Match, base: str) -> str:
    """Callback for _RE_HTML_SRCSET substitutions."""
    value = match.group("value")

    def _replace_url(m: re.Match) -> str:
        url = m.group(0)
        resolved = urljoin(base, url)
        if is_same_origin(resolved, base):
            return make_relative_url(resolved, base)
        return url

    new_value = _RE_SRCSET_URL.sub(_replace_url, value)
    return f'srcset="{new_value}"'


def normalize_html_urls(html: str, base: str) -> str:
    """Rewrite absolute URLs in HTML src/href/srcset to relative when same-origin with base.

    Handles <img src/srcset>, <a href>, <video src>, <audio src>,
    <source src>, <iframe src>, <link href> and similar attributes.
    """
    if not base or not html:
        return html

    html = _RE_HTML_SRC_HREF.sub(lambda m: _replace_src_href(m, base), html)
    html = _RE_HTML_SRCSET.sub(lambda m: _replace_srcset(m, base), html)
    return html


def normalize_markdown_urls(text: str, base: str) -> str:
    """Rewrite markdown link/image URLs to relative when same-origin with base.

    Handles [text](url) and ![alt](url) syntax.
    """
    if not base or not text:
        return text

    def _replace(m: re.Match) -> str:
        url = m.group("url").strip()
        if not url.startswith(("http://", "https://")):
            return m.group(0)
        resolved = urljoin(base, url)
        if is_same_origin(resolved, base):
            relative = make_relative_url(resolved, base)
            prefix = "!" if m.group("image") else ""
            text_content = m.group("text")
            return f"{prefix}[{text_content}]({relative})"
        return m.group(0)

    return _RE_MARKDOWN_URL.sub(_replace, text)
