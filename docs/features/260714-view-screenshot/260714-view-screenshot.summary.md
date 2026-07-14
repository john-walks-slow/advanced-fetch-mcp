# view 新增 screenshot 支持 — Summary

## 背景

用户在 `view` 操作中获取页面截图，并按照 MCP 规范返回 `ImageContent` block 让模型原生看到图片。

## 变更内容

### 1. 默认 Viewport → 1440×900
- `BROWSER_VIEWPORT_WIDTH`: 1366 → 1440
- `BROWSER_VIEWPORT_HEIGHT`: 768 → 900
- 典型笔记本分辨率，截图大小适中

### 2. ViewParams 新增 `with_screenshot` 参数
- `default=False`，仅 `operation="view"` 有效
- 指定 `with_screenshot=True` → 自动切 `fetch.mode="dynamic"`
- refid 不支持截图（报错提示用原始 URL）

### 3. 截图实现
- `FetchResult` 新增 `screenshot: Optional[bytes]` 存原始 PNG 字节
- 页面稳定后调 `page.screenshot(type="png")`，只截 viewport
- **不** base64 编码（交给上层处理）
- 每次请求新开浏览器，不缓存

### 4. MCP 规范响应
- `server.py` 返回 `list[TextContent | ImageContent]`
- 原有 JSON 响应作为 `TextContent`
- 截图作为 `ImageContent`（用 `fastmcp.utilities.types.Image` 自动转）
- 模型原生看到图片，无需 parse JSON data URI

```python
# server.py 核心逻辑
result_dict, screenshot_bytes = await execute_advanced_fetch(...)
blocks = [TextContent(text=json.dumps(result_dict))]
if screenshot_bytes:
    blocks.append(Image(data=screenshot_bytes, format="png"))
return blocks
```

## 涉及文件

| 文件 | 变更 |
|---|---|
| `config_meta.py` | viewport 默认值 1366×768 → 1440×900 |
| `params.py` | `ViewParams.with_screenshot` 字段 + 校验 |
| `fetch.py` | `FetchResult.screenshot: bytes` + 截图捕获 |
| `workflow.py` | 返回 `(dict, bytes | None)` 元组 |
| `server.py` | 返回类型改为 `list[TextContent | ImageContent]` |
| `tests/test_workflow.py` | 适配新返回类型 |
| `tests/test_server_schema.py` | 更新参数列表 |
| `.env.example` / README | 自动同步 |

## 注意
- `ImageContent` 是 MCP 标准的图片返回方式，客户端直接渲染
- `Image` helper 自动处理 base64 编码和 MIME type
- 截图存入 `FetchResult.screenshot` 为原始 bytes，不提前编码
