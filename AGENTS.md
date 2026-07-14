## 模块地图

- `params.py` — 参数模型定义：`AdvancedFetchParams`、各 operation 参数（`FindParams`、`SamplingParams`、`EvalParams`、`ElicitParams`）、`FetchConfig`、`ViewConfig` 等
- `server.py` — FastMCP 服务入口，参数校验与路由
- `workflow.py` — 核心编排：fetch → render → cache → return；含 elicit 四层降级逻辑
- `fetch.py` — 页面获取：静态 HTTP 与 Playwright 动态；elicit 时强制 dynamic
- `detection.py` — 页面检测（CAPTCHA/登录墙）+ 浏览器内 JS 轮询辅助（`wait_for_elicit_end` / `build_elicit_script`）
- `render.py` / `render/` — HTML→Markdown 渲染引擎
- `url_utils.py` — URL 相对化、同源判断
- `sampling.py` — LLM 采样提取逻辑
- `config_meta.py` — 环境变量选项定义（单一来源）
- `docs_sync.py` — 自动同步 `.env.example` 与 README 中的 schema/环境变量段落

# Project Agents

## Docs Sync

- 本项目的下列文档段落是由 `advanced_fetch_mcp/docs_sync.py` 从数据源自动生成的。
  - `.env.example` 
  - `README.md`、`README.en.md` 中 `## Schema` 表格和 `## 环境变量` / `## Environment Variables` 整段
- 环境变量选项定义以 `advanced_fetch_mcp/config_meta.py` 为单一来源。
- 请求参数定义以 `advanced_fetch_mcp/params.py` 为单一来源。
- 参数类型校验失败但实现本身符合当前 schema 时，优先修正过时测试，不要为了旧测试放宽参数类型。
- 写 schema 描述时不要重复类型、默认值、可空性等表格已包含的信息，只说明用途、行为和选择建议。
- 提取引擎属于 `render.engine`，不要放到 `fetch` 配置下；`fetch` 只描述页面获取方式与等待策略。
- 修改参数定义后，注意不要手动修改上述文档，而是执行 `python scripts/sync_docs.py` 并检查文档更新成功。

## Extraction Libraries

- 使用 `markdownify` 选项时，先用当前安装版本做一次最小运行验证，再写入实现；文档里的符号名不一定能直接当字符串传入，否则可能触发静默回退并掩盖真实输出差异。

## Links Extraction

- `extract_links()` 从原始 HTML 解析 `<a href>`，不依赖渲染引擎输出。渲染正文仅用于去重（排除已在正文中显示的链接）。
- 同源链接自动转为相对路径，跨域保持绝对路径。`abs_url` 始终为完整 URL。

## URL 相对化（url_utils）

- 所有 URL 相对化逻辑集中在 `advanced_fetch_mcp/url_utils.py`。
- 渲染输出（`render_view()`）末尾自动对同源 URL 做相对化：markdown 输出用 `normalize_markdown_urls()`，HTML 输出用 `normalize_html_urls()`。
- `extract_links()` 的 `href` 字段也是通过 `url_utils.make_relative_url()` 生成的。
- 处理范围：`<img src/srcset>`、`<a href>`、`<video src>`、`<audio src>`、`<source src>`、`<iframe src>`、`<link href>`。
- 域名比较不区分大小写（`netloc.lower()`）。
- 已知限制：不处理 protocol-relative URL（`//example.com/path`），Markdown URL 正则不支持含 `)` 的 URL。
