# 为 request_human_action 接入 Elicitation 交互

## 背景

目前 `operation="request_human_action"` 的行为：
1. 强制 `fetch.mode = "dynamic"`
2. 直接打开可见浏览器 + 注入遮罩脚本
3. 用户操作后点 "Done" 或关页面
4. 返回当前页面内容

问题：没有向用户解释"为什么需要操作"、"要做什么"的环节。模型也无法在触发前提供上下文说明。

## 目标

在打开浏览器前，使用 MCP Elicitation（`ctx.elicit()`）弹出交互式确认/选择，让模型可以说明需要用户做什么，用户确认后才开浏览器。

## 设计方案

### 核心改动

在执行 `fetch_url()` 之前插入 Elicitation 步骤：

```
用户调用 operation="request_human_action"
  ↓
Elicitation: 模型提供 message 说明需要用户做什么
  ↓ Accept
    打开可见浏览器（现有流程）
  ↓ User Done / Close
    正常返回
  ↓ Decline / Cancel
    返回提示信息，不操作
```

### 具体修改

#### 1. `workflow.py` — `execute_advanced_fetch()`

在 L124（`require_intervention = ...`）之后，`fetch_url()` 之前，增加 Elicitation：

```python
if request.operation == "request_human_action":
    # 构造模型友好的 message
    message = (
        f"需要您手动操作网页：{url}\n"
        "即将打开浏览器，请完成登录/验证码等操作后关闭页面。"
    )
    # 也可以用 params 里预留的 message 参数让模型自定义
    result = await ctx.elicit(message, response_type=Literal["accept"])
    if isinstance(result, (DeclinedElicitation, CancelledElicitation)):
        return {"success": False, "error": "用户取消了手动操作"}, None
```

#### 2. 参数设计

**方案 A（推荐）**：不增加参数。由 Server 在 tool handler 中根据 `operation` 自动构造 message，模型在调用 tool 时通过自然语言说明意图即可。

**方案 B**：在 `request_human_action` 对应参数中增加可选的 `message` 字段，让模型能自定义提示文字。但这样会污染参数 schema。

选择方案 A，保持 schema 不变，Elicitation message 由 server 自动生成 + 模型在自然语言中描述。

#### 3. 错误处理

| 用户操作 | 行为 |
|---------|------|
| Accept | 按现有流程打开可见浏览器 |
| Decline | 返回 `{"success": False, "error": "用户取消了操作"}` |
| Cancel | 同上 |
| Elicitation 不支持 (客户端抛异常) | 记录 warning，**fallback 到直接开浏览器**（原有行为） |

#### 4. 上下文传递

`ctx` 已经传入 `execute_advanced_fetch()`，可以直接使用。

需要新增 import：
```python
from fastmcp import Context
# 或者 elicit 相关的类型
```

### 改动文件清单

| 文件 | 改动 |
|------|------|
| `advanced_fetch_mcp/workflow.py` | 增加 Elicitation 逻辑，处理 accept/decline/cancel |
| `tests/test_workflow.py` | 添加 elicitation 相关测试 |

### 不修改的文件

- `params.py`：不增加参数，保持 schema 不变
- `server.py`：ctx 已传入，不需要改动
- `fetch.py`：浏览器逻辑不变
- `README.md`：`request_human_action` 的行为有变化但对外 API 不变，不需要更新（下次 sync docs 时自动更新）

## 风险与考虑

1. **客户端兼容性**：不支持的客户端会返回 `action: "cancel"`（如 Claude Desktop）或抛异常。通过 fallback 到直接开浏览器保证兼容。
2. **性能影响**：Elicitation 是同步等待，用户体验上比直接开浏览器多一次点击，但更可控。
3. **message 设计**：自动生成的 message 要清晰简洁，让用户理解需要做什么。

## 后续可扩展

- 在检测到 CAPTCHA/登录墙时自动触发 Elicitation（不需要用户显式指定 `request_human_action`）
- URL mode Elicitation：让用户通过外部浏览器完成 OAuth 等操作
