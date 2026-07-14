# view 新增 screenshot 支持

## 背景

用户在 `view` 操作中能获取页面首屏截图。

## 方案

### 1. 默认 Viewport → 典型笔记本大小

当前默认是 1366×768，改为 **1440×900**（MacBook Air / 主流 13-14" 笔记本典型分辨率，截图大小适中）。

| 变量 | 旧值 | 新值 |
|---|---|---|
| `BROWSER_VIEWPORT_WIDTH` | 1366 | 1440 |
| `BROWSER_VIEWPORT_HEIGHT` | 768 | 900 |

### 2. ViewParams 新增 `with_screenshot` 参数

```python
class ViewParams(BaseModel):
    ...
    with_screenshot: bool = Field(
        default=False,
        description="是否截图。自动使用 dynamic 模式获取页面并截取首屏，返回 base64 编码的 PNG。",
    )
```

### 3. 行为规则

- `with_screenshot=True` → 自动将 `fetch.mode` 设为 `"dynamic"`（用户无需手动指定）
- `with_screenshot=True` + `operation != "view"` → 抛错（截图仅对 view 有意义）
- 每次都重新打开浏览器截图，**不缓存截图**（也不走 refid 缓存路径）

### 4. 截图实现

在 `dynamic_fetch` 中嵌入截图流程：

```
页面稳定后 → page.screenshot(type="png", full_page=False) → base64 编码
```

- 截取视口（viewport），不截 full page
- 编码为 `data:image/png;base64,<base64_data>`
- **不滚动** — 只截首屏

### 5. 响应格式

新增字段 `screenshot`（仅当 `with_screenshot=True` 时出现）：

```json
{
  "screenshot": "data:image/png;base64,iVBORw0KGgo..."
}
```

### 6. 传递链路

```
workflow.execute_advanced_fetch()
  request.with_screenshot=True → 强制 fetch.mode="dynamic"
  → fetch_url(url, mode="dynamic", with_screenshot=True)
    → dynamic_fetch(url, with_screenshot=True)
      → 页面稳定后 → page.screenshot() → 编码 base64
      → FetchResult(html=..., screenshot="data:image/...")
  → _build_public_result(..., screenshot=...)
```

### 7. 变更清单

#### `advanced_fetch_mcp/config_meta.py`
- `BROWSER_VIEWPORT_WIDTH` 默认 `"1366"` → `"1440"`
- `BROWSER_VIEWPORT_HEIGHT` 默认 `"768"` → `"900"`

#### `advanced_fetch_mcp/params.py`
- `ViewParams` 新增 `with_screenshot: bool` 字段
- `AdvancedFetchParams._validate_semantics()` 新增：
  - `with_screenshot=True` + `operation != "view"` → 抛错
  - `with_screenshot=True` 自动 `fetch.mode="dynamic"`

#### `advanced_fetch_mcp/fetch.py`
- `FetchResult` 新增 `screenshot: Optional[str] = None`
- `dynamic_fetch()` 新增参数 `with_screenshot: bool`
- 页面稳定后：若 `with_screenshot=True`，执行 `page.screenshot()` 并 base64 编码
- `fetch_url()` 新增透传参数 `with_screenshot`

#### `advanced_fetch_mcp/workflow.py`
- `execute_advanced_fetch()`：若 `request.view.with_screenshot=True`，强制 `fetch.mode="dynamic"`
- 传递 `with_screenshot` 到 `fetch_url()`
- 从 `fetch_result.screenshot` 提取并加入响应
- `_build_public_result()` 新增 `screenshot` 参数

### 8. 不做的事情

- ❌ 不滚动到 cursor 位置
- ❌ 不做 full-page 截图
- ❌ 不缓存截图
- ❌ 不修改 server.py 签名

## 工作量估计

- 代码行数变化：~120-150 LOC
- 涉及 4 个核心文件 + docs sync + 测试
