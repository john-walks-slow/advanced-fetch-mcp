# advanced-fetch-mcp

为 Agent 提供易用、强大、节约 Token 的网页抓取能力。
比 vanilla fetch 强大，比 Playwright 简洁。

## 功能

- **正文提取**：基于 trafilatura 的强大正文提取能力，可配置的提取策略和范围，最大程度剔除噪音节省 Token。
- **支持动态网站**：基于 Playwright 的动态网站抓取能力，智能识别页面稳定状态。
- **LLM Sampling**：通过 `extract_prompt` 对网页内容进行提炼，返回精简结果，避免原始页面内容污染调用方上下文。
- **大页面分段处理**：支持 `find_in_page` 在页面中搜索，`cursor` 和 `max_length` 从任意位置续读。
- **人工介入和鉴权**：`require_user_intervention=true` 打开可见浏览器，用户完成登录、验证码或手动操作后继续抓取。登录一次后，后续请求可继续复用登录信息。
- **反爬伪装**：包含 Playwright-Stealth，尽可能模仿真实请求，尽量防止被检测成机器人。
- **代理支持**：支持 `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY`

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
        "BROWSER_LOCALE": "",
        "BROWSER_TIMEZONE_ID": "",
        "ENABLE_PROMPT_EXTRACTION": "true",
        "MAX_FIND_MATCHES": "8",
        "FIND_SNIPPET_MAX_CHARS": "240",
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
| `operation` | `"view" \| "find" \| "sampling" \| "eval"` | `"view"` | 操作类型。<br>• `view`：获取页面正文。<br>• `find`：在正文中查找匹配项。<br>• `sampling`：使用 LLM 从正文中提取信息。<br>• `eval`：在页面环境中执行 JavaScript 并返回结果。 |
| `fetch` | `object` | 见下表 | 页面获取方式与等待策略配置。 |
| `render` | `object` | 见下表 | 正文提取、输出格式及结果窗口控制。 |
| `find` | `object \| null` | `null` | 查找配置。仅当 `operation="find"` 时提供。 |
| `sampling` | `object \| null` | `null` | 提取配置。仅当 `operation="sampling"` 时提供。 |
| `eval` | `object \| null` | `null` | 脚本配置。仅当 `operation="eval"` 时提供。 |

---

### 二、`fetch` 对象

| 路径 | 类型 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- |
| `fetch.mode` | `"dynamic" \| "static"` | `"dynamic"` | 抓取方式。<br>• `dynamic`：使用浏览器加载并执行页面脚本。<br>• `static`：直接 HTTP 请求页面源码。 |
| `fetch.wait_for` | `number \| "auto"` | `"auto"` | 等待策略（仅 `dynamic` 模式有效）。<br>• `"auto"`：自动等待网络空闲且正文区域稳定。<br>• 数字：页面加载后额外等待的秒数。 |
| `fetch.timeout` | `number \| null` | `null` | 抓取超时秒数。超时后返回当前已获取内容。 |
| `fetch.require_user_intervention` | `boolean` | `false` | 用于需要登录、验证码或人工操作的页面。设为 `true` 时将弹出可见浏览器窗口，等待用户操作完成后自动继续抓取。 |

---

### 三、`render` 对象

| 路径 | 类型 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- |
| `render.output_format` | `"markdown" \| "html"` | `"markdown"` | 正文输出格式。 |
| `render.strategy` | `"strict" \| "loose" \| null` | `null` | 正文提取策略。<br>• `strict`：优先保证内容纯度。<br>• `loose`：优先保证内容覆盖。<br>• `null`：使用默认平衡策略。 |
| `render.include_elements` | `Array<"tables" \| "formatting" \| "images" \| "links" \| "comments">` | `["tables", "formatting"]` | 除正文外需要包含的内容类型。 |
| `render.max_length` | `integer` | `8000` | 文本最大长度。 |
| `render.cursor` | `integer \| null` | `null` | 文本起始偏移量。用于继续读取或继续搜索长页面。 |

---

### 四、`find` 对象

| 路径 | 类型 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- |
| `find.query` | `string` | 必填 | 要查找的文本或正则表达式。 |
| `find.regex` | `boolean` | `false` | 是否将 `query` 视为正则表达式处理。 |

---

### 五、`sampling` 对象

| 路径 | 类型 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- |
| `sampling.prompt` | `string` | 必填 | 指导 LLM 从页面正文中提取信息的提示词。 |

---

### 六、`eval` 对象

| 路径 | 类型 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- |
| `eval.script` | `string` | 必填 | 在页面上下文执行的 JavaScript 代码。仅 `dynamic` 模式支持。 |

---

### 七、使用约束

| 规则 | 说明 |
| :--- | :--- |
| 操作专属配置 | 仅当 `operation` 为对应值时，才可提供 `find`、`sampling` 或 `eval` 对象，且三者互斥。 |
| `eval` 模式限制 | `operation="eval"` 时，`fetch.mode` 必须为 `"dynamic"`。 |
| `render.max_length` 作用域 | max length 只对 render 过程产生出的文本长度生效。对其他操作结果不生效。 |
| `render.cursor` 作用域 | 仅对 `view`、`find` 有效。用于从上次返回的 `next_cursor` 位置继续读取或搜索。 |
| 续读一致性 | 使用 `cursor` 续读时，应保持 `output_format` 与 `strategy` 不变，否则偏移位置可能失效。 |

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

额外等待 5 秒：

```yaml
url: https://example.com
operation: view
fetch:
  wait_for: 5
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
render:
  cursor: 300 # 假设这是某个命中的 cursor
  max_length: 300
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

- `DEFAULT_TIMEOUT`：默认超时秒数。
- `NAVIGATION_TIMEOUT`：`dynamic` 导航超时秒数。
- `NETWORK_IDLE_TIMEOUT`：`dynamic` 等待 `networkidle` 的超时秒数。
- `STATIC_FETCH_TIMEOUT`：`static` 请求超时秒数。
- `AUTO_WAIT_TIMEOUT`：`fetch.wait_for=auto` 的最大等待秒数。
- `DEFAULT_MAX_LENGTH`：默认返回长度上限。
- `ENABLE_PROMPT_EXTRACTION`：是否启用 `sampling`。
- `PROMPT_INPUT_MAX_CHARS`：传给 LLM 的最大输入字符数。
- `MAX_FIND_MATCHES`：页内搜索最多返回多少条命中。
- `FIND_SNIPPET_MAX_CHARS`：每条搜索命中的片段长度上限。
- `SCHEMA_LANGUAGE`：schema 描述语言，支持 `zh` / `en`。

### 浏览器 / 会话

- `BROWSER_CHANNEL`：传给 Playwright 的浏览器 channel。
- `BROWSER_SESSION_MODE`：`auth` 或 `profile`，默认 `auth`。
- `BROWSER_AUTH_STORAGE_STATE`：`auth` 模式下 `storage_state.json` 的路径。
- `BROWSER_PROFILE_DIR`：`profile` 模式下 persistent profile 的目录。
- `BROWSER_LOCALE`：浏览器 locale，留空则使用系统默认。
- `BROWSER_TIMEZONE_ID`：浏览器时区，留空则使用系统默认。
- `BROWSER_COLOR_SCHEME`：颜色方案，默认 `light`。
- `BROWSER_VIEWPORT_WIDTH`：viewport 宽度。
- `BROWSER_VIEWPORT_HEIGHT`：viewport 高度。
- `ENABLE_AUTH_STEALTH`：是否在 `auth` 模式启用 stealth，默认 `true`。
- `INTERVENTION_TIMEOUT_SECONDS`：用户人工介入等待超时秒数。

### 代理

- `ENABLE_PROXY`：是否启用代理，默认 `true`。
- `HTTP_PROXY` / `HTTPS_PROXY`：代理地址。
- `NO_PROXY`：Playwright 代理绕过列表。

### 其它

- `ADVANCED_FETCH_ENV_FILE`：显式指定 dotenv 文件。
- `IGNORE_SSL_ERRORS=true`：忽略 HTTPS / SSL 证书错误。

## 本地安装

```bash
uv sync
```

## 测试

```bash
uv run python -m unittest discover -s tests
```
