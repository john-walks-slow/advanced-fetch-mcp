# advanced-fetch-mcp

中文 | [English](README.en.md)

为 Agent 提供易用、强大、节约 Token 的网页抓取能力。
比 vanilla fetch 强大，比 Playwright 简洁。

## 功能

- **正文提取**：基于 trafilatura 的强大正文提取能力，可配置的提取策略和范围，最大程度剔除噪音节省 Token。
- **支持动态网站**：基于 Playwright 的动态网站抓取能力，智能识别页面稳定状态。
- **LLM Sampling**（实验性）：通过 `sampling.prompt` 对网页内容进行提炼，返回精简结果。支持 sampling 的客户端包括 VS Code GitHub Copilot、goose、Amp 等。
- **大页面分段处理**：支持 `find.query` 在页面中搜索，并结合 `render.cursor` 与顶层 `max_length` 从任意位置续读。
- **人工介入和鉴权**：`fetch.require_user_intervention=true` 打开可见浏览器，用户完成登录、验证码或手动操作后继续抓取。登录一次后，后续请求可继续复用登录信息。
- **反爬伪装**：包含 Playwright-Stealth，尽可能模仿真实请求，尽量防止被检测成机器人。
- **代理支持**：支持 `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY`
- **按站点限流**：支持通过环境变量 `PER_SITE_RATE_LIMIT_SECONDS` 为同一 hostname 的请求设置最小间隔。

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
        "SCHEMA_LANGUAGE": "zh"
      }
    }
  }
}
```

## Schema

### 一、顶层参数

| 参数名 | 类型 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- |
| `url` | `string` | 必填 | 目标网页的完整 URL。 |
| `operation` | `"view" \| "find" \| "sampling" \| "eval"` | `"view"` | 操作类型：查看、页面内搜索、LLM 提取或执行 JS。 |
| `fetch` | `object` | 见下表 | 页面获取方式与等待策略配置。 |
| `render` | `object` | 见下表 | 正文提取、输出格式及续读配置。 |
| `max_length` | `integer` | `8000` | 结果最大长度。 |
| `find` | `object \| null` | `null` | 查找配置。仅当 operation="find" 时提供。 |
| `sampling` | `object \| null` | `null` | 提取配置。仅当 operation="sampling" 时提供。 |
| `eval` | `object \| null` | `null` | 脚本配置。仅当 operation="eval" 时提供。 |

### 二、`fetch` 对象

| 路径 | 类型 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- |
| `fetch.mode` | `"dynamic" \| "static"` | `"dynamic"` | 抓取方式：dynamic 用浏览器，static 直接请求源码。 |
| `fetch.min_stable_seconds` | `number` | `5.0` | 动态抓取等待内容稳定的最小时长（秒）。 |
| `fetch.min_content_length` | `integer` | `150` | 动态抓取时内容长度必须达到此值且稳定时间足够才视为成功。 |
| `fetch.timeout` | `number` | `30.0` | 抓取超时秒数。超时后返回当前已获取内容。 |
| `fetch.require_user_intervention` | `boolean` | `false` | 用于需要登录、验证码或人工操作的页面。会打开可见浏览器窗口，等待操作完成后自动继续抓取；登录态会保存供后续访问复用。 |

### 三、`render` 对象

| 路径 | 类型 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- |
| `render.engine` | `"trafilatura" \| "markdownify"` | `"trafilatura"` | 提取引擎。trafilatura 适合文章/正文类页面；复杂页面可用 markdownify 覆盖更多页面内容。 |
| `render.output_format` | `"markdown" \| "html"` | `"markdown"` | 正文输出格式。 |
| `render.strategy` | `"default" \| "strict" \| "loose"` | `"default"` | trafilatura 专用策略：strict 更干净，loose 覆盖更多。 |
| `render.include_elements` | `Array<"comments" \| "tables" \| "images" \| "links" \| "formatting">` | `["tables", "formatting"]` | 额外保留的内容类型，如 tables、links、images。 |
| `render.cursor` | `integer \| null` | `null` | 文本起始偏移量。仅用于继续读取长页面。 |

### 四、`find` 对象

| 路径 | 类型 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- |
| `find.query` | `string` | 必填 | 要查找的文本或正则表达式。 |
| `find.regex` | `boolean` | `false` | 是否将 query 视为正则表达式处理。 |
| `find.limit` | `integer` | `12` | 本次最多返回多少个匹配项。 |
| `find.snippet_max_chars` | `integer` | `240` | 每个匹配项 snippet 的最大长度。 |
| `find.start_index` | `integer` | `0` | 从第几个匹配开始返回，0 表示第一个匹配。 |

### 五、`sampling` 对象

| 路径 | 类型 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- |
| `sampling.prompt` | `string` | 必填 | 指导 LLM 从页面正文中提取信息的提示词。 |
| `sampling.model` | `string \| null` | `null` | 偏好的模型名。 |

### 六、`eval` 对象

| 路径 | 类型 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- |
| `eval.script` | `string` | 必填 | 在页面上下文执行的 JavaScript 代码。仅 dynamic 模式支持。 |

### 七、使用约束

| 规则 | 说明 |
| :--- | :--- |
| 操作专属配置 | 仅当 `operation` 为对应值时，才可提供 `find`、`sampling` 或 `eval` 对象，且三者互斥。 |
| `eval` 模式限制 | `operation="eval"` 时，`fetch.mode` 必须为 `"dynamic"`。 |
| `max_length` 作用域 | 对 `view`、`find`、`sampling`、`eval` 均生效，限制最终返回结果。 |
| `render.cursor` 作用域 | 仅对 `view` 有效。用于从上次返回的 `next_cursor` 位置继续读取。 |
| 续读一致性 | 使用 `cursor` 续读时，应保持 `output_format` 与 `strategy` 不变，否则偏移位置可能失效。 |


## 返回值格式

### 通用返回结构

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

### 通用字段说明

| 字段 | 类型 | 必然出现 | 说明 |
| :--- | :--- | :--- | :--- |
| `success` | `boolean` | 是 | 成功时恒为 `true`。 |
| `final_url` | `string` | 是 | 最终页面 URL，可能与输入 `url` 不同。 |
| `result` | `string` | 是 | 主返回内容。`view`/`sampling`/`eval` 为文本结果；`find` 当前固定为空字符串。 |
| `cache_hit` | `boolean` | 否 | 命中缓存时出现。 |
| `timed_out` | `boolean` | 否 | 抓取阶段发生超时时出现。 |
| `timeout_stage` | `string` | 否 | 超时所在阶段。 |
| `intervention_ended_by` | `string` | 否 | 人工介入结束原因，如 `timeout`、`page_closed`。 |
| `truncated` | `boolean` | 否 | 返回结果被 `max_length` 截断时出现。 |
| `next_cursor` | `integer` | 否 | 可继续读取或继续搜索时返回下一段偏移量。 |
| `warnings` | `string[]` | 否 | 警告信息列表。 |

### `view` 返回

```json
{
  "success": true,
  "final_url": "https://example.com/final",
  "result": "页面正文片段",
  "truncated": true,
  "next_cursor": 8000
}
```

说明：
- `result` 为当前窗口的正文文本。
- 当正文未读完时，会返回 `next_cursor`。

### `find` 返回

```json
{
  "success": true,
  "final_url": "https://example.com/final",
  "result": "",
  "found": true,
  "matches": [
    {
      "snippet": "…命中附近的文本片段…",
      "cursor": 1234
    }
  ],
  "matches_total": 3,
  "matches_truncated": false,
  "next_cursor": 1234
}
```

### `find` 特有字段

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `found` | `boolean` | 是否找到命中。 |
| `matches` | `object[]` | 命中摘要列表。 |
| `matches_total` | `integer` | 总命中数。 |
| `matches_truncated` | `boolean` | 命中摘要是否因数量过多而被截断。 |

### `find.matches` 项结构

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `snippet` | `string` | 命中附近的文本摘要。 |
| `cursor` | `integer` | 可用于后续 `render.cursor` 续读的偏移量。 |

### `sampling` 返回（实验性）

> 支持 sampling 的客户端包括 VS Code GitHub Copilot、goose、Amp、Glama、Joey、fast-agent、mcp-use、Postman 等。

```json
{
  "success": true,
  "final_url": "https://example.com/final",
  "result": "提炼后的结果文本",
  "truncated": true
}
```

说明：
- `result` 为 LLM 提炼后的文本结果。
- 若 `sampling` 失败，会回退到原始正文文本，并在 `warnings` 中说明。

### `eval` 返回

```json
{
  "success": true,
  "final_url": "https://example.com/final",
  "result": "{\n  \"title\": \"Example\"\n}",
  "truncated": false
}
```

说明：
- `result` 为脚本执行结果的字符串化内容。
- 若返回值是对象、数组、布尔值或数字，会先序列化为 JSON 字符串再返回。

## 示例

抓正文：

```yaml
url: https://example.com
operation: view
```

保留更多内容（`loose` 策略）：

```yaml
url: https://example.com
operation: view
render:
  strategy: loose
```

保留链接和图片：

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

设置超时：

```yaml
url: https://example.com
operation: view
fetch:
  timeout: 60
```

搜索关键词：

```yaml
url: https://example.com
operation: find
find:
  query: 价格
```

从搜索结果位置续读：

```yaml
url: https://example.com
operation: view
max_length: 300
render:
  cursor: 300 # 假设这是某个命中的 cursor
```

智能 Sampling（让模型整理）：

```yaml
url: https://example.com
operation: sampling
sampling:
  prompt: 提取商品名称和价格
```

执行页面内 JS：

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

需要登录的网站：

```yaml
url: https://private-site.com
operation: view
fetch:
  require_user_intervention: true
```

## 会话模式

通过环境变量 `BROWSER_SESSION_MODE` 控制浏览器会话模式：

- `auth`：默认值，推荐。使用普通 browser/context，并通过 `storage_state.json` 保存登录态；会尝试启用 stealth。
- `profile`：兼容模式，不推荐。使用 persistent profile（`user_data_dir`）；不会启用 stealth。

一般情况下，建议始终使用默认的 `auth` 模式。

## 缓存

最近抓取的网站会按 `url + fetch.mode` 缓存。后续在同一页里搜索、跳转、续读时复用已有结果。

## 环境变量

### 通用

- `FETCH_TIMEOUT`：抓取总超时秒数。默认 `30`。
- `PER_SITE_RATE_LIMIT_SECONDS`：同一 hostname 的最小抓取间隔秒数。默认 `1.0`。 设为 `0` 可关闭。串行时会附带一个很小的随机 jitter，避免请求节奏过于固定。

### 自动等待

- `AUTO_WAIT_POLL_INTERVAL`：动态抓取时的稳定性检测轮询间隔（秒）。默认 `0.25`。
- `AUTO_WAIT_MIN_STABLE_SECONDS`：动态抓取时等待内容稳定的最小时长（秒）。默认 `5.0`。
- `AUTO_WAIT_MIN_CONTENT_LENGTH`：动态抓取时的最小内容长度阈值。内容稳定且长度达到此阈值时提前结束等待。默认 `150`。
- `AUTO_WAIT_SAMPLE_EDGE_CHARS`：稳定性检测时用于对比的首尾字符数。默认 `200`。

### 提取 / LLM

- `DEFAULT_MAX_LENGTH`：默认返回长度上限。默认 `8000`。
- `ENABLE_PROMPT_EXTRACTION`：是否启用 `sampling`。默认 `false`。 实验性功能。支持 sampling 的客户端包括 VS Code GitHub Copilot、goose、Amp、Glama、Joey、fast-agent、mcp-use、Postman 等。
- `PROMPT_INPUT_MAX_CHARS`：传给 LLM 的最大输入字符数。默认 `64000`。
- `MAX_FIND_MATCHES`：页内搜索最多返回多少条命中。默认 `12`。
- `FIND_SNIPPET_MAX_CHARS`：每条搜索命中的片段长度上限。默认 `240`。
- `SCHEMA_LANGUAGE`：schema 描述语言。默认 `zh`。 支持 `zh` / `en`。

### 浏览器 / 会话

- `BROWSER_CHANNEL`：传给 Playwright 的浏览器 channel。默认 `chrome`。 可选值包括 `chrome`、`chrome-beta`、`chrome-dev`、`msedge`、`msedge-beta`、`msedge-dev`、`chromium`。
- `BROWSER_SESSION_MODE`：浏览器会话模式。默认 `auth`。 可选 `auth` 或 `profile`，默认推荐 `auth`。
- `BROWSER_AUTH_STORAGE_STATE`：`auth` 模式下 `storage_state.json` 的路径。默认 `~/.advanced-fetch-auth/storage_state.json`。
- `BROWSER_PROFILE_DIR`：`profile` 模式下 persistent profile 的目录。默认 `~/.advanced-fetch-profile`。
- `BROWSER_LOCALE`：浏览器 locale。默认 空字符串。 留空则使用系统默认。
- `BROWSER_TIMEZONE_ID`：浏览器时区。默认 空字符串。 留空则使用系统默认。
- `BROWSER_COLOR_SCHEME`：颜色方案。默认 `light`。
- `BROWSER_VIEWPORT_WIDTH`：viewport 宽度。默认 `1366`。
- `BROWSER_VIEWPORT_HEIGHT`：viewport 高度。默认 `768`。
- `ENABLE_AUTH_STEALTH`：是否在 `auth` 模式启用 stealth。默认 `true`。
- `INTERVENTION_TIMEOUT_SECONDS`：用户人工介入等待超时秒数。默认 `600`。

### 代理

- `ENABLE_PROXY`：是否启用代理。默认 `true`。
- `HTTP_PROXY`：HTTP 代理地址。默认 空字符串。
- `HTTPS_PROXY`：HTTPS 代理地址。默认 空字符串。
- `NO_PROXY`：代理绕过列表。默认 空字符串。

### Env 加载

- `ADVANCED_FETCH_ENV_FILE`：显式指定 dotenv 文件路径。默认 空字符串。

### 其它

- `IGNORE_SSL_ERRORS`：是否忽略 HTTPS / SSL 证书错误。默认 `false`。

## 本地安装

```bash
uv sync
```

## 测试

```bash
uv run python -m unittest discover -s tests
```