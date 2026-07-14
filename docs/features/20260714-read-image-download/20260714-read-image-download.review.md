# 检视报告

## 概要

检视 `read_image` 和 `download` 两个新 MCP 工具的实现，涵盖 `server.py` 新增代码及 `tests/test_read_image_download.py` 测试文件。整体实现正确、风格与现有代码一致（复用 USER_AGENT / proxy / SSL 配置、i18n schema_text、PascalCaseParam 命名）。无阻塞问题，存在若干建议改进项。

## 需求对齐

| 需求项 | 状态 | 说明 |
|--------|------|------|
| `read_image` 工具：接收 url(s)，返回 ImageContent | ✅ | 支持 `Union[str, List[str]]`，错误时返回 TextContent |
| `download` 工具：流式下载文件 | ✅ | 流式分块写入，自动创建父目录，overwrite 保护 |
| 复用项目设置（USER_AGENT / proxy / SSL） | ✅ | 三项均正确复用 |
| 格式检测从 Content-Type 推断 | ✅ | `_infer_image_format` 覆盖 png/jpeg/gif/webp/svg+xml，兜底 png |
| 空列表 / None → 返回错误 TextContent | ⚠️ | 空列表 `[]` 返回空结果列表 `[]`，无提示；None 由 Pydantic 拒绝 |
| 仅修改 server.py | ⚠️ | 同时修改了 `params.py` / `workflow.py` / `README.md`（`output_to_file` 特性），与 `read_image`/`download` 无关 |
| 不修改现有工具行为 | ⚠️ | `workflow.py` 改动对所有现有工具的响应新增了 `duration_seconds` 字段 |

## 阻塞问题

无。

## 建议修改

| ID | 位置 | 问题 | 建议 |
|----|------|------|------|
| S1 | `server.py:163` | **download 工具存在路径穿越风险**。`file_path` 为用户/LLM 可控参数，未经任何校验。恶意输入如 `file_path=../../etc/cronjob` 可能将文件写入预期之外的系统路径。项目已有 `output_to_file`（同理）作为先例，但 `download` 作为独立工具暴露面更广，风险更高。 | 至少做路径解析与验证：<br>1. 使用 `os.path.abspath()` / `os.path.realpath()` 解析最终路径<br>2. 可选：提供 `DOWNLOAD_BASE_DIR` 环境变量约束文件写入范围，超出时报错<br>3. 检查解析后的路径是否仍以预期目录为前缀 |
| S2 | `server.py:119-143` | **read_image 对空列表 `[]` 返回无提示的空结果**。当用户传入 `url=[]` 时，函数返回 `[]`（空列表），MCP 客户端收到的是一份无任何内容的响应，用户无法判断是成功（没有图片）还是错误。 | 在 `urls` 为空时返回一条错误 TextContent：<br>`TextContent(type="text", text="No URLs provided.")` |
| S3 | `server.py:124` | **read_image 超时硬编码为 30s**，与 download 的 `timeout` 可配置参数（默认 120s）不一致。对于大图或慢速网络，30s 可能不足。 | 为 `read_image` 也增加 `timeout` 参数，或至少提取为常量命名，保持与 download 一致。 |
| S4 | `server.py:175-190` | **download 在检查文件存在前创建父目录**。`os.makedirs(dir_path, exist_ok=True)` 在 `if not overwrite and os.path.exists()` 之前执行。导致：即使文件已存在且 `overwrite=False`（下载不执行），父目录仍被创建——这是不可回退的副作用。 | 将父目录创建移到 overwrite 检查之后：<br>```python<br>if not overwrite and os.path.exists(file_path):<br>    return error<br>if dir_path:<br>    os.makedirs(dir_path, exist_ok=True)<br>``` |
| S5 | `server.py:130,199` | **read_image 使用 `stream=True` 后又调用 `resp.content`**。`stream=True` 的本意是延迟读取、分块处理，但 `resp.content` 仍把全部数据加载到内存中，`stream=True` 在此无意义且有误导性。而 download 正确使用了 `iter_content` 流式写入。 | 两个选择：(a) 移除 `stream=True` 简化代码；(b) 用 `resp.raw.read()` 或 `iter_content` 做一致性处理 |
| S6 | `server.py:163` | **download 下载失败时残留部分文件**。如果下载中断（网络中断、磁盘满、异常等），部分写入的文件会留在磁盘上。下次重试时若 `overwrite=False` 会报"文件已存在"；若 `overwrite=True` 会覆盖。两种情况都可能让用户困惑。 | 在下载失败时清理部分文件：包在 try/except 中，catch 到异常时删除已创建的文件（`os.remove(file_path)`）。或者使用临时文件 + 重命名原子操作。 |
| S7 | `tests/test_read_image_download.py` | **测试模块导入模式脆弱**。`_import_server()` 反复 pop `sys.modules` 并重新导入所有 `advanced_fetch_mcp` 模块。每次 import 创建新的 `mcp` 单例并重复注册工具。若模块初始化有副作用（如 `urllib3.disable_warnings` 在 `settings.py` 中），多次重入可能导致不可预测行为。 | 改用 `importlib.reload()` + 定向清理，或在模块级共享 fixture 减少重复 import。如果测试框架支持，可每个测试类只 import 一次。 |
| S8 | `tests/test_read_image_download.py:129` | **测试访问了私有属性 `_format`**。`results[0]._format` 是 FastMCP `Image` 类的内部实现细节，可能随版本升级变化。 | 改用 `results[0]._mime_type` 断言（如 `assertEqual("image/jpeg", ...)`），或检查 `to_image_content()` 输出的 `mimeType` 字段。 |
| S9 | `tests/test_read_image_download.py` | **缺失以下测试场景**：<br>- `read_image` 传入空列表 `[]` 时的行为<br>- `read_image` 传入非图片 URL（如 HTML 页面）时的行为<br>- `read_image` 非 200 状态码（`raise_for_status` 触发）<br>- `download` 磁盘无写权限 / 磁盘满 / 路径为目录<br>- `_infer_image_format` 带 charset 的 content-type（如 `image/png; charset=utf-8`） | 补充上述边界情况测试。 |

## 非阻塞问题

| ID | 位置 | 问题 | 建议 |
|----|------|------|------|
| N1 | `server.py:95` | **SVG 格式返回 `"svg+xml"`**。FastMCP `Image._get_mime_type()` 构造结果为 `f"image/svg+xml"`，这是正确且标准的 MIME 类型。`+` 字符可作为 `format` 字符串的一部分。但部分 MCP 客户端可能对 `+` 的处理不一致（URL 编码等）。 | 确认目标 MCP 客户端支持 `image/svg+xml`。若需最广兼容可考虑 fallback 到 `png`。 |
| N2 | `server.py:147-156` | **`overwrite: DownloadOverwriteParam = False` 参数默认值重复**。`DownloadOverwriteParam` 内的 `Field(default=False)` 与函数签名中的 `= False` 都指定了默认值。虽然 Pydantic 会正确处理，但容易让维护者对"默认值从哪里来"产生困惑。 | 删除函数签名中的 `= False`，仅保留 `Field(default=False)` 一处默认值来源，与项目其他参数风格保持一致。 |
| N3 | `server.py:122-131` | **read_image 对大图无 Content-Length 校验**。如果 URL 指向一个很大的文件（如 500MB），`resp.content` 会耗尽内存。但 download 同样无此校验（只是流式写入磁盘避免了 OOM）。 | 可考虑在 read_image 中增加 `max_size` 参数或基于 `Content-Length` header 做预检，超出时报错。 |
| N4 | `server.py:83-96` | **_infer_image_format 放置在 server.py 中**。该函数逻辑独立，与图片格式检测相关，放在 `server.py` 中增加了该文件的职责范围。 | 后续可考虑将 `_infer_image_format` 抽取到 `url_utils.py` 或新建 `image_utils.py`，便于单元测试和复用。 |

## 准入结论

**结论**：`准入`

**说明**：无阻塞性问题。S1（路径穿越）是项目已有模式的延续，建议在当前 PR 中至少增加路径解析防护；S2-S6 为代码质量改进项，建议在合并前或在后续迭代中处理。代码功能正确、风格一致，可进入下一阶段。
