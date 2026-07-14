# URL 相对化统一处理 — 总结

## 背景

代码中 URL 处理分散：
- 链接（`<a href>`）已有 `_make_relative_href()` 在 `extract.py` 内部
- 图片（`<img src>`）在 rendered markdown/HTML 输出中是绝对路径，未处理
- 没有统一的 URL 工具层

## 做了什么

### 1. 新建 `advanced_fetch_mcp/url_utils.py`
集中 5 个函数：
- `is_same_origin(url, base)` — 判断同源（域名大小写不敏感）
- `is_skipped_href(href)` — 跳过非 HTTP 协议
- `make_relative_url(url, base)` — 同源 URL 转相对路径
- `normalize_html_urls(html, base)` — 处理 HTML 中 `src`/`href`/`srcset`
- `normalize_markdown_urls(text, base)` — 处理 Markdown 中 `[...](...)` 和 `![](...)`

### 2. 重构 `extract.py`
- 删除 `_SKIPPED_PROTOCOLS`、`_is_skipped_href()`、`_make_relative_href()`
- `extract_links()` 从 `url_utils` import
- `render_view()` 末尾对 rendered 输出做 URL 相对化后处理
- `extract_links()` 的 dedup 逻辑同时检查绝对 URL 和相对 URL 两种形式

### 3. 测试
- `tests/test_url_utils.py`：47 个 url_utils 单元测试 + 6 个 render_view 集成测试
- 全部已有测试保持通过

## 注意事项
- Article engine（trafilatura）的 markdown 输出不包含 `[]()` 格式的 URL，因此 normalize_markdown_urls 对其无效果；Full engine（markdownify）的 markdown 输出正常生效
- `normalize_html_urls` 对 HTML 格式输出在所有 engine 下生效
- 不处理 protocol-relative URL（`//example.com/path`）和 Markdown URL 中包含 `)` 的情况（已知限制）
