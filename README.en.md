# advanced-fetch-mcp

[中文](README.md) | English

Provides an easy-to-use, powerful, and token-efficient web fetching tool for agents.
More capable than vanilla fetch, simpler than using Playwright directly.

## Features

- **Main-content extraction**: Built on top of trafilatura with configurable extraction strategy and scope, removing as much noise as possible to save tokens.
- **Dynamic website support**: Uses Playwright to fetch dynamic websites and detect when the page becomes stable.
- **LLM Sampling**: Use `sampling.prompt` to refine page content and return a condensed result, avoiding raw page content polluting the caller context.
- **Chunked reading for large pages**: Supports `find.query` for searching within a page, and uses `render.cursor` plus top-level `max_length` to continue reading from any position.
- **Manual intervention and auth**: `fetch.require_user_intervention=true` opens a visible browser so the user can finish login, CAPTCHA, or manual actions before continuing. Once logged in, later requests can reuse the saved auth state.
- **Anti-bot masking**: Includes Playwright-Stealth to imitate real browser behavior as much as possible and reduce bot detection.
- **Proxy support**: Supports `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY`.
- **Per-site rate limiting**: Configure `PER_SITE_RATE_LIMIT_SECONDS` to enforce a minimum interval between requests to the same hostname.

## MCP Client Configuration

```json
{
  "mcpServers": {
    "advanced-fetch": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/john-walks-slow/advanced-fetch-mcp",
        "advanced-fetch-mcp"
      ],
      "env": {
        "SCHEMA_LANGUAGE": "en"
      }
    }
  }
}
```

## Schema

### 1. Top-level parameters

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `url` | `string` | Required | Full URL of the target webpage. |
| `operation` | `"view" \| "find" \| "sampling" \| "eval"` | `"view"` | Operation: view, in-page search, LLM extraction, or JS execution. |
| `fetch` | `object` | See below | Page fetching mode and wait-strategy configuration. |
| `render` | `object` | See below | Main-content extraction, output-format, and continue-read configuration. |
| `max_length` | `integer` | `8000` | Maximum result length. |
| `find` | `object \| null` | `null` | Find configuration. Provide only when operation="find". |
| `sampling` | `object \| null` | `null` | Sampling configuration. Provide only when operation="sampling". |
| `eval` | `object \| null` | `null` | Script configuration. Provide only when operation="eval". |

### 2. `fetch` object

| Path | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `fetch.mode` | `"dynamic" \| "static"` | `"dynamic"` | Fetch mode: dynamic uses a browser; static requests source HTML directly. |
| `fetch.min_stable_seconds` | `number` | `5.0` | Minimum stable duration in seconds for dynamic fetch. |
| `fetch.min_content_length` | `integer` | `150` | Dynamic fetch requires content length to reach this value and stable duration to succeed. |
| `fetch.timeout` | `number` | `30.0` | Fetch timeout in seconds. On timeout, return the content obtained so far. |
| `fetch.require_user_intervention` | `boolean` | `false` | Use for login, CAPTCHA, or manual page actions. |

### 3. `render` object

| Path | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `render.engine` | `"trafilatura" \| "markdownify"` | `"trafilatura"` | Extraction engine. trafilatura works best for articles/main content; use markdownify for complex pages where broader page content is needed. |
| `render.output_format` | `"markdown" \| "html"` | `"markdown"` | Main-content output format. |
| `render.strategy` | `"default" \| "strict" \| "loose"` | `"default"` | trafilatura-only strategy: strict is cleaner; loose keeps more content. |
| `render.include_elements` | `Array<"comments" \| "tables" \| "images" \| "links" \| "formatting">` | `["tables", "formatting"]` | Extra content types to keep, such as tables, links, and images. |
| `render.cursor` | `integer \| null` | `null` | Text start offset used only to continue reading long pages. |

### 4. `find` object

| Path | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `find.query` | `string` | Required | Text or regular expression to search for. |
| `find.regex` | `boolean` | `false` | Whether to treat query as a regular expression. |
| `find.limit` | `integer` | `12` | Maximum number of matches to return for this request. |
| `find.snippet_max_chars` | `integer` | `240` | Maximum snippet length for each returned match. |
| `find.start_index` | `integer` | `0` | Zero-based match index to start returning from. 0 means the first match. |

### 5. `sampling` object

| Path | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `sampling.prompt` | `string` | Required | Prompt that guides the LLM to extract information from the page main content. |
| `sampling.model` | `string \| null` | `null` | Preferred model name. |

### 6. `eval` object

| Path | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `eval.script` | `string` | Required | JavaScript code executed in the page context. Supported only in dynamic mode. |

### 7. Constraints

| Rule | Description |
| :--- | :--- |
| Operation-specific config | The `find`, `sampling`, or `eval` object may only be provided when `operation` matches, and they are mutually exclusive. |
| `eval` mode restriction | When `operation="eval"`, `fetch.mode` must be `"dynamic"`. |
| `max_length` scope | Applies to `view`, `find`, `sampling`, and `eval`, limiting the final returned result. |
| `render.cursor` scope | Only valid for `view`. Used to continue reading from a previous `next_cursor` position. |
| Continue-read consistency | When continuing with `cursor`, keep `output_format` and `strategy` unchanged, otherwise the offset may become invalid. |


## Response format

### Common response shape

```json
{
  "success": true,
  "final_url": "https://example.com/final",
  "result": "...",
  "cache_hit": true,
  "timed_out": true,
  "timeout_stage": "network_idle",
  "intervention_ended_by": "timeout",
  "truncated": true,
  "next_cursor": 8000,
  "warnings": ["..."]
}
```

### Common fields

| Field | Type | Always present | Description |
| :--- | :--- | :--- | :--- |
| `success` | `boolean` | Yes | Always `true` on success. |
| `final_url` | `string` | Yes | Final page URL, which may differ from the input `url`. |
| `result` | `string` | Yes | Primary return payload. For `view`/`sampling`/`eval`, this is the text result; for `find`, it is currently always an empty string. |
| `cache_hit` | `boolean` | No | Present when a cached fetch result was reused. |
| `timed_out` | `boolean` | No | Present when a timeout occurred during fetching. |
| `timeout_stage` | `string` | No | Stage where the timeout occurred. |
| `intervention_ended_by` | `string` | No | Why manual intervention ended, for example `timeout` or `page_closed`. |
| `truncated` | `boolean` | No | Present when the returned content was truncated by `max_length`. |
| `next_cursor` | `integer` | No | Returned when more content can be read or searched from a later offset. |
| `warnings` | `string[]` | No | Warning messages. |

### `view` response

```json
{
  "success": true,
  "final_url": "https://example.com/final",
  "result": "A window of the extracted page text",
  "truncated": true,
  "next_cursor": 8000
}
```

Notes:
- `result` contains the current text window.
- When there is more text to read, `next_cursor` is returned.

### `find` response

```json
{
  "success": true,
  "final_url": "https://example.com/final",
  "result": "",
  "found": true,
  "matches": [
    {
      "snippet": "...text around the match...",
      "cursor": 1234
    }
  ],
  "matches_total": 3,
  "matches_truncated": false,
  "next_cursor": 1234
}
```

### `find`-specific fields

| Field | Type | Description |
| :--- | :--- | :--- |
| `found` | `boolean` | Whether any match was found. |
| `matches` | `object[]` | List of match summaries. |
| `matches_total` | `integer` | Total number of matches found. |
| `matches_truncated` | `boolean` | Whether the returned match summaries were truncated because there were too many matches. |

### `find.matches` item shape

| Field | Type | Description |
| :--- | :--- | :--- |
| `snippet` | `string` | Text snippet around the match. |
| `cursor` | `integer` | Offset that can be used later as `render.cursor` to continue reading. |

### `sampling` response

```json
{
  "success": true,
  "final_url": "https://example.com/final",
  "result": "Refined extraction result",
  "truncated": true
}
```

Notes:
- `result` is the LLM-refined text result.
- If sampling fails, it falls back to the raw rendered text and explains that in `warnings`.

### `eval` response

```json
{
  "success": true,
  "final_url": "https://example.com/final",
  "result": "{\n  \"title\": \"Example\"\n}",
  "truncated": false
}
```

Notes:
- `result` is the stringified script execution result.
- If the script returns an object, array, boolean, or number, it is serialized to a JSON string before being returned.

## Examples

Fetch the main content:

```yaml
url: https://example.com
operation: view
```

Keep more content (`loose` strategy):

```yaml
url: https://example.com
operation: view
render:
  strategy: loose
```

Keep links and images:

```yaml
url: https://example.com
operation: view
render:
  include_elements:
    - tables
    - formatting
    - links
    - images
```

Wait 5 extra seconds:

```yaml
url: https://example.com
operation: view
fetch:
  wait_for: 5
```

Search for a keyword:

```yaml
url: https://example.com
operation: find
find:
  query: price
```

Continue reading from a search position:

```yaml
url: https://example.com
operation: view
max_length: 300
render:
  cursor: 300 # assume this is a cursor returned from a previous match
```

Use sampling to refine the result:

```yaml
url: https://example.com
operation: sampling
sampling:
  prompt: Extract the product name and price
```

Execute in-page JavaScript:

```yaml
url: https://example.com
operation: eval
fetch:
  mode: dynamic
eval:
  script: |
    () => ({
      title: document.title,
      href: location.href,
      itemCount: document.querySelectorAll('.item').length
    })
```

A site that requires login:

```yaml
url: https://private-site.com
operation: view
fetch:
  require_user_intervention: true
```

## Session Modes

Browser session behavior is controlled by `BROWSER_SESSION_MODE`:

- `auth`: default and recommended. Uses a normal browser/context and saves auth state through `storage_state.json`; stealth is enabled when available.
- `profile`: compatibility mode, not recommended. Uses a persistent profile (`user_data_dir`) and does not enable stealth.

In most cases, the default `auth` mode is the right choice.

## Cache

Fetched pages are cached by `url + fetch.mode`. The cache is reused later when searching, jumping, or continuing within the same page.

## Environment Variables

### General

- `FETCH_TIMEOUT`: Total fetch timeout in seconds. Default: `30`.
- `PER_SITE_RATE_LIMIT_SECONDS`: Minimum interval in seconds between requests to the same hostname. Default: `1.0`. Set to `0` to disable it. Serialized requests include a small random jitter to avoid an overly regular access pattern.

### Auto-wait

- `AUTO_WAIT_POLL_INTERVAL`: Polling interval in seconds for dynamic-content stability detection. Default: `0.25`.
- `AUTO_WAIT_MIN_STABLE_SECONDS`: Minimum stable duration in seconds for dynamic fetch. Default: `5.0`.
- `AUTO_WAIT_MIN_CONTENT_LENGTH`: Minimum content length threshold for dynamic fetch. When content is stable and reaches this length, exit early. Default: `150`.
- `AUTO_WAIT_SAMPLE_EDGE_CHARS`: Number of leading and trailing characters compared during stability detection. Default: `200`.

### Extraction / LLM

- `DEFAULT_MAX_LENGTH`: Default max output length. Default: `8000`.
- `ENABLE_PROMPT_EXTRACTION`: Whether `sampling` is enabled. Default: `true`.
- `PROMPT_INPUT_MAX_CHARS`: Max input size passed to the LLM. Default: `64000`.
- `MAX_FIND_MATCHES`: Maximum number of page-search matches to return. Default: `12`.
- `FIND_SNIPPET_MAX_CHARS`: Max snippet length for each search match. Default: `240`.
- `SCHEMA_LANGUAGE`: Schema description language. Default: `zh`. Supported values: `zh` / `en`.

### Browser / Session

- `BROWSER_CHANNEL`: Browser channel passed to Playwright. Default: `chrome`. Allowed values include `chrome`, `chrome-beta`, `chrome-dev`, `msedge`, `msedge-beta`, `msedge-dev`, and `chromium`.
- `BROWSER_SESSION_MODE`: Browser session mode. Default: `auth`. Use `auth` or `profile`. `auth` is the default and recommended mode.
- `BROWSER_AUTH_STORAGE_STATE`: Path to `storage_state.json` in `auth` mode. Default: `~/.advanced-fetch-auth/storage_state.json`.
- `BROWSER_PROFILE_DIR`: Persistent profile directory in `profile` mode. Default: `~/.advanced-fetch-profile`.
- `BROWSER_LOCALE`: Browser locale. Default: empty string. Leave empty to use the system default.
- `BROWSER_TIMEZONE_ID`: Browser timezone. Default: empty string. Leave empty to use the system default.
- `BROWSER_COLOR_SCHEME`: Color scheme. Default: `light`.
- `BROWSER_VIEWPORT_WIDTH`: Viewport width. Default: `1366`.
- `BROWSER_VIEWPORT_HEIGHT`: Viewport height. Default: `768`.
- `ENABLE_AUTH_STEALTH`: Whether to enable stealth in `auth` mode. Default: `true`.
- `INTERVENTION_TIMEOUT_SECONDS`: Timeout in seconds for manual user intervention. Default: `600`.

### Proxy

- `ENABLE_PROXY`: Whether proxy support is enabled. Default: `true`.
- `HTTP_PROXY`: HTTP proxy address. Default: empty string.
- `HTTPS_PROXY`: HTTPS proxy address. Default: empty string.
- `NO_PROXY`: Proxy bypass list. Default: empty string.

### Env loading

- `ADVANCED_FETCH_ENV_FILE`: Explicitly specify a dotenv file path. Default: empty string.

### Misc

- `IGNORE_SSL_ERRORS`: Whether to ignore HTTPS / SSL certificate errors. Default: `false`.

## Local Installation

```bash
uv sync
```

## Tests

```bash
uv run python -m unittest discover -s tests
```
