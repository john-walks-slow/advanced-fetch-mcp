# 检视报告

## 概要

检视范围：`advanced_fetch_mcp/browser.py`（BrowserManager 重写）和 `advanced_fetch_mcp/fetch.py`（适配新 API）。
总体评价：设计方向正确（浏览器实例复用、独立 Context、原子写 storage_state、并发安全），但**存在一个阻塞级别的死锁问题**：`_ensure_browser_headless` 和 `_ensure_playwright` 共享同一个 `asyncio.Lock`，被嵌套调用时造成非可重入锁死锁。另外，Elicit 测试的 mock 未跟上新的 `open_elicit_session` API。

## 需求对齐

- ✅ 浏览器实例复用（`_ensure_browser_headless` lazy init + 保持存活）
- ✅ 每请求独立 BrowserContext（`open_session` / `open_elicit_session` 每次 `new_context()`）
- ✅ 请求结束自动保存 storage_state（`finally` 块中调用 `_save_storage_state_atomic`）
- ✅ Elicit 保持 headful + 无 stealth（`open_elicit_session` 使用 `headless=False`，不调用 `apply_auth_stealth`）
- ✅ 并发安全（`asyncio.Lock` 保护初始化与原子写，`os.replace` 原子重命名）
- ✅ 崩溃恢复（`_ensure_browser_headless` 检查 `browser.is_connected()`，断开时自动重建）

## 阻塞问题

| ID | 位置 | 问题 | 建议 |
|----|------|------|------|
| B1 | `browser.py:223-226` `_ensure_playwright` + `browser.py:241-244` `_ensure_browser_headless` | **`asyncio.Lock` 非可重入导致的死锁**。`_ensure_browser_headless()` 在持有 `_init_lock` 的临界区内调用 `_ensure_playwright()`，而 `_ensure_playwright()` 也试图获取同一个 `_init_lock`。由于 `asyncio.Lock` 不可重入，首次调用（`_pw` 和 `_browser` 均为 None）时必然死锁。<br><br>调用链：`open_session()` → `_ensure_browser_headless()` → `async with self._init_lock:` → `self._ensure_playwright()` → `async with self._init_lock:` **⛔ DEADLOCK** | **方案（推荐）**：将两个锁分离。新增 `_pw_lock: asyncio.Lock`，让 `_ensure_playwright` 使用 `_pw_lock` 而非 `_init_lock`。这样 `_ensure_browser_headless` 持有 `_init_lock` 调用 `_ensure_playwright` 时不会产生锁竞争。<br><br>```python
# 在 __init__ 或 field 中增加：
_pw_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

# _ensure_playwright 使用 _pw_lock：
async with self._pw_lock:
    if self._pw is not None:
        return self._pw
    self._pw = await async_playwright().start()
``` |

## 建议修改

| ID | 位置 | 问题 | 建议 |
|----|------|------|------|
| S1 | `tests/test_fetch_and_browser.py:483-519` `test_eval_elicit_page_closed_raises_clear_error` | **Elicit 测试的 mock 未适配新 API**。测试中设置了 `mock_manager.open_session = MagicMock(return_value=mock_session_cm)`，但代码现调用 `browser_manager.open_elicit_session()`。由于 `mock_manager` 是 `MagicMock`，`open_elicit_session()` 会自动创建新 MagicMock（而非使用配置的 `mock_session_cm`）。该测试靠外部的 `wait_for_elicit_end` patch 侥幸通过，**并未实际验证 `open_elicit_session` 集成路径**。 | 增加 `mock_manager.open_elicit_session = MagicMock(return_value=mock_session_cm)` 配置，确保 elicit 场景的测试经过正确的 mock 上下文。 |
| S2 | `tests/test_fetch_and_browser.py` (同文件其他测试) | **建议补充 `open_elicit_session` 的单元测试**。当前 `BrowserManager` 新增方法 `_ensure_playwright`、`_ensure_browser_headless`、`_save_storage_state_atomic`、`open_elicit_session`、`close` 均无单元测试覆盖（仅依赖集成 mock）。虽然部分逻辑依赖 Playwright 难以纯单元测试，但 `_save_storage_state_atomic` 的原子写入逻辑可以在 mock `context.storage_state` 下测试。 | 为 `_save_storage_state_atomic` 添加单元测试：mock `context.storage_state`，验证写入临时文件 + `os.replace` 被调用、并发下锁保护正确。 |
| S3 | `fetch.py:44` `FetchResult.screenshot: Optional[str]` | **类型标注与运行时值不一致**（pre-existing）。`page.screenshot(type="png")` 返回 `bytes`，但 `FetchResult.screenshot` 标注为 `Optional[str]`。运行时虽无报错（Python 不做运行时类型检查），但类型检查工具会报错。 | 将 `screenshot: Optional[str] = None` 改为 `screenshot: Optional[bytes] = None`。 |
| S4 | `browser.py:267` `_save_storage_state_atomic` | **`context.storage_state()` 失败时残留 `.tmp` 文件**。若写入过程中异常退出，`*.tmp` 文件不会被清理。长期运行可能积累临时文件。 | 在 `finally` 或 `except` 分支中尝试 `os.remove(str(tmp))` 清理临时文件（`FileNotFoundError` 可静默忽略）。 |

## 非阻塞问题

| ID | 位置 | 问题 | 建议 |
|----|------|------|------|
| N1 | `browser.py:230-247` `_ensure_browser_headless` | **两个并发检测到浏览器断开时，均在锁外设置 `self._browser = None`**。虽不会导致重复创建（DCL 在锁内保护），但逻辑上不够精确。 | 可将 `self._browser = None` 移到锁内，但需要重排逻辑（先确认 Playwright 可用再做标记）。当前行为无害，低优先级。 |
| N2 | `browser.py:275-293` vs `browser.py:295-321` | **`open_session` 和 `open_elicit_session` 的 finally 块有重复代码**（保存 storage_state + 关闭 context）。当前重复可接受（逻辑不同：一个不关 browser，一个关 browser），但若后续增加第三种 session 类型，需考虑抽取共用模式。 | 暂无行动。 |
| N3 | `browser.py:296` `open_elicit_session` 文档字符串 | 文档提到"用户完成人机验证或登录后自动保存 storage_state"，但实际的保存操作在 `finally` 块中，无论用户是否完成验证都会保存。如果不成功，保存的 state 可能不含有效 auth。 | 建议更新 docstring 澄清：storage_state 始终在会话结束时保存，无论 elicit 是否成功。 |

## 准入结论

**结论**：`不准入`

**说明**：B1 是运行时死锁，只要首次 `open_session()` 调用就会触发，阻断核心功能。修复 B1 后建议处理 S1、S3（测试适配 + 类型修复），可改为条件准入。
