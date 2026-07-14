# advanced-fetch-mcp

[中文](README.md) | English

Provides an easy-to-use, powerful, and token-efficient web fetching tool for agents.
More capable than vanilla fetch, simpler than using Playwright directly.

## Features

- **Main-content extraction**: Built on top of trafilatura with configurable extraction strategy and scope, removing as much noise as possible to save tokens.
- **Dynamic website support**: Uses Playwright to fetch dynamic websites and detect when the page becomes stable.
- **LLM Sampling** (experimental): Use `sampling.prompt` to refine page content and return a condensed result. Supported by VS Code GitHub Copilot, goose, Amp, Glama, Joey, fast-agent, mcp-use, Postman, etc.
- **Chunked reading for large pages**: Supports `find.query` for searching within a page, and uses `cursor` plus `view.max_length` to continue reading from any position.
- **Manual interaction and auth**: `operation="elicit"` opens a visible browser so the user can finish login, CAPTCHA, or manual actions before continuing. Once logged in, later requests can reuse the saved auth state.
- **Anti-bot masking**: Includes Playwright-Stealth to imitate real browser behavior as much as possible and reduce bot detection.
- **Proxy support**: Supports `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY`.
- **Per-site rate limiting**: Configure `PER_SITE_RATE_LIMIT_SECONDS` to enforce a minimum interval between requests to the same hostname.
- **Image and resource download**: Use `read_image` to fetch images and return them as MCP ImageContent; use `download` to save files from URLs to a local path.

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
| `url` | `string` | Required | Full URL of the target webpage, or a refid to reuse a previous fetch result. |
| `operation` | `"view" \| "find" \| "sampling" \| "eval" \| "elicit"` | `"view"` | Operation: view, in-page search, LLM extraction, JS execution, or elicit (request manual user action, use only when blocked by captcha/login wall). |
| `fetch` | `object` | See below | Page fetching mode and wait-strategy configuration. |
| `view` | `object` | See below | View operation configuration. |
| `find` | `object \| null` | `null` | Find operation configuration. |
| `sampling` | `object \| null` | `null` | Sampling operation configuration. |
| `eval` | `object \| null` | `null` | Eval operation configuration. |
| `elicit` | `object \| null` | `null` | Elicit operation configuration. |
| `cursor` | `integer \| null` | `null` | Continue-read offset. Valid for both view and find operations. |
| `max_length` | `integer` | `20000` | Maximum result length. |
| `output_to_file` | `string \| null` | `null` | If set, writes the full result as JSON to this file path instead of returning it. max_length is ignored. |

### 2. `fetch` object

| Path | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `fetch.mode` | `"dynamic" \| "static"` | `"static"` | Fetch mode: dynamic uses a browser; static requests source HTML directly. Auth info is automatically reused. |
| `fetch.min_stable_seconds` | `number` | `3.0` | Minimum stable duration in seconds for dynamic fetch. |
| `fetch.timeout` | `number` | `12.0` | Fetch timeout in seconds. On timeout, return the content obtained so far. |

### 3. `view` object

| Path | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `view.output_format` | `"markdown" \| "html"` | `"markdown"` | Main-content output format. |
| `view.markdown_engine` | `"article" \| "full"` | `"article"` | Markdown extraction engine. article uses trafilatura for article main content; full uses markdownify for the full page. |
| `view.max_length` | `integer` | `20000` | Maximum result length. |
| `view.links` | `boolean` | `true` | Whether to extract all links from the page. |
| `view.with_screenshot` | `boolean` | `false` | Whether to capture a screenshot of the page. Forces dynamic mode and captures the initial viewport as a base64-encoded PNG. |

### 4. `find` object

| Path | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `find.query` | `string` | Required | Text or regular expression to search for. |
| `find.regex` | `boolean` | `false` | Whether to treat query as a regular expression. |

### 5. `sampling` object

| Path | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `sampling.prompt` | `string` | Required | Prompt that guides the LLM to extract information from the page main content. |
| `sampling.model` | `string \| null` | `null` | Preferred model name. |

### 6. `eval` object

| Path | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `eval.script` | `string` | Required | JavaScript code executed in the page context. |

### 7. Constraints

| Rule | Description |
| :--- | :--- |
| Operation-specific config | The `find`, `sampling`, or `eval` object may only be provided when `operation` matches, and they are mutually exclusive. |
| `eval` mode restriction | When `operation="eval"`, `fetch.mode` must be `"dynamic"`. |
| `elicit` mode restriction | When `operation="elicit"`, `fetch.mode` must be `"dynamic"`. |
| `max_length` scope | Applies to `view`, `find`, `sampling`, and `eval`, limiting the final returned result. |
| `cursor` scope | Valid for both `view` and `find`. Used to continue reading from a previous `next_cursor` position. |
| Continue-read consistency | When continuing with `cursor`, use the previous response's `refid` as the `url` to reuse the cache and ensure the same page snapshot. |


## Response format

### Common response shape

```json
{
  "success": true,
  "final_url": "https://example.com/final",
  "result": "...",
  "refid": "a1b2c3d4e5f6",
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
| `refid` | `string` | No | Reference ID for this fetch result. Pass this value as the `url` in subsequent requests to reuse the cached result. |
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

### `sampling` response (experimental)

> Supported by VS Code GitHub Copilot, goose, Amp, Glama, Joey, fast-agent, mcp-use, Postman, etc.

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

Get the full page as markdown (keep all content, no article extraction):

```yaml
url: https://example.com
operation: view
view:
  markdown_engine: full
```

Extract links from the page:

```yaml
url: https://example.com
operation: view
view:
  links: true
```

Output as HTML:

```yaml
url: https://example.com
operation: view
view:
  output_format: html
```

Set timeout:

```yaml
url: https://example.com
operation: view
fetch:
  timeout: 60
```

Search for a keyword:

```yaml
url: https://example.com
operation: find
find:
  query: price
```

Continue reading from a specific position (using `matches[].cursor` or `next_cursor` from a `find` response):

```yaml
url: <refid>
operation: view
cursor: 300
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
  operation: elicit
fetch:
  mode: dynamic
```

## Session Modes

To fetch intranet pages, use `operation="elicit"` to open a visible browser window. After you log in once, cookies are automatically saved via `storage_state.json`, and subsequent silent requests (without `operation="elicit"`) will carry the login state automatically.

## Cache

Each fetch result generates a `refid`. Pass the `refid` directly as the `url` in subsequent requests to reuse the cache without re-fetching.

- `refid` is a 12-character hex string, with a cache TTL of 24 hours
- Using a `refid` as the `url` will not generate a new `refid` (the same `refid` always points to the same content)
- Passing a regular URL always triggers a fresh fetch, never implicitly using the cache
- If the `refid` has expired or does not exist, an error is returned; use the original URL to re-fetch

## Environment Variables

### General

- `FETCH_TIMEOUT`: Total fetch timeout in seconds. Default: `12`.
- `PER_SITE_RATE_LIMIT_SECONDS`: Minimum interval in seconds between requests to the same hostname. Default: `1.0`. Set to `0` to disable it. Serialized requests include a small random jitter to avoid an overly regular access pattern.

### Auto-wait

- `AUTO_WAIT_POLL_INTERVAL`: Polling interval in seconds for dynamic-content stability detection. Default: `0.25`.
- `AUTO_WAIT_MIN_STABLE_SECONDS`: Minimum stable duration in seconds for dynamic fetch. Default: `3.0`.
- `AUTO_WAIT_MIN_CONTENT_LENGTH`: Minimum content length for dynamic fetch. Content must be stable and reach this length to be considered ready. Default: `150`.
- `AUTO_WAIT_SAMPLE_EDGE_CHARS`: Number of leading and trailing characters compared during stability detection. Default: `200`.

### Extraction / LLM

- `DEFAULT_MAX_LENGTH`: Default max output length. Default: `20000`.
- `ENABLE_PROMPT_EXTRACTION`: Whether `sampling` is enabled. Default: `false`. Experimental feature. Supported by VS Code GitHub Copilot, goose, Amp, Glama, Joey, fast-agent, mcp-use, Postman, etc.
- `PROMPT_INPUT_MAX_CHARS`: Max input size passed to the LLM. Default: `64000`.
- `MAX_FIND_MATCHES`: Maximum number of page-search matches to return. Default: `12`.
- `FIND_SNIPPET_MAX_CHARS`: Max snippet length for each search match. Default: `240`.
- `MAX_LINKS_COUNT`: Maximum number of links returned by `links` operation. Default: `30`.
- `SCHEMA_LANGUAGE`: Schema description language. Default: `zh`. Supported values: `zh` / `en`.

### Browser / Session

- `BROWSER_CHANNEL`: Browser channel passed to Playwright. Default: `chrome`. Allowed values include `chrome`, `chrome-beta`, `chrome-dev`, `msedge`, `msedge-beta`, `msedge-dev`, and `chromium`.
- `BROWSER_AUTH_STORAGE_STATE`: Path to `storage_state.json` in `auth` mode. Default: `~/.advanced-fetch-auth/storage_state.json`.
- `BROWSER_LOCALE`: Browser locale. Default: empty string. Leave empty to use the system default.
- `BROWSER_TIMEZONE_ID`: Browser timezone. Default: empty string. Leave empty to use the system default.
- `BROWSER_COLOR_SCHEME`: Color scheme. Default: `light`.
- `BROWSER_VIEWPORT_WIDTH`: Viewport width. Default: `1440`.
- `BROWSER_VIEWPORT_HEIGHT`: Viewport height. Default: `900`.
- `ENABLE_AUTH_STEALTH`: Whether to enable stealth in `auth` mode. Default: `true`.
- `INTERVENTION_TIMEOUT_SECONDS`: Timeout in seconds for manual user action. Default: `600`.

### Proxy

- `ENABLE_STATIC_PROXY`: Whether proxy is enabled for static fetch mode. Default: `true`.
- `ENABLE_DYNAMIC_PROXY`: Whether proxy is enabled for dynamic (browser) fetch mode. Default: `false`.
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
