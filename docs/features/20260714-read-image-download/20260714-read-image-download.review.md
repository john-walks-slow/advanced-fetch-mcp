# 检视报告

## 概要

检视 `read_image` 和 `download` 两个新 MCP 工具的实现，涵盖 `server.py` 新增代码及 `tests/test_read_image_download.py` 测试文件（25 个用例）。整体实现正确、风格与项目现有代码一致（复用 USER_AGENT/proxy/SSL 配置、i18n schema_text、Session 模式），边界情况处理充分。无阻塞问题，存在若干建议改进项与非阻塞记录。

## 需求对齐

| 需求 | 状态 | 说明 |
|------|------|------|
| `read_image` 工具：接收 url(s)，返回 ImageContent | ✅ | 支持 `Union[str, List[str]]`，错误时返回 TextContent |
| `download` 工具：流式下载文件 | ✅ | 流式分块写入，自动创建父目录，overwrite 保护，失败清理 |
| 复用项目配置（USER_AGENT/proxy/SSL/cookies） | ✅ | 使用 Session 模式，与 `static_fetch` 一致 |
| 仅修改 server.py，不新增文件 | ⚠️ | 新增了测试文件（符合计划），README/AGENTS.md 同步更新 |
| 测试覆盖 | ✅ | 25 个用例，覆盖正常、错误、边界、工具注册 |

### 与计划偏差说明

计划文档明确写 "不注入 auth cookie（对于图片 / 文件下载，auth cookie 通常不相关）"，但最终实现（commit `035c863`）在两工具中都调用了 `_inject_auth_storage_cookies(session)`。这是**有意为之的正确改进**——使工具能访问鉴权资源（如私有图片、受保护文件），功能上优于原计划。建议更新计划文档以对齐实际行为。

## 阻塞问题

无。

## 建议修改

| ID | 位置 | 问题 | 建议 |
|----|------|------|------|
| S1 | `server.py:219` | **`read_image` 的 `timeout` 参数存在双重默认值**。`ReadImageTimeoutParam` 的 `Field(default=30.0)` 与函数签名 `= 30.0` 分别定义了两次默认值，若不同步则 schema 与运行时行为不一致。而 `download` 的 `timeout` 仅在函数签名中定义了一次。 | 统一风格：要么全部在 Annotated Field 中定义默认值（函数签名不写），要么全部在函数签名中定义。建议按 `download` 的模式，去掉 `ReadImageTimeoutParam` 的 `Field(default=...)`，仅在函数签名保留 `= 30.0`。 |
| S2 | `server.py:192-202` | **`ReadImageTimeoutParam` 和 `ReadImageUrlParam` 类型别名仅各使用一次，增加了间接性但没有复用价值**。而 `download` 采用内联 `Field` 定义更为直接。 | 考虑内联这些类型，移除不必要的类型别名，或统一提取为项目级可复用的类型定义。 |
| S3 | `server.py:216,279` | **两工具的 `ctx: Context` 参数均未被使用**。对于 `download` 的大文件场景，用户无法感知下载进度；调试时也无法知晓内部状态。项目其他工具（如 `advanced_fetch`）也未使用 `ctx`，但新工具有机会做得更好。 | 使用 `ctx.info()` / `ctx.report_progress()`（如果 FastMCP 支持）记录关键步骤，或至少用 `ctx.info` 记录错误/完成日志。**（低优先级）** |
| S4 | `server.py:248` | **`read_image` 对大图无大小限制**。对于非常大的图片（如 100MB+），`resp.content` 全部加载到内存可能 OOM。而 `download` 流式写入磁盘避免此问题。 | 考虑增加可选 `max_size` 参数，或对 `Content-Length` header 做预检（存在时），超出时返回错误提示。**（低优先级，可后续迭代）** |
| S5 | `README.md` | **`read_image` timeout 文档为 `30`，与代码默认值 30.0 一致但未说明单位**。`download` timeout 文档为 `120` 同理。虽然从上下文可推断是秒，但明确标注更友好。 | 在 README 工具表格描述中追加单位说明，如 "超时秒数" → "超时秒数（默认 30）"。 |
| S6 | `docs/features/20260714-read-image-download/20260714-read-image-download.summary.md` | **Summary 未记录 auth cookie 注入的行为变更**。计划文档、review 问题和 summary 都需要与实际实现一致。 | 更新 summary，在 "设计要点" 或 "Review 中解决的问题" 中补充：决定注入 auth cookie 以支持鉴权资源。 |

## 非阻塞问题

| ID | 位置 | 问题 | 建议 |
|----|------|------|------|
| N1 | `server.py:176-189` | **SVG 格式支持**。`_infer_image_format` 对 `image/svg+xml` 返回 `"svg+xml"`，最终 MIME 为 `image/svg+xml`。许多 MCP 客户端不支持 SVG 作为图片渲染，可能显示异常或无显示。 | 保持现状，仅将 SVG 作为额外的功能；或增加配置项让用户选择是否排除 SVG。目前无实际用户反馈，无需过度设计。 |
| N2 | `server.py:294-308` | **`download` 的 overwrite 检查在 try 外部**，如果 `os.path.exists` 和 `os.makedirs` 之间目录被删除，`makedirs` 仍然重新创建了目录即使最终不下载。理论上不影响正确性，但存在极小竞态窗口。 | 可接受，无需修改。如需改进，将 makedirs 移到 try 块内。 |
| N3 | `tests/test_read_image_download.py` | **测试 `_import_server` 模式仍较脆弱**。当前只 pop server 模块（比以前全 purge 好），但仍依赖 `sys.modules` 的副作用顺序。 | 考虑改用类级别的 `import` 配合 `importlib.reload()`，或考虑在测试基类中统一管理。 |
| N4 | `tests/test_read_image_download.py:123` | **测试通过 `_format` 私有属性断言图片格式**。`_format` 是 `FastMCP Image` 的内部属性，API 不公开。 | 改用 `results[0]._mime_type`（同样私有，但更接近协议层输出），或检查框架是否有公开的 format 访问器。如现有项目测试已使用该属性，可容忍。 |
| N5 | `server.py:342` | **`download` 成功响应的 `content_type` 从 `resp.headers` 读取，此时 `with session` 块已退出**。虽然 `resp` 对象仍然存活且 headers 可用，但逻辑上不够直观。 | 可在 `with session` 块内提前提取 `content_type = resp.headers.get("content-type", "")`，然后在返回值中引用变量，更清晰。 |
| N6 | `server.py:350-354` | **下载失败清理残留文件时使用了 `Exception` 兜底**（`try: os.remove(abs_path) except Exception: pass`）。吞掉了所有异常，包括权限错误等本应上报的问题。 | 仅捕获 `OSError` 或 `PermissionError`，保留其他异常的可观测性。 |

## 准入结论

**结论**：`准入`

**说明**：代码质量高，与项目风格一致，测试充分（25/25 通过）。无阻塞问题，建议修改项均为可优化项，可在后续迭代中处理。
