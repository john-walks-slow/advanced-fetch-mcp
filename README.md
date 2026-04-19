# advanced-fetch-mcp

`advanced-fetch-mcp` 是一个只做一件事的 MCP Server：把页面抓下来，再做少量高频后处理。

它不替代完整浏览器自动化，也不替代 Browserbase/Playwright 编排。它适合这类调用：

- 抓网页正文
- 返回 Markdown 或原始 HTML
- 在结果里搜索并按游标续读
- 对提取文本做一轮 prompt 整理
- 在真实页面上下文执行 JavaScript

## 能力概览

只暴露一个工具：`advanced_fetch`

核心特性：

- `dynamic` 和 `static` 两种抓取模式
- `full` / `body` / `content` 三种视图范围
- `selector` 和 `strip` 做局部提取
- `find_in_page` 做搜索和续读
- `evaluateJS` 在页面里执行脚本
- `require_user_intervention` 支持人工登录或过验证后继续

## 安装

### 1. 安装依赖

```bash
uv sync
```

### 2. 安装 Playwright 浏览器

```bash
uv run playwright install
```

### 3. 可选：复制环境变量模板

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

## 启动

```bash
uv run advanced-fetch-mcp
```

项目入口定义在 `pyproject.toml`：

- 命令名：`advanced-fetch-mcp`
- 入口：`advanced_fetch_entry:main`

## MCP Server 配置建议

推荐把浏览器 profile 放到仓库外面，否则真实抓取后会持续污染 git 工作区。

例如：

```env
BROWSER_PROFILE_DIR=C:\Users\John\.advanced-fetch-profile
```

或：

```env
BROWSER_PROFILE_DIR=/Users/you/.advanced-fetch-profile
```

### Claude Desktop

Windows 示例：

```json
{
  "mcpServers": {
    "advanced-fetch": {
      "command": "uv",
      "args": [
        "--directory",
        "D:\\+Projects\\Coding\\advanced-fetch-mcp",
        "run",
        "advanced-fetch-mcp"
      ],
      "env": {
        "BROWSER_CHANNEL": "chrome",
        "BROWSER_PROFILE_DIR": "C:\\Users\\John\\.advanced-fetch-profile"
      }
    }
  }
}
```

macOS / Linux 示例：

```json
{
  "mcpServers": {
    "advanced-fetch": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/advanced-fetch-mcp",
        "run",
        "advanced-fetch-mcp"
      ],
      "env": {
        "BROWSER_CHANNEL": "chrome",
        "BROWSER_PROFILE_DIR": "/Users/you/.advanced-fetch-profile"
      }
    }
  }
}
```

### 其他 MCP Client

只要客户端支持 `stdio` 型 MCP Server，思路都一样：

- `command`: `uv`
- `args`: `["--directory", "<repo-path>", "run", "advanced-fetch-mcp"]`
- `env`: 按需传 `BROWSER_CHANNEL`、`BROWSER_PROFILE_DIR` 等变量

如果你的运行环境更适合直接执行 Python，也可以用：

```json
{
  "command": "uv",
  "args": [
    "--directory",
    "/path/to/advanced-fetch-mcp",
    "run",
    "python",
    "advanced_fetch_entry.py"
  ]
}
```

## 环境变量

常用环境变量：

```env
DEFAULT_TIMEOUT=10
STATIC_FETCH_TIMEOUT=10

BROWSER_CHANNEL=chrome
BROWSER_PROFILE_DIR=/path/to/fetch-browser-profile
BROWSER_PROFILE_TEMPLATE_DIR=/path/to/your/chrome-or-edge-profile

ENABLE_PROMPT_EXTRACTION=true
PROMPT_INPUT_MAX_CHARS=16000
PROMPT_OUTPUT_MAX_TOKENS=1200

MAX_FIND_MATCHES=8
FIND_SNIPPET_MAX_CHARS=240
```

说明：

- `DEFAULT_TIMEOUT`
  - 同时影响导航超时和 `networkidle` 等待时间
- `STATIC_FETCH_TIMEOUT`
  - `static` 模式的请求超时
- `BROWSER_CHANNEL`
  - 只支持 `chrome` 或 `msedge`
- `BROWSER_PROFILE_DIR`
  - `dynamic` 抓取和 `evaluateJS` 默认都会使用这个目录
  - 不设置时，默认使用项目目录下的 `.fetch-browser-profile`
  - 实际使用建议显式改到仓库外
- `BROWSER_PROFILE_TEMPLATE_DIR`
  - 可选
  - 启动前从已有浏览器配置中复制登录态和本地存储相关数据
  - 只补缺失数据，不覆盖现有 profile
- `ENABLE_PROMPT_EXTRACTION`
  - 关闭后，`prompt` 参数不可用

## 工具参数

`advanced_fetch` 的参数全部是顶层平铺参数，不需要再包一层对象。

最小调用：

```yaml
url: https://example.com
mode: dynamic
markdownify: true
scope: content
```

完整参数：

```yaml
url: https://example.com

mode: dynamic
wait_for: 0
require_user_intervention: false

markdownify: true
scope: content
selector: null
strip: []
keep_media: false

prompt: null
find_in_page: null
evaluateJS: null

max_length: 20000
refresh_cache: false
```

### 抓取参数

- `url`
  - 目标网址
- `mode`
  - `dynamic`：使用浏览器加载页面
  - `static`：直接请求页面响应
- `wait_for`
  - 仅在 `dynamic` 模式下生效
  - 页面导航完成后额外等待的秒数
- `require_user_intervention`
  - 为 `true` 时，会打开非 headless 浏览器并注入“我已完成页面操作”按钮
  - 适合登录、过验证或手动点选之后再继续抓取

### 结果视图参数

- `markdownify`
  - `true`：返回 Markdown
  - `false`：返回原始 HTML
- `scope`
  - `full`：整个文档
  - `body`：`body` 范围
  - `content`：优先 `main`、`article` 等正文区域，找不到时回退 `body`
- `selector`
  - 在基础范围内继续用 CSS selector 缩小区域
- `strip`
  - 在当前范围内删除一组 CSS selector 命中的节点
- `keep_media`
  - 默认会移除图片、视频、音频、SVG 等媒体节点

### 结果处理参数

- `prompt`
  - 把当前视图文本交给模型再整理一轮
- `find_in_page`
  - 在提取文本里搜索，或者用游标继续读取
- `evaluateJS`
  - 在真实页面上下文里执行 JavaScript
  - 只支持 `dynamic`
  - 与 `prompt`、`find_in_page`、`markdownify`、`scope`、`selector`、`strip`、`keep_media` 互斥

### 其他参数

- `max_length`
  - 文本结果长度上限
  - 普通提取、`prompt`、`evaluateJS` 都会按它截断
  - 搜索模式下表示窗口大小
- `refresh_cache`
  - 忽略当前 URL 对应的已有缓存并重新抓取

## `find_in_page`

`find_in_page` 保持为对象，因为它承担两个动作：

1. 首次搜索
2. 继续读取 / 跳转到命中位置

首次搜索：

```yaml
find_in_page:
  query: 退款
  regex: false
```

续读或跳转：

```yaml
find_in_page:
  cursor: 2af
```

字段说明：

- `query`
  - 首次搜索时提供
- `regex`
  - 是否按正则处理 `query`
- `cursor`
  - 继续读取或跳转时提供
  - 可以直接使用上次返回的 `next_cursor`
  - 也可以使用 `matches` 中某个命中的 `cursor`

首次搜索返回时，可能额外包含：

- `found`
- `matches`
- `matches_total`
- `matches_truncated`
- `next_cursor`

其中：

- `matches`
  - 默认最多返回 8 个命中摘要
- 每个命中只保留：
  - `snippet`
  - `cursor`

## 返回字段

所有成功结果都会包含：

- `success`
- `final_url`
- `result`

按需返回：

- `timed_out`
- `timeout_stage`
- `warnings`
- `truncated`
- `intervention_ended_by`
- `found`
- `matches`
- `matches_total`
- `matches_truncated`
- `next_cursor`

### `intervention_ended_by`

启用 `require_user_intervention` 时，可能返回：

- `user_marked_ready`
- `page_closed`
- `timeout`

含义分别是：

- 用户点击了“我已完成页面操作”
- 浏览器页面被关闭
- 人工介入等待超时

## 使用示例

### 抓正文 Markdown

```yaml
url: https://example.com
mode: dynamic
markdownify: true
scope: content
```

### 抓正文 HTML

```yaml
url: https://example.com
mode: dynamic
markdownify: false
scope: content
```

### 去掉广告区再抓正文

```yaml
url: https://example.com
mode: dynamic
markdownify: true
scope: content
strip:
  - .share
  - .related
  - .ad
```

### 搜索关键词

```yaml
url: https://example.com
mode: dynamic
markdownify: true
scope: content
find_in_page:
  query: 退款
```

### 跳到某个匹配

```yaml
url: https://example.com
mode: dynamic
markdownify: true
scope: content
find_in_page:
  cursor: 2af
```

### 人工登录后继续抓取

```yaml
url: https://example.com
mode: dynamic
require_user_intervention: true
markdownify: true
scope: content
```

### 在页面里执行 JavaScript

函数体风格：

```yaml
url: https://example.com
mode: dynamic
evaluateJS: |
  return {
    title: document.title,
    href: location.href,
  }
```

表达式风格：

```yaml
url: https://example.com
mode: dynamic
evaluateJS: document.title
```

箭头函数风格：

```yaml
url: https://example.com
mode: dynamic
evaluateJS: |
  () => ({
    title: document.title,
    href: location.href,
  })
```

## 缓存行为

- 只有非 `evaluateJS` 请求会命中抓取缓存
- 缓存按这些条件区分：
  - `url`
  - `mode`
  - `wait_for`
  - `require_user_intervention`
- `refresh_cache: true` 会强制重新抓取

## 验证

本地测试：

```bash
uv run python -m unittest discover -s tests
```

## 适用边界

适合：

- 从网页取正文
- 在稳定页面上做轻量后处理
- 要求参数少、调用简单的 MCP 场景

不适合：

- 跨多个页面的复杂流程
- 需要精细点击、表单、上传、下载编排
- 完整浏览器测试自动化
