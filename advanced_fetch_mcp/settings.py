import logging
import os
from pathlib import Path
from typing import Literal, Optional
from urllib.parse import urlparse

import urllib3

from .config_meta import env_default


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def env_float(name: str, default: float, *, minimum: float) -> float:
    raw = os.getenv(name)
    value = default if raw is None else float(raw)
    return max(minimum, value)


def env_optional_str(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def env_choice(name: str, default: str, allowed: set[str]) -> str:
    value = (os.getenv(name, default) or default).strip().lower()
    return value if value in allowed else default


def seconds_to_ms(seconds: float) -> int:
    return max(1, int(seconds * 1000))


def _split_no_proxy_entries(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    normalized = raw.replace(";", ",")
    return [entry.strip() for entry in normalized.split(",") if entry.strip()]


def _normalize_no_proxy(raw: Optional[str]) -> Optional[str]:
    entries = _split_no_proxy_entries(raw)
    return ",".join(entries) or None


def _strip_host_port(entry: str) -> str:
    value = entry.strip()
    if not value:
        return ""
    if value.startswith("["):
        end = value.find("]")
        return value[1:end] if end != -1 else value
    if value.count(":") == 1 and "." in value:
        return value.rsplit(":", 1)[0]
    return value


def _host_matches_no_proxy(host: str, pattern: str) -> bool:
    candidate = _strip_host_port(pattern).lower().lstrip()
    if not candidate:
        return False
    if candidate == "*":
        return True
    if candidate.startswith("."):
        suffix = candidate[1:]
        return host == suffix or host.endswith(candidate)
    return host == candidate or host.endswith("." + candidate)


def should_bypass_proxy(url: str) -> bool:
    host = (urlparse(url).hostname or "").strip().lower()
    if not host:
        return False
    return any(_host_matches_no_proxy(host, entry) for entry in _split_no_proxy_entries(get_no_proxy()))


def get_proxy_url() -> Optional[str]:
    if not env_flag("ENABLE_PROXY", True):
        return None
    return (
        os.getenv("HTTPS_PROXY")
        or os.getenv("https_proxy")
        or os.getenv("HTTP_PROXY")
        or os.getenv("http_proxy")
    ) or None


def get_no_proxy() -> Optional[str]:
    raw = os.getenv("NO_PROXY") or os.getenv("no_proxy") or None
    return _normalize_no_proxy(raw)


def get_requests_proxies(url: Optional[str] = None) -> Optional[dict[str, str]]:
    proxy_url = get_proxy_url()
    if not proxy_url:
        return None
    if url and should_bypass_proxy(url):
        return None
    return {"http": proxy_url, "https": proxy_url}


def _env_session_mode() -> Literal["auth", "profile"]:
    default_mode = env_default("BROWSER_SESSION_MODE")
    raw = (os.getenv("BROWSER_SESSION_MODE", default_mode) or default_mode).strip().lower()
    if raw in {"auth", "profile"}:
        return raw
    return default_mode


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MAX_LENGTH = int(os.getenv("DEFAULT_MAX_LENGTH", env_default("DEFAULT_MAX_LENGTH")))
INTERVENTION_TIMEOUT_SECONDS = int(os.getenv("INTERVENTION_TIMEOUT_SECONDS", env_default("INTERVENTION_TIMEOUT_SECONDS")))
INTERVENTION_BUTTON_ID = "advanced-fetch-intervention-done"

FETCH_TIMEOUT_SECONDS = env_float("FETCH_TIMEOUT", float(env_default("FETCH_TIMEOUT")), minimum=1.0)
PER_SITE_RATE_LIMIT_SECONDS = env_float("PER_SITE_RATE_LIMIT_SECONDS", float(env_default("PER_SITE_RATE_LIMIT_SECONDS")), minimum=0.0)
IGNORE_SSL_ERRORS = env_flag("IGNORE_SSL_ERRORS", env_default("IGNORE_SSL_ERRORS") == "true")

AUTO_WAIT_POLL_INTERVAL_SECONDS = env_float("AUTO_WAIT_POLL_INTERVAL", float(env_default("AUTO_WAIT_POLL_INTERVAL")), minimum=0.05)
AUTO_WAIT_MIN_STABLE_SECONDS = env_float("AUTO_WAIT_MIN_STABLE_SECONDS", float(env_default("AUTO_WAIT_MIN_STABLE_SECONDS")), minimum=0.1)
AUTO_WAIT_MIN_CONTENT_LENGTH = int(os.getenv("AUTO_WAIT_MIN_CONTENT_LENGTH", env_default("AUTO_WAIT_MIN_CONTENT_LENGTH")))
AUTO_WAIT_SAMPLE_EDGE_CHARS = int(os.getenv("AUTO_WAIT_SAMPLE_EDGE_CHARS", env_default("AUTO_WAIT_SAMPLE_EDGE_CHARS")))

if IGNORE_SSL_ERRORS:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ENABLE_PROMPT_EXTRACTION = env_flag("ENABLE_PROMPT_EXTRACTION", env_default("ENABLE_PROMPT_EXTRACTION") == "true")
PROMPT_INPUT_MAX_CHARS = int(os.getenv("PROMPT_INPUT_MAX_CHARS", env_default("PROMPT_INPUT_MAX_CHARS")))
MAX_FIND_MATCHES = int(os.getenv("MAX_FIND_MATCHES", env_default("MAX_FIND_MATCHES")))
FIND_SNIPPET_MAX_CHARS = int(os.getenv("FIND_SNIPPET_MAX_CHARS", env_default("FIND_SNIPPET_MAX_CHARS")))
SCHEMA_LANGUAGE = env_choice("SCHEMA_LANGUAGE", env_default("SCHEMA_LANGUAGE"), {"zh", "en"})

BROWSER_CHANNEL = env_choice(
    "BROWSER_CHANNEL",
    env_default("BROWSER_CHANNEL"),
    {"chrome", "chrome-beta", "chrome-dev", "msedge", "msedge-beta", "msedge-dev", "chromium"},
)
BROWSER_SESSION_MODE = _env_session_mode()
BROWSER_PROFILE_DIR = Path(
    os.getenv(
        "BROWSER_PROFILE_DIR",
        env_default("BROWSER_PROFILE_DIR"),
    )
).expanduser()
AUTH_STORAGE_STATE_PATH = Path(
    os.getenv(
        "BROWSER_AUTH_STORAGE_STATE",
        env_default("BROWSER_AUTH_STORAGE_STATE"),
    )
).expanduser()
BROWSER_LOCALE = env_optional_str("BROWSER_LOCALE")
BROWSER_TIMEZONE_ID = env_optional_str("BROWSER_TIMEZONE_ID")
BROWSER_COLOR_SCHEME = os.getenv("BROWSER_COLOR_SCHEME", env_default("BROWSER_COLOR_SCHEME")).strip() or env_default("BROWSER_COLOR_SCHEME")
BROWSER_VIEWPORT_WIDTH = max(320, int(os.getenv("BROWSER_VIEWPORT_WIDTH", env_default("BROWSER_VIEWPORT_WIDTH"))))
BROWSER_VIEWPORT_HEIGHT = max(320, int(os.getenv("BROWSER_VIEWPORT_HEIGHT", env_default("BROWSER_VIEWPORT_HEIGHT"))))
ENABLE_AUTH_STEALTH = env_flag("ENABLE_AUTH_STEALTH", env_default("ENABLE_AUTH_STEALTH") == "true")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0"
)
CORE_REMOVE_TAGS = ["script", "style", "head", "noscript", "template"]
MEDIA_REMOVE_TAGS = ["video", "audio", "img", "canvas", "svg", "picture", "source"]

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
logger = logging.getLogger("AdvancedFetchMCP")

if BROWSER_SESSION_MODE == "profile":
    logger.warning(
        "[Browser] 当前 BROWSER_SESSION_MODE=profile。该模式仅为兼容保留，不推荐使用，且不会启用 stealth。"
    )
