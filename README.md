# advanced-fetch-mcp

advanced-fetch-mcp 是一个面向“高级 fetch”场景的 MCP 服务。

它不尝试替代 Browserbase，也不尝试替代完整的 Playwright 脚本编排。它解决的是另一类问题：当你只想“把一个页面抓下来，再做一点常见处理”时，用一组简单参数稳定完成任务。

它支持的核心能力只有这些：

- 抓取页面
- 输出 Markdown 文本或原始 HTML
- 在结果中搜索并按游标继续读取
- 基于结果做一轮模型整理
- 在页面上下文里执行 JavaScript

## 安装

安装依赖：

```bash
uv sync
```

安装 Playwright 浏览器：

```bash
uv run playwright install
```

启动 MCP 服务：

```bash
uv run advanced-fetch-mcp
```

## 工具

只提供一个工具：`advanced_fetch`。

所有参数都是**顶层平铺参数**，不需要再包一层对象。

最简单的调用：

```yaml
url: https://example.com
mode: dynamic
markdownify: true
scope: content
```

## 环境变量

常用环境变量如下：

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

- `BROWSER_CHANNEL`
  - 只支持 `chrome` 或 `msedge`
- `BROWSER_PROFILE_DIR`
  - 浏览器配置目录
  - dynamic 抓取和 evaluateJS 默认都会使用这个目录
  - 如果不设置，会使用项目目录下的 `.fetch-browser-profile`
- `BROWSER_PROFILE_TEMPLATE_DIR`
  - 可选
  - 如果提供，系统会在启动浏览器前，从这个目录里复制一小部分和登录状态、会话、本地存储相关的数据到 `BROWSER_PROFILE_DIR`
  - 只会补充缺失数据，不会覆盖 `BROWSER_PROFILE_DIR` 里已经存在的内容

## 参数总览

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

## 参数说明

### 抓取参数

- `url`
  - 目标网址
- `mode`
  - `dynamic`：使用浏览器加载页面
  - `static`：直接请求页面响应
- `wait_for`
  - 仅在 `dynamic` 模式下生效
  - 页面导航完成后再额外等待多少秒
- `require_user_intervention`
  - 是否要求人工在浏览器里完成登录、验证或其他操作后再继续
  - 为 `true` 时，页面右下角会注入一个“我已完成页面操作”按钮
  - 用户点击这个按钮，表示“手动操作已经完成，可以继续”

### 结果视图参数

- `markdownify`
  - `true`：把选中的页面范围转换成 Markdown 文本
  - `false`：返回选中的原始 HTML
- `scope`
  - `full`：整个页面文档
  - `body`：`body` 范围
  - `content`：优先选择 `main`、`article` 等正文区域；找不到时退回 `body`
- `selector`
  - 在基础范围内，再用一个 CSS selector 缩小到更小的子区域
- `strip`
  - 在当前范围内，按一组 CSS selector 删除节点
- `keep_media`
  - 是否保留图片、视频、音频、SVG 等媒体节点
  - 默认不保留媒体节点

### 结果处理参数

- `prompt`
  - 字符串
  - 提供后，会先得到当前视图文本，再交给模型整理
- `find_in_page`
  - 一个对象，承担“搜索”和“按游标继续读取/跳转”
- `evaluateJS`
  - 字符串
  - 在真实页面上下文中执行 JavaScript，并返回脚本结果
  - 只支持 `dynamic` 模式
  - 与 `prompt`、`find_in_page` 和视图参数互斥

### 其他参数

- `max_length`
  - 文本结果长度上限
  - 普通提取、`prompt`、`evaluateJS` 会按这个长度截断
  - 搜索时表示结果窗口大小
- `refresh_cache`
  - 是否忽略当前 URL 的已有缓存并重新抓取
  - 重新抓到的结果仍会写回缓存
  - `evaluateJS` 始终忽略缓存

## `find_in_page`

`find_in_page` 仍然保留成对象，因为它同时承担两个动作：

1. 首次搜索
2. 继续读取或跳到某个命中位置

首次搜索示例：

```yaml
find_in_page:
  query: 退款
  regex: false
```

继续读取或跳转示例：

```yaml
find_in_page:
  cursor: 2af
```

字段说明：

- `query`
  - 首次搜索时提供
- `regex`
  - 是否把 `query` 按正则表达式处理
- `cursor`
  - 继续读取或跳转时提供
  - 可以直接使用上一次返回的 `next_cursor`
  - 也可以使用某个匹配项里的 `cursor`

首次搜索返回时，额外可能出现这些字段：

- `found`
- `matches`
- `matches_total`
- `matches_truncated`
- `next_cursor`

其中：

- `matches`
  - 最多返回 8 个命中摘要
  - 每个命中只保留两个字段：
    - `snippet`
    - `cursor`
- `next_cursor`
  - 用于继续读取当前窗口后续内容

## 返回字段

所有成功返回都会包含：

- `success`
- `final_url`
- `result`

按需返回的字段包括：

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

当启用了 `require_user_intervention` 时，可能返回：

- `user_marked_ready`
- `page_closed`
- `timeout`

含义分别是：

- 用户点了“我已完成页面操作”
- 浏览器页面被关闭
- 人工介入等待超时

## 常见例子

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

```yaml
url: https://example.com
mode: dynamic
evaluateJS: |
  return {
    title: document.title,
    href: location.href,
  }
```
