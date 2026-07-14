# advanced-fetch-mcp

中文 | [English](README.en.md)

为 Agent 提供易用、强大、节约 Token 的网页抓取能力。
比 vanilla fetch 强大，比 Playwright 简洁。

## 功能

- **正文提取**：基于 trafilatura 的强大正文提取能力，可配置的提取策略和范围，最大程度剔除噪音节省 Token。
- **支持动态网站**：基于 Playwright 的动态网站抓取能力，智能识别页面稳定状态。
- **支持鉴权**：请求自动携带 cookie 鉴权信息。Agent 可打开可见浏览器请用户完成登录。登录一次后，后续请求可继续复用登录信息。
- **引用和分段处理**：支持页面内搜索和分段读取页面。后续处理同一页面可以用 refid 引用。
- **防止反爬**：同一 hostname 的请求限制最小间隔防止触发限流。包含 Playwright-Stealth，尽可能模仿真实请求防止被检测成机器人。
- **代理支持**：支持 `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY`
- **LLM Sampling**（实验性）：通过 `sampling.prompt` 对网页内容进行提炼，返回精简结果。支持 sampling 的客户端包括 VS Code GitHub Copilot、goose、Amp 等。
- **图片获取**（`read_image`）：传入图片 URL 或 URL 列表，直接获取并返回为图片内容，无需走完整网页抓取流程。
- **文件下载**（`download`）：从 URL 下载文件到本地指定路径，支持流式下载大文件，自动创建父目录。

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
| `url` | `string` | 必填 | 目标网页的完整 URL 或之前结果的引用 ID（复用抓取结果）。 |
| `operation` | `"view" \| "find" \| "sampling" \| "eval" \| "elicit"` | `"view"` | 操作类型：查看、页面内搜索、LLM 提取、执行 JS 或 请求用户手动操作（当且仅当被 captcha / 登录墙阻拦时使用）。 |
| `fetch` | `object` | 见下表 | 页面获取方式与等待策略配置。 |
| `view` | `object` | 见下表 | View 操作配置 |
| `find` | `object \| null` | `null` | Find 操作配置 |
| `sampling` | `object \| null` | `null` | Sampling 操作配置 |
| `eval` | `object \| null` | `null` | Eval 操作配置 |
| `elicit` | `object \| null` | `null` | Elicit 操作配置 |
| `cursor` | `integer \| null` | `null` | 继续读取的偏移量。对 view 和 find 操作均有效。 |
| `max_length` | `integer` | `20000` | 结果最大长度。 |
| `output_to_file` | `string \| null` | `null` | 若指定，结果以 JSON 格式写入此文件路径而非直接返回，此时忽略 max_length。 |

### 二、`fetch` 对象

| 路径 | 类型 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- |
| `fetch.mode` | `"dynamic" \| "static"` | `"static"` | 抓取方式：dynamic=浏览器，static=request。自动复用鉴权信息。 |
| `fetch.min_stable_seconds` | `number` | `3.0` | 动态抓取等待内容稳定的最小时长（秒）。 |
| `fetch.timeout` | `number` | `12.0` | 抓取超时秒数。超时后返回当前已获取内容。 |

### 三、`view` 对象

| 路径 | 类型 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- |
| `view.output_format` | `"markdown" \| "html"` | `"markdown"` | 正文输出格式。 |
| `view.markdown_engine` | `"article" \| "full"` | `"article"` | markdown 提取引擎。article 用 trafilatura 提取文章正文；full 用 markdownify 提取完整页面。 |
| `view.max_length` | `integer` | `20000` | 结果最大长度。 |
| `view.links` | `boolean` | `true` | 是否提取页面中的出链。 |
| `view.with_screenshot` | `boolean` | `false` | 是否截图。自动使用 dynamic 模式获取页面并截取首屏，返回 base64 编码的 PNG。 |

### 四、`find` 对象

| 路径 | 类型 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- |
| `find.query` | `string` | 必填 | 要查找的文本或正则表达式。 |
| `find.regex` | `boolean` | `false` | 是否将 query 视为正则表达式处理。 |

### 五、`sampling` 对象

| 路径 | 类型 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- |
| `sampling.prompt` | `string` | 必填 | 指导 LLM 从页面正文中提取信息的提示词。 |
| `sampling.model` | `string \| null` | `null` | 偏好的模型名。 |

### 六、`eval` 对象

| 路径 | 类型 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- |
| `eval.script` | `string` | 必填 | 在页面上下文执行的 JavaScript 代码。 |

### 七、使用约束

| 规则 | 说明 |
| :--- | :--- |
| 操作专属配置 | 仅当 `operation` 为对应值时，才可提供 `find`、`sampling` 或 `eval` 对象，且三者互斥。 |
| `eval` 模式限制 | `operation="eval"` 时，`fetch.mode` 必须为 `"dynamic"`。 |
| `elicit` 模式限制 | `operation="elicit"` 时，`fetch.mode` 必须为 `"dynamic"`。 |
| `max_length` 作用域 | 对 `view`、`find`、`sampling`、`eval` 均生效，限制最终返回结果。 |
| `cursor` 作用域 | 对 `view` 和 `find` 均有效。用于从上次返回的 `next_cursor` 位置继续读取。 |
| 续读一致性 | 使用 `cursor` 续读时，填入上次结果的 `refid` 作为 `url` 以复用缓存，确保引用同一份页面快照。 |


## 返回值格式

### 通用返回结构

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

### 通用字段说明

| 字段                    | 类型       | 必然出现 | 说明                                                                         |
| :---------------------- | :--------- | :------- | :--------------------------------------------------------------------------- |
| `success`               | `boolean`  | 是       | 成功时恒为 `true`。                                                          |
| `final_url`             | `string`   | 是       | 最终页面 URL，可能与输入 `url` 不同。                                        |
| `result`                | `string`   | 是       | 主返回内容。`view`/`sampling`/`eval` 为文本结果；`find` 当前固定为空字符串。 |
| `refid`                 | `string`   | 否       | 本次抓取结果的引用 ID。将此值填入后续请求的 `url` 参数可直接复用缓存。       |
| `timed_out`             | `boolean`  | 否       | 抓取阶段发生超时时出现。                                                     |
| `timeout_stage`         | `string`   | 否       | 超时所在阶段。                                                               |
| `intervention_ended_by` | `string`   | 否       | 人工介入结束原因，如 `timeout`、`page_closed`。                              |
| `truncated`             | `boolean`  | 否       | 返回结果被 `max_length` 截断时出现。                                         |
| `next_cursor`           | `integer`  | 否       | 可继续读取或继续搜索时返回下一段偏移量。                                     |
| `warnings`              | `string[]` | 否       | 警告信息列表。                                                               |

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

| 字段                | 类型       | 说明                             |
| :------------------ | :--------- | :------------------------------- |
| `found`             | `boolean`  | 是否找到命中。                   |
| `matches`           | `object[]` | 命中摘要列表。                   |
| `matches_total`     | `integer`  | 总命中数。                       |
| `matches_truncated` | `boolean`  | 命中摘要是否因数量过多而被截断。 |

### `find.matches` 项结构

| 字段      | 类型      | 说明                                      |
| :-------- | :-------- | :---------------------------------------- |
| `snippet` | `string`  | 命中附近的文本摘要。                      |
| `cursor`  | `integer` | 可用于后续 `render.cursor` 续读的偏移量。 |

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

获取完整页面 markdown（不提取正文，保留全部内容）：

```yaml
url: https://example.com
operation: view
view:
  markdown_engine: full
```

同时提取页面中的链接：

```yaml
url: https://example.com
operation: view
view:
  links: true
```

以 HTML 格式输出：

```yaml
url: https://example.com
operation: view
view:
  output_format: html
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

从指定位置续读（配合 `find` 返回的 `matches[].cursor` 或 `next_cursor`）：

```yaml
url: <refid>
operation: view
cursor: 300
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
  operation: elicit
fetch:
  mode: dynamic
```

## `read_image` — 获取图片

独立工具，不依赖 `advanced_fetch`。

```yaml
# 单张图片
read_image:
  url: https://example.com/photo.png

# 多张图片
read_image:
  url:
    - https://example.com/photo1.png
    - https://example.com/photo2.jpg
```

**参数**：

| 参数 | 类型 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- |
| `url` | `string \| string[]` | 必填 | 图片 URL，可传单个 URL 或 URL 列表。 |
| `timeout` | `number` | `30` | 获取图片的超时秒数。 |

**输出**：返回 `ImageContent` 列表（MCP 原生图片），失败时返回 `TextContent` 说明错误原因。单 URL 失败不影响其他 URL。

## `download` — 下载文件

独立工具，不依赖 `advanced_fetch`。

```yaml
download:
  url: https://example.com/document.pdf
  file_path: /path/to/save/document.pdf
```

**参数**：

| 参数 | 类型 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- |
| `url` | `string` | 必填 | 下载源 URL。 |
| `file_path` | `string` | 必填 | 本地保存路径。自动创建父目录，自动解析为绝对路径。 |
| `overwrite` | `boolean` | `false` | 若为 `false` 且文件已存在则报错；设为 `true` 覆盖已有文件。 |
| `timeout` | `number` | `120` | 下载超时秒数。 |

**输出**：成功时返回包含 `file_path`、`size`、`content_type` 的 JSON；失败时返回 `{success: false, error: ...}`。下载中断会自动清理残留文件。

## 会话模式

抓取内网页面时，使用 `operation="elicit"` 打开可见浏览器，登录一次后 cookies 会通过 `storage_state.json` 自动保存，后续静默请求（不带 `operation="elicit"`）会自动携带登录态。

## 缓存

每次抓取结果会生成一个 `refid` 返回。将 `refid` 直接填入后续请求的 `url` 参数即可复用缓存，无需重新抓取。

- `refid` 为 12 位 hex 字符串，缓存有效期 24 小时
- 使用 `refid` 作为 URL 时不会产生新的 `refid`（同一个 `refid` 始终指向同一份内容）
- 直接传入普通 URL 时始终重新抓取，不会隐式使用缓存
- `refid` 过期或不存在时会返回错误，需使用原始 URL 重新抓取

## 环境变量

### 通用

- `FETCH_TIMEOUT`：抓取总超时秒数。默认 `12`。
- `PER_SITE_RATE_LIMIT_SECONDS`：同一 hostname 的最小抓取间隔秒数。默认 `1.0`。 设为 `0` 可关闭。串行时会附带一个很小的随机 jitter，避免请求节奏过于固定。

### 自动等待

- `AUTO_WAIT_POLL_INTERVAL`：动态抓取时的稳定性检测轮询间隔（秒）。默认 `0.25`。
- `AUTO_WAIT_MIN_STABLE_SECONDS`：动态抓取时等待内容稳定的最小时长（秒）。默认 `3.0`。
- `AUTO_WAIT_MIN_CONTENT_LENGTH`：动态抓取时内容最小长度。内容稳定且长度达到此阈值才视为就绪。默认 `150`。
- `AUTO_WAIT_SAMPLE_EDGE_CHARS`：稳定性检测时用于对比的首尾字符数。默认 `200`。

### 提取 / LLM

- `DEFAULT_MAX_LENGTH`：默认返回长度上限。默认 `20000`。
- `ENABLE_PROMPT_EXTRACTION`：是否启用 `sampling`。默认 `false`。 实验性功能。支持 sampling 的客户端包括 VS Code GitHub Copilot、goose、Amp、Glama、Joey、fast-agent、mcp-use、Postman 等。
- `PROMPT_INPUT_MAX_CHARS`：传给 LLM 的最大输入字符数。默认 `64000`。
- `MAX_FIND_MATCHES`：页内搜索最多返回多少条命中。默认 `12`。
- `FIND_SNIPPET_MAX_CHARS`：每条搜索命中的片段长度上限。默认 `240`。
- `MAX_LINKS_COUNT`：`links` 操作最多返回多少条链接。默认 `30`。
- `SCHEMA_LANGUAGE`：schema 描述语言。默认 `zh`。 支持 `zh` / `en`。

### 浏览器 / 会话

- `BROWSER_CHANNEL`：传给 Playwright 的浏览器 channel。默认 `chrome`。 可选值包括 `chrome`、`chrome-beta`、`chrome-dev`、`msedge`、`msedge-beta`、`msedge-dev`、`chromium`。
- `BROWSER_AUTH_STORAGE_STATE`：`auth` 模式下 `storage_state.json` 的路径。默认 `~/.advanced-fetch-auth/storage_state.json`。
- `BROWSER_LOCALE`：浏览器 locale。默认 空字符串。 留空则使用系统默认。
- `BROWSER_TIMEZONE_ID`：浏览器时区。默认 空字符串。 留空则使用系统默认。
- `BROWSER_COLOR_SCHEME`：颜色方案。默认 `light`。
- `BROWSER_VIEWPORT_WIDTH`：viewport 宽度。默认 `1440`。
- `BROWSER_VIEWPORT_HEIGHT`：viewport 高度。默认 `900`。
- `ENABLE_AUTH_STEALTH`：是否在 `auth` 模式启用 stealth。默认 `true`。
- `INTERVENTION_TIMEOUT_SECONDS`：用户人工操作等待超时秒数。默认 `600`。

### 代理

- `ENABLE_STATIC_PROXY`：static 模式是否启用代理。默认 `true`。
- `ENABLE_DYNAMIC_PROXY`：dynamic 模式（浏览器）是否启用代理。默认 `false`。
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
