# advanced-fetch-mcp

为 Agent 提供快速、强大、节省 Token 的动态网页抓取能力。
比 vanilla fetch 强大，比 Playwright 简单。

## 功能

- **智能提取**：使用 trafilatura 自动识别正文、剔除广告导航等噪音，节省 Token。
- **灵活策略**：`strategy` 选择提取模式——strict 精确、loose 保留更多、none 返回完整 body。
- **LLM 整理**：提供 `extract_prompt` 让模型对内容进行提炼，返回精简结果，避免原始页面污染上下文。
- **搜索续读**：`find_in_page` 搜索关键词，返回命中列表。用 `cursor` 从任意位置续读，适合大页面分段处理。
- **人工介入**：`require_user_intervention=true` 打开可见浏览器，用户完成登录/验证码后继续抓取。
- **登录态持久化**：浏览器 profile 存到 `~/.advanced-fetch-profile`，登录一次后续请求自动保持登录态。
- 支持 HTTP_PROXY / HTTPS_PROXY 代理

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

## 参数

| 参数                        | 说明                                                                                              |
| --------------------------- | ------------------------------------------------------------------------------------------------- |
| `url`                       | 目标网址。                                                                                        |
| `mode`                      | 页面抓取方式。dynamic 使用 Playwright；static 直接获取页面响应。                                  |
| `wait_for`                  | dynamic 模式下，networkidle 后额外等待秒数（适合有懒加载内容的页面）。                            |
| `timeout`                   | 抓取超时秒数，超时后返回当前已加载内容。                                                          |
| `output_format`             | 输出格式。`markdown` 返回 Markdown；`html` 返回原始 HTML。                                        |
| `strategy`                  | 提取策略。strict 提取最小正文；loose 优先避免误删；none 返回完整 body。                           |
| `strip_selectors`           | 按 CSS selector 剔除节点。默认剔除媒体标签（video/audio/img 等）。传空列表保留全部。              |
| `cursor`                    | 文本位置偏移。从该位置续读或继续搜索。（受输出格式和提取策略影响）                                |
| `max_length`                | 结果长度上限。                                                                                    |
| `find_in_page`              | 页面内搜索，返回 matches 列表，适合在长页面中定位关键部分。                                       |
| `find_with_regex`           | 是否把 find_in_page 按正则表达式处理。                                                            |
| `extract_prompt`            | 提取提示词。提供后，调用 LLM 整理内容，返回提取后的结果。可以避免原始页面内容污染调用方的上下文。 |
| `evaluate_js`               | 在页面上下文中执行 JavaScript，返回脚本结果。                                                     |
| `require_user_intervention` | 需要登录/过验证码时设为 true，打开可见浏览器让用户手动操作，用户操作完成后自动继续。              |
| `refresh_cache`             | 是否忽略已有缓存重新抓取。（`require_user_intervention` 和 `evaluate_js` 自动忽略缓存）           |

## 示例

抓正文（默认 strict 策略，智能剔除广告导航）：

```yaml
url: https://example.com
```

保留更多内容（loose 策略）：

```yaml
url: https://example.com
strategy: loose
```

返回完整 body（包含导航等）：

```yaml
url: https://example.com
strategy: none
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

智能提炼（让模型整理）：

```yaml
url: https://example.com
extract_prompt: '提取商品名称和价格'
```

需要登录的网站：

```yaml
url: https://private-site.com
require_user_intervention: true
```

会打开可见浏览器，用户登录后点击页面上的"我已完成操作"按钮，工具继续抓取。已登录的 session 会保存到 profile，下次访问自动保持登录态。

## 缓存

最近抓取的网站会按 url + mode 缓存，下次访问、查找无需重新抓取。`require_user_intervention` 和 `evaluate_js` 无视缓存。

## 本地安装

```bash
uv sync
uv run playwright install
```

## 测试

```bash
uv run python -m unittest discover -s tests
```
