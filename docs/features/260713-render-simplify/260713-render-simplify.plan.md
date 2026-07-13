# Render 参数简化

## 背景

当前 `render` 对象参数过多：
- `engine` / `strategy` / `include_elements` 三个参数本质上只控制两件事：用 trafilatura 还是 markdownify、保留哪些内容
- 用户不需要细粒度的 `include_elements` 控制

## 最终方案

### 1. 新的参数结构

**`render` 对象：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `output_format` | `"markdown" \| "html"` | `"markdown"` | 输出格式（不变） |
| `markdown_engine` | `"article" \| "full"` | `"article"` | article=trafilatura, full=markdownify |
| `render_images` | `bool` | `false` | true 时将图片下载为 base64 data URI 嵌入 markdown |
| `cursor` | `int \| null` | `null` | 续读偏移（保持不变，仍在 render 内） |

**顶层参数：** `max_length` 保持不变（不在 render 内）

**移除的参数：** `engine`, `strategy`, `include_elements`

### 2. 变更清单

#### params.py
- 移除 `FetchEngine`, `ExtractStrategy`, `SemanticExtra` 类型别名
- 新增 `MarkdownEngine = Literal["article", "full"]`
- 新增 `MarkdownEngineParam`, `RenderImagesParam` 定义
- `RenderParams`: 删 `engine`/`strategy`/`include_elements`，增 `markdown_engine`/`render_images`；`cursor` 保持在 RenderParams 内不变
- 移除 `_normalize_include_elements` validator
- `AdvancedFetchParams`: `max_length` 保持顶层，`to_render_config()` 传 `output_format`/`markdown_engine`/`render_images`
- `RenderConfig`: 精简为 `output_format`/`markdown_engine`/`render_images`
- `_validate_semantics`: 移除 markdownify+strategy 互斥校验

#### server.py
- 函数签名不变（`cursor` 在 `render` 内部）

#### workflow.py
- `render_view()` 调用改为新签名 `(html, render_config, base_url=...)`
- `request.render.cursor` 引用保持不变

#### extract.py
- `render_view(html, view, engine)` → `render_view(html, render_config, base_url=None)`
- 新增 `_render_article_view()` — 基于 trafilatura
- 新增 `_render_full_view()` — 基于 markdownify
- 新增 `render_images` 实现：下载 → base64 → data URI 嵌入；失败回退原始 URL
- 移除 `_filter_markdownify_html` 和 `_build_trafilatura_kwargs` 函数
- 其余函数（`search_in_text`, `continue_in_text`, `encode_cursor` 等）不变

#### docs_sync.py
- 约束描述中 `strategy` → `markdown_engine`

### 3. render_images 实现

当 `render_images=True` 时：
1. 从 HTML 中提取所有 `<img>` 标签（src, alt）
2. 找相邻 `<figure>/<figcaption>` 提取 caption
3. 用 `requests` 下载图片（超时 10s，大小上限 5MB）
4. 转 base64，构造 `![alt](data:image/...;base64,...)`
5. 在渲染结果中将 `![alt](url)` 替换为 `![alt](data:...)`
6. 下载失败时保留原始 URL

当 `render_images=False` 时：
- article 引擎：trafilatura `include_images=False`
- full 引擎：从 HTML 移除 img/picture/source/svg/canvas 节点

### 4. 测试变更
- `test_dsl.py`: 更新 defaults/cursor/can_use_cache 测试；新增 markdown_engine/render_images/old params 测试
- `test_extract.py`: 适配新的 RenderConfig；简化 test cases
- `test_docs_sync.py`: 自动通过（sync_docs 后测试）

### 5. 兼容性
- 不再接受 `engine`/`strategy`/`include_elements`，传入会触发 `extra="forbid"` 报错
- Breaking change，客户端需更新调用方式
