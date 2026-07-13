# 检视报告

## 概要

检视 `extract_links` 功能变更，涵盖 `config_meta.py`、`settings.py`、`params.py`、`extract.py`、`workflow.py`、`docs_sync.py` 及对应测试文件。整体实现与需求对齐度高，逻辑正确，测试覆盖全面。发现一个需确认的命名引用疑点，无其他阻塞性问题。

## 需求对齐

- ✅ `LinksParams` 模型 + `MAX_LINKS_COUNT` 环境变量（默认 30）
- ✅ `render.links` 写入 `ViewParams`，响应经 `_build_public_result` 条件性注入 `links` / `links_total` / `links_truncated`
- ✅ 链接提取：非 http 协议过滤、绝对 URL 去重、排除渲染正文已含链接、同源转相对路径、limit 截断
- ✅ `extract_links` 在所有 render 路径（view/find/sampling/cursor）后调用
- ✅ 文档同步（`docs_sync.py` 新增 `render_links` 段落）
- ✅ 测试覆盖：15 个单元测试 + 2 个集成测试

## 阻塞问题

| ID | 位置 | 问题 | 建议 |
| --- | ---- | ---- | ---- |
| B1 | `advanced_fetch_mcp/params.py:291` | `RenderParam = Annotated[RenderParams, ...]` 引用了 `RenderParams`，但该文件（以及整个代码库）中不存在同名类定义。`ViewParams`（第 237 行）包含了 render 相关字段及 `links` 字段，但并未被 `RenderParam` 引用。 | 确认以下两种场景之一：**场景 A** — 若 `RenderParams` 本应保留，则将 `links` 字段加回 `RenderParams`，或创建 `RenderParams = ViewParams` 别名；**场景 B** — 若 `RenderParams` 有意重命名为 `ViewParams`，则将 `RenderParam` 类型别名中的 `RenderParams` 改为 `ViewParams`。需要核实运行时是否因此出错。 |

## 建议修改

| ID | 位置 | 问题 | 建议 |
| --- | ---- | ---- | ---- |
| S1 | `advanced_fetch_mcp/extract.py:491` | 排除已渲染链接的判断是 `if abs_url in rendered_text`，使用 Python 的 `in` 子串匹配。当 `rendered_text` 中恰好包含另一 URL 的子串时可能误过滤（如 `rendered_text` 中包含 `https://example.com/page` 但待排除的链接是 `https://example.com/page-extra`）。不过在实践中该场景概率极低，且 trafilatura 渲染后的文本中极少出现完整裸 URL。 | 可考虑在未来若出现误报 issue 时加入更严格的 URL 边界匹配（如检查前后空白/标点），当前保持现有行为即可。非紧迫修改。 |
| S2 | `advanced_fetch_mcp/workflow.py:188` | `limit=request.render.links.limit or MAX_LINKS_COUNT` — `LinksLimitParam` 已设 `default=MAX_LINKS_COUNT` 且 `ge=1`，`limit` 永远不会为 0/空值，`or` 回退实际不会触发。 | 可简化为 `limit=request.render.links.limit`。若保留 `or` 建议加简短注释说明意图，避免后续维护者困惑。 |
| S3 | `advanced_fetch_mcp/extract.py:411` | `_SKIPPED_PROTOCOLS` 包含了 `sms:`、`fax:`、`file:` 等协议，需求文档和 plan 中未提及。这些是合理的安全扩展，但与 spec 不一致。 | 若为有意追加，建议更新 plan 文档或在代码注释中注明；若无意添加，建议保持一致或至少提一句。 |


## 非阻塞问题

| ID | 位置 | 问题 | 建议 |
| --- | ---- | ---- | ---- |
| N1 | `tests/test_workflow.py:534-590` | 两个 `render.links` 集成测试均 mock 了 `extract_links`，没有测试 real `extract_links` 与 workflow 的串联。当前覆盖了"是否传递 links_result"的集成逻辑，但未验证真实链接提取结果在完整流程中是否正确传输。 | 可考虑在后续迭代中增加一个不 mock `extract_links` 的 e2e 集成测试，确保真实解析结果正常流入响应。 |
| N2 | `advanced_fetch_mcp/extract.py` | 没有针对超大 HTML（>10k 链接）的性能防护。`extract_links` 会遍历所有 `<a>` 节点并逐一做 URL 解析、去重、渲染文本匹配。若页面链接数极大（如站点地图页），可能耗时较久。 | 当前阶段暂不需要优化。若后续有性能 issue，可考虑添加 `max_links_scan` 上限（扫描超过此数后停止）或使用 `lxml` 的 incremental parsing。 |

## 准入结论

**结论**：`条件准入`

**说明**：**B1** 需要开发者确认 `RenderParam` 类型别名中的 `RenderParams` 引用是否正确——若运行时确实缺少该类定义则必须修复；若实为名称误读（存在等效定义），则无问题。建议尽快核实此点。其余建议项（S1–S3、N1–N2）不影响准入，可在后续迭代中处理。
