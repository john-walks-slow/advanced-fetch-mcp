# advanced-fetch-mcp

Provides an easy-to-use, powerful, and token-efficient web fetching tool for agents.
More capable than vanilla fetch, simpler than using Playwright directly.

## Features

- **Main-content extraction**: Built on top of trafilatura with configurable extraction strategy and scope, removing as much noise as possible to save tokens.
- **Dynamic website support**: Uses Playwright to fetch dynamic websites and detect when the page becomes stable.
- **LLM Sampling**: Use `extract_prompt` to refine page content and return a condensed result, avoiding raw page content polluting the caller context.
- **Chunked reading for large pages**: Supports `find_in_page` for searching within a page, and `cursor` + `max_length` to continue reading from any position.
- **Manual intervention and auth**: `require_user_intervention=true` opens a visible browser so the user can finish login, CAPTCHA, or manual actions before continuing. Once logged in, later requests can reuse the saved auth state.
- **Anti-bot masking**: Includes Playwright-Stealth to imitate real browser behavior as much as possible and reduce bot detection.
- **Proxy support**: Supports `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY`.

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
        "BROWSER_CHANNEL": "chrome",
        "BROWSER_SESSION_MODE": "auth",
        "DEFAULT_TIMEOUT": "10",
        "AUTO_WAIT_TIMEOUT": "5",
        "ENABLE_PROXY": "true",
        "HTTP_PROXY": "",
        "HTTPS_PROXY": "",
        "NO_PROXY": "",
        "ENABLE_AUTH_STEALTH": "true",
        "BROWSER_LOCALE": "",
        "BROWSER_TIMEZONE_ID": "",
        "ENABLE_PROMPT_EXTRACTION": "true",
        "MAX_FIND_MATCHES": "8",
        "FIND_SNIPPET_MAX_CHARS": "240",
        "SCHEMA_LANGUAGE": "en"
      }
    }
  }
}
```

Notes:

- Leave `BROWSER_LOCALE` empty to use the system default locale.
- Leave `BROWSER_TIMEZONE_ID` empty to use the system default timezone.
- `SCHEMA_LANGUAGE` controls the MCP schema description language. Supported values: `zh` / `en`.

## Schema

### 1. Top-level parameters

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `url` | `string` | Required | Full URL of the target webpage. |
| `operation` | `"view" \| "find" \| "sampling" \| "eval"` | `"view"` | Operation type. `view`: get the page main content. `find`: search matches in the main content. `sampling`: use an LLM to extract information from the main content. `eval`: execute JavaScript in the page context and return the result. |
| `fetch` | `object` | See below | Page fetching mode and wait-strategy configuration. |
| `render` | `object` | See below | Main-content extraction, output-format, and result-window configuration. |
| `find` | `object \| null` | `null` | Find configuration. Provide only when `operation="find"`. |
| `sampling` | `object \| null` | `null` | Sampling configuration. Provide only when `operation="sampling"`. |
| `eval` | `object \| null` | `null` | Script configuration. Provide only when `operation="eval"`. |

### 2. `fetch` object

| Path | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `fetch.mode` | `"dynamic" \| "static"` | `"dynamic"` | Fetch mode. `dynamic`: use a browser to load the page and execute scripts. `static`: request the page source directly over HTTP. |
| `fetch.wait_for` | `number \| "auto"` | `"auto"` | Wait strategy (only effective in dynamic mode). `"auto"`: automatically wait until the network is idle and the main-content area is stable. Number: extra seconds to wait after page load. |
| `fetch.timeout` | `number \| null` | `null` | Fetch timeout in seconds. On timeout, return the content obtained so far. |
| `fetch.require_user_intervention` | `boolean` | `false` | For pages that require login, CAPTCHA, or manual actions. When set to true, a visible browser window is opened and fetching resumes automatically after the user finishes. |

### 3. `render` object

| Path | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `render.output_format` | `"markdown" \| "html"` | `"markdown"` | Main-content output format. |
| `render.strategy` | `"strict" \| "loose" \| null` | `null` | Main-content extraction strategy. `strict`: prioritize content purity. `loose`: prioritize content coverage. `null`: use the default balanced strategy. |
| `render.include_elements` | `Array<"tables" \| "formatting" \| "images" \| "links" \| "comments">` | `["tables", "formatting"]` | Content types to include in addition to the main content. |
| `render.max_length` | `integer` | `8000` | Maximum text length. |
| `render.cursor` | `integer \| null` | `null` | Text start offset used to continue reading or continue searching on long pages. |

### 4. `find` object

| Path | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `find.query` | `string` | Required | Text or regular expression to search for. |
| `find.regex` | `boolean` | `false` | Whether to treat `query` as a regular expression. |

### 5. `sampling` object

| Path | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `sampling.prompt` | `string` | Required | Prompt that guides the LLM to extract information from the page main content. |

### 6. `eval` object

| Path | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `eval.script` | `string` | Required | JavaScript code executed in the page context. Supported only in dynamic mode. |

### 7. Constraints

| Rule | Description |
| :--- | :--- |
| Operation-specific config | The `find`, `sampling`, or `eval` object may only be provided when `operation` matches, and they are mutually exclusive. |
| `eval` mode restriction | When `operation="eval"`, `fetch.mode` must be `"dynamic"`. |
| `render.max_length` scope | max length only applies to text produced by the render step. It does not apply to results of other operations. |
| `render.cursor` scope | Only valid for `view` and `find`. Used to continue reading or searching from a previous `next_cursor` position. |
| Continue-read consistency | When continuing with `cursor`, keep `output_format` and `strategy` unchanged, otherwise the offset may become invalid. |

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
render:
  cursor: 300 # assume this is a cursor returned from a previous match
  max_length: 300
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

- `DEFAULT_TIMEOUT`: default timeout in seconds.
- `NAVIGATION_TIMEOUT`: navigation timeout for `dynamic` mode.
- `NETWORK_IDLE_TIMEOUT`: `networkidle` timeout for `dynamic` mode.
- `STATIC_FETCH_TIMEOUT`: request timeout for `static` mode.
- `AUTO_WAIT_TIMEOUT`: max wait time when `fetch.wait_for=auto`.
- `DEFAULT_MAX_LENGTH`: default max output length.
- `ENABLE_PROMPT_EXTRACTION`: whether `sampling` is enabled.
- `PROMPT_INPUT_MAX_CHARS`: max input size passed to the LLM.
- `MAX_FIND_MATCHES`: maximum number of page-search matches to return.
- `FIND_SNIPPET_MAX_CHARS`: max snippet length for each search match.
- `SCHEMA_LANGUAGE`: schema description language. Supported values: `zh` / `en`.

### Browser / Session

- `BROWSER_CHANNEL`: browser channel passed to Playwright.
- `BROWSER_SESSION_MODE`: `auth` or `profile`, default is `auth`.
- `BROWSER_AUTH_STORAGE_STATE`: path to `storage_state.json` in `auth` mode.
- `BROWSER_PROFILE_DIR`: persistent profile directory in `profile` mode.
- `BROWSER_LOCALE`: browser locale. Leave empty to use the system default.
- `BROWSER_TIMEZONE_ID`: browser timezone. Leave empty to use the system default.
- `BROWSER_COLOR_SCHEME`: color scheme, default is `light`.
- `BROWSER_VIEWPORT_WIDTH`: viewport width.
- `BROWSER_VIEWPORT_HEIGHT`: viewport height.
- `ENABLE_AUTH_STEALTH`: whether to enable stealth in `auth` mode, default is `true`.
- `INTERVENTION_TIMEOUT_SECONDS`: timeout for manual user intervention.

### Proxy

- `ENABLE_PROXY`: whether to enable proxy, default is `true`.
- `HTTP_PROXY` / `HTTPS_PROXY`: proxy address.
- `NO_PROXY`: Playwright proxy bypass list.

### Others

- `ADVANCED_FETCH_ENV_FILE`: explicitly specify a dotenv file.
- `IGNORE_SSL_ERRORS=true`: ignore HTTPS / SSL certificate errors.

## Local Installation

```bash
uv sync
```

## Tests

```bash
uv run python -m unittest discover -s tests
```
