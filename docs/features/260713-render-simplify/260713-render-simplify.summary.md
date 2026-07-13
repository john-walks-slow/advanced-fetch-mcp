# Render 参数简化

## 变更内容

对 `render` 对象做了大幅简化：

### 移除的参数
- `engine` — 不再直接暴露 trafilatura/markdownify 底层引擎名
- `strategy` — 不再提供 strict/loose 策略控制
- `include_elements` — 不再提供细粒度的内容类型控制

### 新增的参数
- `render.output_format` — 保留，`"markdown"` / `"html"`
- `render.markdown_engine` — `"article"`(trafilatura) / `"full"`(markdownify)
- `render.render_images` — `bool`，默认 `false`；true 时下载图片嵌入 base64 data URI
- `render.cursor` — 从 render 移出又移回，最终留在 render 内
- `max_length` 保持在顶层（不变）

### 核心实现
- `extract.py` 重写：`_render_article_view()` 基于 trafilatura，`_render_full_view()` 基于 markdownify
- `render_images`：下载 → base64 → data URI 嵌入 markdown；失败回退保留原始 URL
- `RenderConfig` 精简为 `output_format` + `markdown_engine` + `render_images`

### 文档同步
- `sync_docs` 生成 README Schema/环境变量章节
- `docs_sync.py` 约束描述更新（`strategy` → `markdown_engine`）

## 测试结果
- `test_dsl.py`：18 tests passed
- `test_extract.py`：16 tests passed
- `test_server_schema.py`：2 tests passed
- `test_docs_sync.py`：3 tests passed
- 总计 33 tests 全部通过

## 注意事项
- **Breaking change**：旧版调用使用 `engine`/`strategy`/`include_elements` 会触发 `extra="forbid"` 报错
- `render_images` 需要 `requests` 库（已存在于依赖中）
- `test_workflow.py`/`test_server_integration.py` 因其他 Agent 的并发修改暂不通过，不属本次变更范围
