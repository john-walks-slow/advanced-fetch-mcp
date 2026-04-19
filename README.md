# advanced-fetch-mcp

为 Agent 提供快速、强大、节省 Token 的动态网页抓取能力。
比 vanilla fetch 强大，比 Playwright 简单。

## 功能

- **节省 Token**：默认只抓正文，自动剔除 script/style/img/video 等无用节点。支持自定义 `selector`、`strip` 精确控制范围。
- **智能提取**：支持 Sampling 能力，调用 LLM 对内容进行整理，返回精简结果，避免原始页面内容污染调用方的上下文。
- **搜索续读**：`find_in_page` 搜索关键词，返回命中列表。用 `cursor` 从任意命中位置续读，适合大页面分段处理。
- **人工介入**：`require_user_intervention=true` 打开可见浏览器，页面会注入"我已完成操作"按钮。用户登录、过验证码、手动点选后点击按钮，工具继续抓取。
- **登录态持久化**：浏览器 profile 存到 `~/.advanced-fetch-profile`，登录一次后续请求自动保持登录态。
- 支持 HTTP_PROXY / HTTPS_PROXY 代理

## 安装

```bash
uv sync
uv run playwright install
```

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
        "DEFAULT_TIMEOUT": 10,
        "HTTP_PROXY": "",
        "HTTPS_PROXY": "",
        "ENABLE_PROMPT_EXTRACTION": true,
        "MAX_FIND_MATCHES": 8,
        "FIND_SNIPPET_MAX_CHARS": 240
      }
    }
  }
}
```

浏览器 profile 默认存到 `~/.advanced-fetch-profile`。

## 参数

| 参数                        | 说明                                                                                                          |
| --------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `url`                       | 目标网址。                                                                                                    |
| `mode`                      | 页面抓取方式。dynamic 使用 Playwright；static 直接获取页面响应。                                              |
| `wait_for`                  | dynamic 模式下，networkidle 后额外等待秒数（适合有懒加载内容的页面）。                                        |
| `timeout`                   | 抓取超时秒数，超时后返回当前已加载内容。                                                                      |
| `markdownify`               | 是否转换成 Markdown；为 false 时返回原始 HTML。                                                               |
| `scope`                     | 基础范围。可选 full（全页）、body（body）、content（智能选择正文）。                                          |
| `selector`                  | 在基础范围内，再用 CSS selector 选出更小的子区域。                                                            |
| `strip`                     | 在当前范围内，按这些 CSS selector 剔除节点。                                                                  |
| `keep_media`                | 是否保留图片、视频、音频、SVG 等媒体节点。                                                                    |
| `cursor`                    | 文本位置偏移。从该位置续读或继续搜索。                                                                        |
| `max_length`                | 文本结果长度上限。                                                                                            |
| `find_in_page`              | 搜索关键词。返回 matches 列表，适合在长页面中定位关键部分。                                                   |
| `find_with_regex`           | 是否把 find_in_page 按正则表达式处理。                                                                        |
| `prompt`                    | 提取提示词。提供后，调用 LLM 对内容进行整理和提取，返回提取后的结果。可以避免原始页面内容污染调用方的上下文。 |
| `evaluateJS`                | 在页面上下文中执行 JavaScript，返回脚本结果。                                                                 |
| `require_user_intervention` | 需要登录/过验证码时设为 true，打开可见浏览器让用户手动操作，完成后点按钮继续抓取。                            |
| `refresh_cache`             | 是否忽略已有缓存重新抓取。(`require_user_intervention` 和 `evaluateJS` 自动忽略)                              |

## 示例

抓正文：

```yaml
url: https://example.com
scope: content
```

搜索关键词：

```yaml
url: https://example.com
find_in_page: '价格'
```

从搜索结果位置续读：

```yaml
url: https://example.com
cursor: 300 # 假设这是某个命中的 cursor
max_length: 300
```

智能提取（让模型整理）：

```yaml
url: https://example.com
scope: content
prompt: '提取商品名称和价格'
```

需要登录的网站：

```yaml
url: https://private-site.com
require_user_intervention: true
```

会打开可见浏览器，用户登录后点击页面上的"我已完成操作"按钮，工具继续抓取。已登录的 session 会保存到 profile，下次访问自动保持登录态。

## 缓存

最近抓取的网站会按 url + mode 缓存，下次访问、查找无需重新抓取。`require_user_intervention` 和 `evaluateJS` 无视缓存。

## 测试

```bash
uv run python -m unittest discover -s tests
```
