# URL 相对化统一处理

## 背景

目前代码中：
- 链接（`<a href>`）已有 `_make_relative_href()` 处理相对化，但写在 `extract.py` 内部，不可复用
- 图片（`<img src>`）在 rendered markdown/html 输出中仍是绝对路径，完全未处理
- 其他资源 URL（`<video src>` 等）也未处理
- 没有统一的 URL 工具层

用户希望所有 URL 优先使用相对路径（同源），且逻辑集中一处，方便复用。

## 方案

### 新建 `url_utils.py` — URL 集中处理模块

提供四个函数，逐步递进：

| 函数 | 输入 | 输出 | 用途 |
|------|------|------|------|
| `is_same_origin(url, base)` | 两个 URL | bool | 判断同源（scheme+netloc） |
| `make_relative_url(url, base)` | 单个 URL + base | str | 同源→相对路径，跨域→原样 |
| `normalize_html_urls(html, base)` | HTML 字符串 + base | str | 处理 HTML 中所有 `src`/`href`/`srcset` |
| `normalize_markdown_urls(text, base)` | Markdown 字符串 + base | str | 处理 Markdown 中 `[...](...)` 和 `![](...)` |

`normalize_html_urls` 处理标签：
- `<a href>` — 已有，迁移过来
- `<img src>` / `<img srcset>` — 新增
- `<video src>` / `<audio src>` / `<source src>` / `<iframe src>` — 一并覆盖
- `<* style="background-image: url(...)">` — 选择性支持（暂不做，优先级低）

### 重构 `extract.py`

- 删除 `_make_relative_href()` / `_is_skipped_href()`
- `extract_links()` 改为从 `url_utils` import
- `render_view()` 在返回前对 rendered 输出做 URL 相对化：
  - 若 `output_format="markdown"` → 调用 `normalize_markdown_urls()`
  - 若 `output_format="html"` → 调用 `normalize_html_urls()`

### 不变项

- API 参数、返回值结构完全不变
- `extract_links()` 输出中 `href` 仍为相对路径、`abs_url` 仍为绝对路径
- 已有测试保持通过（`_make_relative_href` 行为不变，只是换了个位置）

### 变更清单

| 文件 | 变更 |
|------|------|
| `advanced_fetch_mcp/url_utils.py` | **新建**：`is_same_origin`, `make_relative_url`, `normalize_html_urls`, `normalize_markdown_urls` |
| `advanced_fetch_mcp/extract.py` | 删除 `_make_relative_href`/`_is_skipped_href`；改为 import；`render_view()` 末尾增加 URL 相对化后处理 |
| `tests/test_extract.py` | 涉及 `_make_relative_href`（已通过 `extract_links` 间接覆盖）的测试不需改；新增 `url_utils` 单元测试 |
