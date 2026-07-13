# Extract Links 能力

## 背景

用户需要一种在查看页面时顺便提取全部外链的能力，用于导航、爬取入口发现等场景。

## 需求

- 在 `render` 对象中新增 `links` 配置，view/find/sampling 等操作渲染页面时可选返回链接列表
- 有数量限制，默认 30 条
- 不包含提取出的正文中已经包含的链接（去重依据：链接的绝对 URL 出现在渲染后的正文文本中则排除）
- 优先显示为相对路径（同源链接转为相对路径；跨域保持绝对路径）

## 方案

### 1. 新增 `LinksParams` 模型（附属在 `RenderParams` 下）

```python
class LinksParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: LinksLimitParam  # 默认 MAX_LINKS_COUNT (30)
```

### 2. 新增环境变量

`MAX_LINKS_COUNT`：默认 `30`。链接提取最多返回多少条链接。

### 3. 实现 `extract_links()` 函数

核心逻辑在 `extract.py` 中新增：

1. 用 lxml 解析 HTML，提取所有 `<a href="...">` 节点
2. 过滤无效协议（javascript:, mailto:, tel:, data:, #fragment-only）
3. 对 href 做 URL 标准化（相对于 base_url 解析为绝对 URL）
4. 以 `abs_url` 去重（保留首次出现）
5. 过滤：若 `abs_url` 出现在渲染后的正文文本中，视为"正文中已包含"，排除
6. 同源链接转换为相对路径（优先显示为相对路径）
7. 按用户 `limit` 截断

返回格式：

```json
{
  "links": [
    {"href": "/relative/path", "text": "链接文本", "abs_url": "https://example.com/relative/path"},
    {"href": "https://external.com", "text": "外部链接", "abs_url": "https://external.com"}
  ],
  "links_total": 50,
  "links_truncated": true
}
```

- `href`：同源为相对路径，跨域为绝对路径
- `text`：锚文本（图片链接取 alt；无文本锚点用空字符串）
- `abs_url`：始终为解析后的绝对 URL，用于精确引用

### 4. 响应结构

任何经过 render 的操作（view/find/sampling/view+cursor），只要设置了 `render.links`，响应中会额外包含：
- `links` - 链接数组
- `links_total` - 总链接数（截断前）
- `links_truncated` - 是否被限制截断

### 5. RenderParams 变化

```python
class RenderParams(BaseModel):
    output_format: OutputFormatParam
    markdown_engine: MarkdownEngineParam
    render_images: RenderImagesParam
    cursor: CursorParam
    links: Optional[LinksParams] = None  # 新增
```

### 6. 变更清单

| 文件 | 变更 |
|------|------|
| `config_meta.py` | 新增 `MAX_LINKS_COUNT` env var spec |
| `settings.py` | 读取 `MAX_LINKS_COUNT` |
| `params.py` | 新增 `LinksLimitParam` / `LinksParams`；`RenderParams` 新增 `links` 字段；`RenderConfig` 保持不变 |
| `extract.py` | 新增 `extract_links()` |
| `workflow.py` | 渲染后若 `request.render.links` 已设置则调用 `extract_links()`；`_build_public_result` 新增 `links_result` 参数 |
| `docs_sync.py` | `SECTION_LABELS` 新增 `render_links` 条目；`render_readme_schema_section` 新增 `LinksParams` 表格渲染 |
| `README.md/en.md` | 运行 `sync_docs` 自动更新 |
| `.env.example` | 运行 `sync_docs` 自动更新 |
| `tests/test_extract.py` | 新增 `extract_links` 单元测试 |
