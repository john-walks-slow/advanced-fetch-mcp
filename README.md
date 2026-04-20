# advanced-fetch-mcp

给 Agent 一个更顺手的网页抓取工具。  
比 vanilla fetch 更能打，又没直接上 Playwright 那么重。

它主要解决三件事：

1. **把网页抓下来**：能跑动态页面，也能兜底走静态请求。
2. **把正文提干净**：尽量少带导航、广告、脚本这些噪音，省 token。
3. **把长页面读顺手**：支持页内搜索、续读、登录后再抓、执行一点页面 JS。

---

## 它能做什么

- **默认更适合现代网页**：默认走 `dynamic`，用 Playwright 抓 JS 渲染后的页面。
- **正文抽取统一用 Trafilatura**：Markdown、HTML、自动等待采样都基于同一套抽取逻辑，结果更稳定。
- **自动等页面“长完整”再抓**：`wait_for=auto` 时，会在页面加载后继续观察正文是否还在明显变化；差不多稳定了再返回，比较适合懒加载页面。
- **支持不同提取风格**：
  - `strict`：更偏正文纯度
  - `loose`：更偏召回，宁可多带一点
  - `none`：用 Trafilatura 默认平衡策略
- **可以保留结构信息**：通过 `extra_elements` 控制是否额外保留 `tables / links / images / comments / formatting`。
- **支持 LLM 二次整理**：给 `extract_prompt`，让模型按你的要求提取重点，减少原始网页内容污染上下文。
- **支持页内搜索和续读**：先 `find_in_page` 找，再用 `cursor` 从对应位置继续往后读，适合超长页面。
- **需要登录也能抓**：`require_user_intervention=true` 会打开可见浏览器，让用户自己登录、过验证码、点选页面，然后继续抓。
- **登录态可以复用**：默认把登录态存成 `storage_state`，下次继续用，不用每次从头登录。
- **比普通自动化更像真人**：默认 `auth` 模式会带 locale、viewport、timezone、Accept-Language，并尝试启用 stealth。
- **代理配置统一**：`dynamic` 和 `static` 两种模式都会按同一套代理配置走，不会一边走代理一边不走。

---

## 什么时候适合用它

比如这些场景：

- 页面是 JS 渲染的，普通 fetch 拿不到真正正文
- 页面很长，只想先搜关键词，再从命中的地方开始读
- 页面能打开，但正文和导航、推荐、脚注混在一起，想尽量提纯
- 网页需要先登录或手动过验证码
- 想在页面里执行一小段 JS，读某个变量、列表长度或 DOM 信息

---

## 安装

```bash
uv sync
uv run playwright install
```

如果你希望启用 stealth，环境里还需要能安装 `playwright-stealth`。当前 `pyproject.toml` 已经把它列进依赖了。

---

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

---

## 参数

| 参数 | 说明 |
| --- | --- |
| `url` | 目标网址。 |
| `mode` | 抓取模式。`dynamic` 用 Playwright；`static` 直接发请求。默认推荐 `dynamic`。 |
| `wait_for` | 只对 `dynamic` 生效。默认是 `auto`，会自动多等一会儿，直到正文趋于稳定；也可以直接传秒数。 |
| `timeout` | 抓取超时秒数。超时后尽量返回当前已经拿到的内容。 |
| `output_format` | 输出格式。`markdown` 返回抽取后的 Markdown；`html` 返回抽取后的 HTML。 |
| `strategy` | 提取策略。`strict` 偏纯，`loose` 偏全，`none` 用默认平衡策略。 |
| `extra_elements` | 额外保留哪些结构。可选：`tables`、`images`、`links`、`comments`、`formatting`。默认只保留 `tables`。 |
| `cursor` | 文本偏移位置。从这里开始续读。 |
| `max_length` | 返回文本的最大长度。 |
| `find_in_page` | 在页面里搜索关键词，返回命中摘要和对应 cursor。 |
| `find_with_regex` | 是否把 `find_in_page` 当正则表达式处理。 |
| `extract_prompt` | 让 LLM 再提炼一次结果。适合“帮我提取价格和标题”这种场景。 |
| `evaluate_js` | 在页面上下文里执行 JavaScript，返回结果。仅支持 `dynamic`。 |
| `require_user_intervention` | 需要用户手动登录、验证、点选页面时设为 `true`。 |

---

## 示例

### 抓一个普通页面正文

```yaml
url: https://example.com
```

### 明确走动态抓取

```yaml
url: https://example.com
mode: dynamic
```

### 走静态抓取

```yaml
url: https://example.com
mode: static
```

### 保留更多内容

```yaml
url: https://example.com
strategy: loose
```

### 保留表格、链接和图片

```yaml
url: https://example.com
extra_elements:
  - tables
  - links
  - images
```

### 页面里搜一个关键词

```yaml
url: https://example.com
find_in_page: 价格
```

### 从某个位置继续往后读

```yaml
url: https://example.com
cursor: 300
max_length: 300
```

### 让模型帮你提炼重点

```yaml
url: https://example.com
extract_prompt: 提取商品名称、价格和促销信息
```

### 执行一小段页面 JS

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

### 先让用户登录，再继续抓

```yaml
url: https://private-site.com
require_user_intervention: true
```

这时会打开可见浏览器，页面右下角会注入一个“我已完成页面操作”按钮。用户处理完登录、验证码或其它手动步骤后点一下，工具再继续。

---

## 会话模式

通过环境变量 `BROWSER_SESSION_MODE` 控制：

### `auth`（默认，推荐）

这一模式会：

- 用普通 browser/context
- 尝试启用 stealth
- 把登录态存成 `storage_state.json`
- 更适合长期使用，也更稳

一般来说，直接用这个就够了。

### `profile`（兼容模式）

这一模式会：

- 直接启动 persistent profile
- 用 `user_data_dir` 保存整套浏览器数据
- **不会启用 stealth**

它主要是为了兼容旧行为保留的。除非你明确想要 persistent profile 语义，否则不太建议用。

---

## 缓存怎么工作

这工具会按 `url + mode` 维护抓取缓存。

现在的行为比较简单：

- **普通抓取 / extract / eval**：默认重新抓页面，并更新缓存
- **`find_in_page` 和 `cursor` 续读**：优先走缓存，不重复抓

所以它更像是：

- 先抓一次页面，写入缓存
- 后面在同一页里搜、跳、续读时复用这次抓取结果

这对长页面会比较顺手，也比较省。

---

## 代理

支持这些环境变量：

- `ENABLE_PROXY`
- `HTTP_PROXY`
- `HTTPS_PROXY`
- `NO_PROXY`

其中：

- `ENABLE_PROXY=true` 时，`dynamic` 和 `static` 都会使用代理
- `ENABLE_PROXY=false` 时，两边都不走代理
- `NO_PROXY` 会参与浏览器代理绕过逻辑

也就是说，代理行为是统一的，不会出现一边走代理、一边偷偷直连的情况。

---

## 环境变量

### 抓取相关

- `DEFAULT_TIMEOUT`：默认超时秒数
- `NAVIGATION_TIMEOUT`：dynamic 导航超时
- `NETWORK_IDLE_TIMEOUT`：dynamic 等待 networkidle 的超时
- `STATIC_FETCH_TIMEOUT`：static 请求超时
- `AUTO_WAIT_TIMEOUT`：`wait_for=auto` 的最大等待时间
- `DEFAULT_MAX_LENGTH`：默认返回长度上限
- `MAX_FIND_MATCHES`：搜索最多返回多少条命中
- `FIND_SNIPPET_MAX_CHARS`：每条命中摘要最多多长
- `ENABLE_PROMPT_EXTRACTION`：是否启用 `extract_prompt`
- `PROMPT_INPUT_MAX_CHARS`：传给 LLM 的最大输入字符数

### 浏览器相关

- `BROWSER_CHANNEL`：传给 Playwright 的 channel
- `BROWSER_SESSION_MODE`：`auth` 或 `profile`
- `BROWSER_AUTH_STORAGE_STATE`：auth 模式下保存登录态的位置
- `BROWSER_PROFILE_DIR`：profile 模式下的 profile 目录
- `BROWSER_LOCALE`：浏览器 locale
- `BROWSER_TIMEZONE_ID`：浏览器时区
- `BROWSER_COLOR_SCHEME`：浏览器颜色模式
- `BROWSER_VIEWPORT_WIDTH` / `BROWSER_VIEWPORT_HEIGHT`：viewport 大小
- `ENABLE_AUTH_STEALTH`：auth 模式下是否启用 stealth
- `INTERVENTION_TIMEOUT_SECONDS`：人工介入等待上限

### 其它

- `ADVANCED_FETCH_ENV_FILE`：显式指定 dotenv 文件
- `IGNORE_SSL_ERRORS=true`：忽略 HTTPS / SSL 证书错误

---

## .env 加载规则

程序启动时会这样找环境变量文件：

1. 先看 `ADVANCED_FETCH_ENV_FILE`
2. 没指定的话，只看当前工作目录下的 `.env`

这样做的好处是比较可控。  
特别是配合 `uv --directory ...` 使用时，不容易误读到别的项目里的 `.env`。

---

## 测试

```bash
uv run python -m unittest discover -s tests
```
