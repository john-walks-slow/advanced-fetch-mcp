# 检视报告

## 概要

检视分支为 URL 相对化统一处理变更（new `url_utils.py`，refactor `extract.py`，new `test_url_utils.py`）。整体设计清晰、函数职责单一、重构安全。但存在 1 个集成路径下的功能回归 bug，以及变更范围远大于需求描述（附带移除了图片嵌入全功能），建议修复后准入。

## 需求对齐

- ✅ **URL 相对化逻辑集中**：`url_utils.py` 提供 5 个函数覆盖了同源判断、href 跳过、URL 相对化、HTML/Markdown 后处理，职责清晰
- ✅ **extract.py 内旧函数已删除，改用 url_utils 导入**：`_SKIPPED_PROTOCOLS`、`_is_skipped_href()`、`_make_relative_href()` 均已移除
- ✅ **extract_links() 输出不变**：`href` 仍为相对路径、`abs_url` 仍为绝对路径
- ✅ **28 个 extract 测试全部通过**，45 个新 url_utils 测试全部通过
- ⚠️ **变更范围超出需求描述**：需求只提到 URL 相对化，但实际变更同时移除了整个图片嵌入功能（`render_images` 参数、`_download_image_as_base64`、`_collect_images_from_html`、`_strip_images_from_html`、`_embed_images_in_result`、`import requests`/`import base64`、`params.py` 中 `RenderImagesParam`），涉及 `extract.py`、`params.py`、`test_dsl.py`、`test_server_integration.py` 的额外修改

## 阻塞问题

无。

## 建议修改

| ID | 位置 | 问题 | 建议 |
|----|------|------|------|
| S1 | `extract.py:356` | **`abs_url in rendered_text` dedup 因 URL 相对化而失效**。`workflow.py:171-173` 产生的 `rendered` 文本现在经过 `normalize_html_urls`/`normalize_markdown_urls`，其中 URL 已被转为相对路径（如 `/page`）。但 `extract_links:356` 的 dedup 检查 `abs_url in rendered_text` 使用的是绝对 URL（如 `https://example.com/page`），两者不匹配，导致原本应被去重的链接（已在正文中出现）会额外出现在 links 输出中。 | 在 `abs_url in rendered_text` 后增加 `or href in rendered_text` 检查：<br>```python<br>href = make_relative_url(abs_url, base) if base else abs_url<br>if abs_url in rendered_text or (href != abs_url and href in rendered_text):<br>    continue<br>``` 注意 `href` 需要在 abs_url 检查之后计算（当前第 360 行），需将 `href` 的计算提前。 |
| S2 | 全文 | **变更范围超出需求描述**。URL 相对化变更同时移除了图片嵌入功能（render_images 参数及相关函数）。这是两个独立的功能变更，捆绑在一起增加了检视负担和回滚风险。 | 若图片嵌入移除是有意为之，应更新变更说明或单独提 PR；若为误删，需恢复。当前变更中未涉及图片嵌入的需求描述。 |
| S3 | `url_utils.py:41` | **`is_same_origin` 对 host 大小写敏感**。域名大小写不敏感（RFC 4343），但 `urlparse("http://EXAMPLE.com").netloc` 返回 `"EXAMPLE.com"`，与 `"example.com"` 比较为 False。 | 在比较前对 `u.netloc` 和 `b.netloc` 做 `.lower()`：<br>```python<br>return u.scheme == b.scheme and u.netloc.lower() == b.netloc.lower()<br>``` |
| S4 | `tests/test_url_utils.py:191-197` | **Article markdown 的 URL 归一化测试未真正验证归一化效果**。`test_article_markdown_url_normalized` 只断言了 `"Title" in result`，未检查 URL 是否被相对化。trafilatura 的 markdown 输出格式可能不会生成 `[text](url)` 格式的链接，但测试至少应验证 `base_url` 未出现在结果中。 | 增加断言检查归一化效果，或补充注释说明 trafilatura 在此场景下不输出 markdown 链接格式。 |

## 非阻塞问题

| ID | 位置 | 问题 | 建议 |
|----|------|------|------|
| N1 | `url_utils.py:33` | **Markdown URL 正则不能处理含 `)` 的 URL**。`[^)]+` 会在遇到第一个 `)` 时停止，无法匹配 `[link](https://en.wikipedia.org/wiki/C_(language))`。 | 这是正则解析 Markdown 的已知限制，当前可接受。若后续需要支持，可用更完善的解析方案或限制 URL 中不出现未转义的 `)`。 |
| N2 | `url_utils.py:18` | **HTML 正则不处理 protocol-relative URL**。`//example.com/path` 不会被匹配，因为正则要求 `https?://` 开头。 | Protocol-relative URLs 使用率已大幅下降，当前可接受。如需支持可在未来扩展正则。 |
| N3 | `url_utils.py:64-66` | **`make_relative_url` 对 fragment-only 结果返回 `#frag` 而非 `/`**。当输入为 `https://example.com#section` 时，`urlunparse` 返回 `#section`（truthy），不会 fallback 到 `"/"`。 | 这不是错误（fragment-only 结果有其含义），但行为与 `result or "/"` 的注释预期不完全一致。建议补充测试覆盖此场景。 |
| N4 | `tests/test_url_utils.py` | **`test_same_origin_with_query` 测试名称与函数不对应**。`test_same_origin_with_query` 位于 `MakeRelativeUrlTests` 下，测试的是 `make_relative_url` 而非 `is_same_origin`，名称易混淆。 | 建议重命名为 `test_same_origin_url_with_query` 或在类内保持命名风格一致。 |
| N5 | `extract.py:130-131` | **`markdown_engine` 参数名与 markdownify 的 `engine` 概念易混淆**。`markdown_engine` 实际控制的是使用 article（trafilatura）还是 full（markdownify），而不是 markdownify 内部引擎选择。 | 文档已说明两者区别，命名属于历史遗留，无需修改。 |

## 准入结论

**结论**：`条件准入`

**说明**：无阻塞问题，但存在建议修改项。**S1（dedup 失效）是集成路径下的功能回归，影响实际用户体验，建议在合并前修复**。S2（超范围变更）虽不致命，但建议明确变更意图。修复 S1 后可准入。
