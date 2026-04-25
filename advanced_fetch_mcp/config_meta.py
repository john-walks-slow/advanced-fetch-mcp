from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnvVarSpec:
    name: str
    default: str
    section: str
    description_zh: str
    description_en: str
    note_zh: str = ""
    note_en: str = ""
    example_comment: str = ""


SECTION_TITLES = {
    "core": "Core timeouts",
    "auto_wait": "Auto-wait (content stability detection)",
    "extraction": "Extraction / LLM",
    "browser": "Browser / session",
    "proxy": "Proxy",
    "env_loading": "Env loading",
    "misc": "Misc",
}


ENV_VAR_SPECS: tuple[EnvVarSpec, ...] = (
    EnvVarSpec("FETCH_TIMEOUT", "30", "core", "抓取总超时秒数。", "Total fetch timeout in seconds."),
    EnvVarSpec(
        "PER_SITE_RATE_LIMIT_SECONDS",
        "1.0",
        "core",
        "同一 hostname 的最小抓取间隔秒数。",
        "Minimum interval in seconds between requests to the same hostname.",
        note_zh="设为 `0` 可关闭。串行时会附带一个很小的随机 jitter，避免请求节奏过于固定。",
        note_en="Set to `0` to disable it. Serialized requests include a small random jitter to avoid an overly regular access pattern.",
    ),
    EnvVarSpec(
        "AUTO_WAIT_POLL_INTERVAL",
        "0.25",
        "auto_wait",
        "动态抓取时的稳定性检测轮询间隔（秒）。",
        "Polling interval in seconds for dynamic-content stability detection.",
        example_comment="Poll interval in seconds (default: 0.25)",
    ),
    EnvVarSpec(
        "AUTO_WAIT_MIN_STABLE_SECONDS",
        "5.0",
        "auto_wait",
        "动态抓取时等待内容稳定的最小时长（秒）。",
        "Minimum stable duration in seconds for dynamic fetch.",
        example_comment="Minimum stable duration in seconds (default: 5.0)",
    ),
    EnvVarSpec(
        "AUTO_WAIT_MIN_CONTENT_LENGTH",
        "150",
        "auto_wait",
        "动态抓取时的最小内容长度阈值。内容稳定且长度达到此阈值时提前结束等待。",
        "Minimum content length threshold for dynamic fetch. When content is stable and reaches this length, exit early.",
        example_comment="Minimum content length for early exit (default: 150)",
    ),
    EnvVarSpec(
        "AUTO_WAIT_SAMPLE_EDGE_CHARS",
        "200",
        "auto_wait",
        "稳定性检测时用于对比的首尾字符数。",
        "Number of leading and trailing characters compared during stability detection.",
        example_comment="Edge chars to compare for stability (default: 200)",
    ),
    EnvVarSpec("DEFAULT_MAX_LENGTH", "8000", "extraction", "默认返回长度上限。", "Default max output length."),
    EnvVarSpec(
        "ENABLE_PROMPT_EXTRACTION",
        "false",
        "extraction",
        "是否启用 `sampling`。",
        "Whether `sampling` is enabled.",
        note_zh="实验性功能。支持 sampling 的客户端包括 VS Code GitHub Copilot、goose、Amp、Glama、Joey、fast-agent、mcp-use、Postman 等。",
        note_en="Experimental feature. Supported by VS Code GitHub Copilot, goose, Amp, Glama, Joey, fast-agent, mcp-use, Postman, etc.",
    ),
    EnvVarSpec("PROMPT_INPUT_MAX_CHARS", "64000", "extraction", "传给 LLM 的最大输入字符数。", "Max input size passed to the LLM."),
    EnvVarSpec("MAX_FIND_MATCHES", "12", "extraction", "页内搜索最多返回多少条命中。", "Maximum number of page-search matches to return."),
    EnvVarSpec("FIND_SNIPPET_MAX_CHARS", "240", "extraction", "每条搜索命中的片段长度上限。", "Max snippet length for each search match."),
    EnvVarSpec(
        "SCHEMA_LANGUAGE",
        "zh",
        "extraction",
        "schema 描述语言。",
        "Schema description language.",
        note_zh="支持 `zh` / `en`。",
        note_en="Supported values: `zh` / `en`.",
        example_comment="Schema language: zh / en",
    ),
    EnvVarSpec(
        "BROWSER_CHANNEL",
        "chrome",
        "browser",
        "传给 Playwright 的浏览器 channel。",
        "Browser channel passed to Playwright.",
        note_zh="可选值包括 `chrome`、`chrome-beta`、`chrome-dev`、`msedge`、`msedge-beta`、`msedge-dev`、`chromium`。",
        note_en="Allowed values include `chrome`, `chrome-beta`, `chrome-dev`, `msedge`, `msedge-beta`, `msedge-dev`, and `chromium`.",
        example_comment="chrome / msedge / chromium",
    ),
    EnvVarSpec(
        "BROWSER_SESSION_MODE",
        "auth",
        "browser",
        "浏览器会话模式。",
        "Browser session mode.",
        note_zh="可选 `auth` 或 `profile`，默认推荐 `auth`。",
        note_en="Use `auth` or `profile`. `auth` is the default and recommended mode.",
        example_comment="auth (recommended) / profile (legacy)",
    ),
    EnvVarSpec(
        "BROWSER_AUTH_STORAGE_STATE",
        "~/.advanced-fetch-auth/storage_state.json",
        "browser",
        "`auth` 模式下 `storage_state.json` 的路径。",
        "Path to `storage_state.json` in `auth` mode.",
        example_comment="auth mode storage",
    ),
    EnvVarSpec(
        "BROWSER_PROFILE_DIR",
        "~/.advanced-fetch-profile",
        "browser",
        "`profile` 模式下 persistent profile 的目录。",
        "Persistent profile directory in `profile` mode.",
        example_comment="profile mode dir (only used if BROWSER_SESSION_MODE=profile)",
    ),
    EnvVarSpec(
        "BROWSER_LOCALE",
        "",
        "browser",
        "浏览器 locale。",
        "Browser locale.",
        note_zh="留空则使用系统默认。",
        note_en="Leave empty to use the system default.",
        example_comment="Leave empty to use system defaults",
    ),
    EnvVarSpec(
        "BROWSER_TIMEZONE_ID",
        "",
        "browser",
        "浏览器时区。",
        "Browser timezone.",
        note_zh="留空则使用系统默认。",
        note_en="Leave empty to use the system default.",
    ),
    EnvVarSpec("BROWSER_COLOR_SCHEME", "light", "browser", "颜色方案。", "Color scheme."),
    EnvVarSpec("BROWSER_VIEWPORT_WIDTH", "1366", "browser", "viewport 宽度。", "Viewport width."),
    EnvVarSpec("BROWSER_VIEWPORT_HEIGHT", "768", "browser", "viewport 高度。", "Viewport height."),
    EnvVarSpec("ENABLE_AUTH_STEALTH", "true", "browser", "是否在 `auth` 模式启用 stealth。", "Whether to enable stealth in `auth` mode."),
    EnvVarSpec(
        "INTERVENTION_TIMEOUT_SECONDS",
        "600",
        "browser",
        "用户人工介入等待超时秒数。",
        "Timeout in seconds for manual user intervention.",
    ),
    EnvVarSpec("ENABLE_PROXY", "true", "proxy", "是否启用代理。", "Whether proxy support is enabled."),
    EnvVarSpec("HTTP_PROXY", "", "proxy", "HTTP 代理地址。", "HTTP proxy address."),
    EnvVarSpec("HTTPS_PROXY", "", "proxy", "HTTPS 代理地址。", "HTTPS proxy address."),
    EnvVarSpec("NO_PROXY", "", "proxy", "代理绕过列表。", "Proxy bypass list."),
    EnvVarSpec(
        "ADVANCED_FETCH_ENV_FILE",
        "",
        "env_loading",
        "显式指定 dotenv 文件路径。",
        "Explicitly specify a dotenv file path.",
        example_comment="Optional: explicitly specify env file path",
    ),
    EnvVarSpec(
        "IGNORE_SSL_ERRORS",
        "false",
        "misc",
        "是否忽略 HTTPS / SSL 证书错误。",
        "Whether to ignore HTTPS / SSL certificate errors.",
        example_comment="Ignore HTTPS certificate errors",
    ),
)


ENV_VAR_NAMES = tuple(spec.name for spec in ENV_VAR_SPECS)
ENV_VAR_BY_NAME = {spec.name: spec for spec in ENV_VAR_SPECS}


def env_default(name: str) -> str:
    return ENV_VAR_BY_NAME[name].default
