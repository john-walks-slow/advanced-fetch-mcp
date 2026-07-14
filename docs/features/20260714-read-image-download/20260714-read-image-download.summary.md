# Summary: read_image + download 独立工具

## 背景

原有 `advanced_fetch` 工具功能丰富但较为重度。需要两个轻量独立的工具：
- **read_image**: 直接传入图片 URL，获取并返回为 ImageContent
- **download**: 从 URL 下载文件到本地路径

## 变更概要

### 文件修改

**`advanced_fetch_mcp/server.py`**：
- 新增 `_infer_image_format()` — 从 Content-Type 推断图片格式
- 新增 `read_image` 工具 — 支持单 URL / URL 列表，自动格式检测，可配 timeout
- 新增 `download` 工具 — 流式分块下载，overwrite 保护，自动创建父目录，失败自动清理残留文件
- 将 `import requests` 移至模块级（原在函数内局部 import，不利于测试 mock）

**`tests/test_read_image_download.py`**（新增，25 个测试用例）：
- ReadImageTests（10 个）：单 URL、多 URL、错误处理、格式检测、空列表、charset content-type、HTTP 错误、自定义 timeout
- DownloadTests（6 个）：正常下载、网络错误、文件已存在（含 overwrite）、父目录创建、部分文件清理
- InferImageFormatTests（7 个）：所有图片格式 + 兜底
- ToolRegistrationTests（2 个）：工具注册确认、参数签名验证

### 设计要点

- 复用项目已有设置：`USER_AGENT`、`get_requests_proxies()`、`IGNORE_SSL_ERRORS`
- 使用 `schema_text()` 中英文描述，与项目 i18n 风格一致
- 错误处理：read_image 单 URL 失败不影响其他 URL；download 返回结构化 JSON 错误

### Review 中解决的问题

| Issue | 描述 | 处理 |
|-------|------|------|
| S1 | 路径穿越风险 | 增加 `os.path.abspath()` 解析 |
| S2 | 空列表无提示 | 增加空列表检查，返回错误 TextContent |
| S3 | read_image timeout 硬编码 | 增加 `timeout` 参数 |
| S4 | 目录副作用顺序 | overwrite 检查后再创建父目录 |
| S5 | stream=True 无意义 | 移除 read_image 的 stream=True |
| S6 | 下载失败残留文件 | catch 异常时清理已创建文件 |
| N2 | overwrite 默认值重复 | 保留 Field(default=False) 单一来源 |
| S9 | 缺失测试 | 补充空列表、charset、HTTP 错误、partial cleanup 等测试 |

### 值得注意

- `Image`（`fastmcp.utilities.types`）不是 `mcp.types.ImageContent`，直接调用函数返回的是前者，MCP 框架在传输层自动转换
- `download` 的 overwrite 参数做了安全保护：默认不覆盖已有文件
