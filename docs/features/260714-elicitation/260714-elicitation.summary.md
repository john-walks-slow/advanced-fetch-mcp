# 260714 Elicitation 重构 — Summary

## 背景

`operation="request_human_action"` 原本通过打开可见浏览器并启动 JS 轮询等待用户点击"已就绪"按钮来实现人工介入。需求：

1. 接入 FastMCP 3.4.4 的 `ctx.elicit()` 原生 API，让模型能感知需要用户操作并在用户返回后继续
2. 可选地让模型自定义提示文字
3. 最终统一全量 API 命名为 `elicit`

## 实施要点

### 第一阶段：接入 ctx.elicit()

- 在 `workflow.py` 的 `execute_advanced_fetch()` 中，检测 `operation == "request_human_action"` 时，先 `await ctx.elicit()` 再打开浏览器
- 新增可选参数 `intervention_message` 让模型自定义提示

### 第二阶段：全量重命名为 elicit

所有 `intervention` / `request_human_action` 相关标识符统一为 `elicit`：

| 旧名 | 新名 |
|------|------|
| `operation="request_human_action"` | `operation="elicit"` |
| `intervention_message` 参数 | 移入 `ElicitParams.message` 字段，顶层 `elicit` 对象 |
| `require_user_intervention` | `require_elicit` |
| `intervention_ended_by` | `elicit_ended_by` |
| `EvalInterventionClosedError` | `EvalElicitClosedError` |
| `INTERVENTION_BUTTON_ID` | `ELICIT_BUTTON_ID` |
| `wait_for_intervention_end` | `wait_for_elicit_end` |
| `build_intervention_script` | `build_elicit_script` |
| `intervention_mode` (docs_sync.py 标签) | `elicit_mode` |

### 四层降级策略（workflow.py）

1. 优先调用 `ctx.elicit()`（FastMCP >= 3.4.4）
2. 若抛出 `NotImplementedError` → 打印提示 + 用户输入器
3. 若抛出 `ConnectionCancelledError` → 返回错误
4. 超时（`ELICIT_TIMEOUT_SECONDS`，默认 600s）→ 自动取消

### 兼容性

- 环境变量名 `INTERVENTION_TIMEOUT_SECONDS` 保留（Python 变量名改为 `ELICIT_TIMEOUT_SECONDS`）
- `ElicitParams` 实现了 `model_validate()` 以支持旧 client 传入 `request_human_action` 时自动降级

## 值得注意

- `ctx.elicit()` 返回 `ElicitResult` 对象，需通过 `.is_accepted` / `.is_cancelled` 判断用户行为
- 浏览器打开后同时启动 `ctx.elicit()` 和轮询，任何一个返回即继续，防止用户"一个完成另一个卡住"
- JS 端 window flag 从 `__ADVANCED_FETCH_INTERVENTION_DONE__` 改为 `__ADVANCED_FETCH_ELICIT_DONE__`
