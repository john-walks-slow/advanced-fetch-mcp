# advanced-fetch-mcp

为 Agent 提供快速、强大、节省 Token 的网页抓取能力。  
比 vanilla fetch 更强，比直接上 Playwright 更简单。

## 功能

- **动态抓取优先**：默认 `dynamic` 模式（推荐），使用 Playwright 加载 JS 页面，适合现代网站。
- **静态抓取兜底**：`static` 模式直接请求页面响应，速度更快，适合纯静态页面或简单接口页。
- **正文抽取统一走 Trafilatura**：Markdown 输出、HTML 输出、自动等待采样都统一基于 Trafilatura，不再混用 `markdownify` 或 CSS selector 剔除。
- **灵活策略**：`strategy` 选择提取模式：`strict` 偏正文纯度、`loose` 偏召回、`none` 使用 Trafilatura 默认平衡策略。
- **语义级 extras**：通过 `extra_elements` 控制是否额外保留 `tables / images / links / comments / formatting` 等结构，而不是手写 `strip_selectors`。
- **LLM 整理**：提供 `extract_prompt` 让模型对内容进行提炼，返回精简结果，避免原始页面污染上下文。
- **搜索续读**：`find_in_page` 搜索关键词，返回命中列表；用 `cursor` 从任意位置续读，适合大页面分段处理。
- **人工介入**：`require_user_intervention=true` 打开可见浏览器，用户完成登录/验证码后继续抓取。
- **登录态持久化**：默认使用 Playwright `storage_state` 持久化登录态。登录一次后，后续 dynamic 请求可自动复用登录态。
- **更像真实用户**：默认在 `auth` 模式启用 stealth、真实浏览器上下文参数、语言/时区/viewport 等配置，降低被识别为自动化的概率。
- **代理支持**：支持 `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY`，并且 `dynamic` / `static` 两种模式行为一致。
- **缓存复用**：最近抓取的网站按 `url + mode` 缓存，下次续读或页内搜索无需重新抓取。

## 设计说明

### 关于 session 模式

通过环境变量 `BROWSER_SESSION_MODE` 控制浏览器会话模式：

- `auth`：默认值，推荐。使用普通 browser/context，并通过 `storage_state.json` 保存登录态。
- `profile`：兼容模式，不推荐。使用 persistent profile（`user_data_dir`），**不会启用 stealth**。

一般情况下，建议始终使用默认的 `auth` 模式。

### 关于代理

通过环境变量 `ENABLE_PROXY` 控制是否启用代理，默认值为 `true`。

- 当 `ENABLE_PROXY=true` 时：
  - `dynamic` 模式会给 Playwright 配置代理
  - `static` 模式会给 `requests` 显式配置同样的代理
- 当 `ENABLE_PROXY=false` 时：
  - `dynamic` / `static` 都不会使用代理
  - `static` 也不会偷偷继承系统代理环境变量

## 环境变量加载

程序启动时会优先读取显式指定的 dotenv 文件：`ADVANCED_FETCH_ENV_FILE`。如果未指定，则只读取**当前工作目录**下的 `.env`。

这能兼容 `uv --directory <父目录>` 的用法：只要把 `.env` 放在那个工作目录里即可，不会再向更上层目录误读其他项目的配置。

## MCP Client 配置

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
        "BROWSER_LOCALE": "en-US",
        "BROWSER_TIMEZONE_ID": "Asia/Shanghai",
        "BROWSER_VIEWPORT_WIDTH": "1366",
        "BROWSER_VIEWPORT_HEIGHT": "768",
        "ENABLE_PROMPT_EXTRACTION": "true",
        "MAX_FIND_MATCHES": "8",
        "FIND_SNIPPET_MAX_CHARS": "240"
      }
    }
  }
}
```

## 参数

| 参数 | 说明 |
| --- | --- |
| `url` | 目标网址。 |
| `mode` | 页面抓取方式。`dynamic`（推荐）使用 Playwright；`static` 直接获取页面响应。 |
| `wait_for` | 仅对 `dynamic` 生效。默认 `auto`：页面加载后自动轮询正文抽取结果，直到结果趋于稳定；也可传秒数，表示额外等待指定秒数。 |
| `timeout` | 抓取超时秒数。超时后尽量返回当前已加载内容。未提供时使用环境变量中的默认超时。 |
| `output_format` | 输出格式。`markdown` 返回 Trafilatura 生成的 Markdown；`html` 返回 Trafilatura 抽取后的 HTML。 |
| `strategy` | 提取策略。`strict` 偏正文纯度；`loose` 偏召回；`none` 使用 Trafilatura 默认平衡策略。 |
| `extra_elements` | 语义级额外保留元素。可选值：`tables`、`images`、`links`、`comments`、`formatting`。默认 `['tables']`。 |
| `cursor` | 文本位置偏移。从该位置续读或继续搜索。（受输出格式和提取策略影响；给定该参数时优先使用缓存） |
| `max_length` | 结果长度上限。 |
| `find_in_page` | 页面内搜索，返回 `matches` 列表，适合在长页面中定位关键部分。（给定该参数时优先使用缓存） |
| `find_with_regex` | 是否把 `find_in_page` 按正则表达式处理。 |
| `extract_prompt` | 提取提示词。提供后，调用 LLM 整理内容，返回提取后的结果。可避免原始页面内容污染调用方上下文。 |
| `evaluate_js` | 在页面上下文中执行 JavaScript，返回脚本结果。仅支持 `dynamic`。 |
| `require_user_intervention` | 需要登录/过验证码时设为 `true`，打开可见浏览器让用户手动操作，用户完成后自动继续。 |

## 示例

抓正文（默认 `dynamic` + `strict` + `wait_for=auto`）：

```yaml
url: https://example.com
```

明确使用动态抓取：

```yaml
url: https://example.com
mode: dynamic
```

静态抓取：

```yaml
url: https://example.com
mode: static
```

保留更多正文（`loose` 策略）：

```yaml
url: https://example.com
strategy: loose
```

使用 Trafilatura 默认平衡策略：

```yaml
url: https://example.com
strategy: none
```

保留链接和图片：

```yaml
url: https://example.com
extra_elements:
  - tables
  - links
  - images
```

动态模式下额外等待 2 秒：

```yaml
url: https://example.com
wait_for: 2
```

搜索关键词：

```yaml
url: https://example.com
find_in_page: 价格
```

从搜索结果位置续读：

```yaml
url: https://example.com
cursor: 300
max_length: 300
```

智能提炼：

```yaml
url: https://example.com
extract_prompt: 提取商品名称和价格
```

执行页面内 JS：

```yaml
url: https://example.com
mode: dynamic
evaluate_js: |
  () => ({
    title: document.title,
    href: location.href,
    itemCount: document.querySelectorAll('.item').length
  })
```

需要登录的网站：

```yaml
url: https://private-site.com
require_user_intervention: true
```

会打开可见浏览器，用户登录后点击页面上的“我已完成操作”按钮，工具继续抓取。默认 `auth` 模式下，已登录的 session 会保存到 `storage_state.json`，后续请求可继续复用。

## 缓存

最近抓取的网站会按 `url + mode` 缓存。  
因此同一页面的续读（`cursor`）和页内搜索（`find_in_page`）通常无需重新抓取。

以下情况会跳过缓存：

- `require_user_intervention=true`
- 提供 `evaluate_js`

## 环境变量

### 通用

- `DEFAULT_TIMEOUT`：默认超时秒数。
- `NAVIGATION_TIMEOUT`：dynamic 导航超时秒数。
- `NETWORK_IDLE_TIMEOUT`：dynamic 等待 `networkidle` 的超时秒数。
- `STATIC_FETCH_TIMEOUT`：static 请求超时秒数。
- `AUTO_WAIT_TIMEOUT`：`wait_for=auto` 的最大等待秒数。
- `DEFAULT_MAX_LENGTH`：默认返回长度上限。
- `ENABLE_PROMPT_EXTRACTION`：是否启用 `extract_prompt`。
- `PROMPT_INPUT_MAX_CHARS`：传给 LLM 的最大输入字符数。
- `MAX_FIND_MATCHES`：页内搜索最多返回多少条命中。
- `FIND_SNIPPET_MAX_CHARS`：每条搜索命中的片段长度上限。

### 浏览器 / 会话

- `BROWSER_CHANNEL`：传给 Playwright 的浏览器 channel，不做校验。
- `BROWSER_SESSION_MODE`：`auth` 或 `profile`，默认 `auth`。
- `BROWSER_AUTH_STORAGE_STATE`：auth 模式下 `storage_state.json` 的路径。
- `BROWSER_PROFILE_DIR`：profile 模式下 persistent profile 的目录。
- `BROWSER_LOCALE`：浏览器 locale。
- `BROWSER_TIMEZONE_ID`：浏览器时区，例如 `Asia/Shanghai`。
- `BROWSER_COLOR_SCHEME`：颜色方案，默认 `light`。
- `BROWSER_VIEWPORT_WIDTH`：viewport 宽度。
- `BROWSER_VIEWPORT_HEIGHT`：viewport 高度。
- `ENABLE_AUTH_STEALTH`：是否在 `auth` 模式启用 stealth，默认 `true`。
- `INTERVENTION_TIMEOUT_SECONDS`：用户人工介入等待超时秒数。

### 代理

- `ENABLE_PROXY`：是否启用代理，默认 `true`。
- `HTTP_PROXY` / `HTTPS_PROXY`：代理地址。
- `NO_PROXY`：Playwright 代理绕过列表。

## 本地安装

```bash
uv sync
uv run playwright install
```

如果希望启用 stealth，请确认已安装可选依赖 `playwright-stealth`。当前仓库的 `requirements.txt` 已包含该依赖。

## 测试

```bash
uv run python -m unittest discover -s tests
```


## 环境变量

- `IGNORE_SSL_ERRORS=true`：忽略 HTTPS/SSL 证书校验错误。
  - static 模式下会传给 `requests` 的 `verify=False`。
  - dynamic 模式下会给 Playwright context 设置 `ignore_https_errors=True`。
  - 默认关闭。
