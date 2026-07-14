# Plan: read_image + download 独立工具

## 背景

当前仅有一个 `advanced_fetch` 工具，功能丰富但较为重度。用户需要两个轻量独立的工具：
- **read_image**: 直接传入图片 URL，获取并显示图片
- **download**: 从 URL 下载文件到本地路径

## 设计

### `read_image` 工具

| 项目 | 说明 |
|------|------|
| 入参 | `url: Union[str, List[str]]` — 单个或一组图片 URL |
| 出参 | `List[Union[TextContent, ImageContent]]` — 图片以 base64 ImageContent 返回，错误 URL 返回 TextContent 说明 |
| 获取方式 | requests 直连，复用项目 USER_AGENT / 代理 / SSL 设置 |
| 格式检测 | 从 `Content-Type` header 推断格式（png/jpeg/gif/webp），兜底 png |
| 错误处理 | 单个 URL 失败不影响其他 URL，返回错误说明而非中断 |

边界情况：
- 非图片 URL（如 HTML 页面）→ 仍然返回 bytes，用 content-type 判断格式
- 超时 / 404 → 返回 TextContent 错误
- 超大图片 → 直接用 requests 全量下载（与现有 static_fetch 行为一致）
- 空列表 / None → 返回错误 TextContent

### `download` 工具

| 项目 | 说明 |
|------|------|
| 入参 | `url: str` — 下载源 URL；`file_path: str` — 本地保存路径；`timeout: float` — 超时秒数（默认 120） |
| 出参 | JSON TextContent：`{success, file_path, size, content_type}` |
| 获取方式 | requests 流式下载，复用项目 USER_AGENT / 代理 / SSL 设置 |
| 文件写入 | 自动创建父目录（`os.makedirs`），流式写入避免 OOM |
| 覆盖行为 | 已存在的文件将被覆盖 |

边界情况：
- 父目录不存在 → 自动创建
- 网络中断 / 超时 → 返回 `{success: false, error: ...}`
- 文件路径不可写 → 返回错误
- 超大文件 → 流式分块写入（8KB 块），避免内存爆炸

### 复用项目设置

两个工具均使用 `settings.py` 中已有的全局配置：
- `USER_AGENT` — 请求头
- `get_requests_proxies(url)` — 代理
- `IGNORE_SSL_ERRORS` — SSL 证书验证

> 与 `static_fetch` 保持一致，包括注入 auth cookie（`_inject_auth_storage_cookies`），使工具能访问鉴权资源。

### 代码变更

只修改 `/root/projects/advanced-fetch-mcp/advanced_fetch_mcp/server.py`，新增两个 `@mcp.tool()` 函数。

不涉及：
- 不新增文件
- 不修改现有工具行为
- 不修改参数模型
- 不修改同步文档脚本

### 测试计划

新增测试文件 `tests/test_read_image_download.py`，覆盖：
1. `read_image` 正常读取图片（mock requests）
2. `read_image` 无效 URL
3. `read_image` 非图片 content-type
4. `download` 正常下载
5. `download` 目标目录不存在
6. `download` 网络错误
7. 两个工具注册在 FastMCP 上（检查 server.mcp._tool_manager 或类似方式）
