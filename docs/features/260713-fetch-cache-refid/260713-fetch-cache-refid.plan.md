# Fetch 缓存显式引用 (refid)

## 背景

当前缓存机制存在两个问题：

1. **缓存是隐式的**：`find`、`links` 操作和 `cursor` 续读会自动使用缓存（通过 `can_use_cache` 属性），用户无法控制是否使用缓存。
2. **没有可复用的缓存标识**：用户无法在两次调用之间引用同一个缓存结果。

## 目标

1. 每次请求返回一个 `refid`（缓存引用 ID）。
2. 后续请求的 `url` 参数可以填写 `refid`，代表复用缓存结果。
3. 去除所有隐式缓存复用逻辑：除非显式传入 `refid`，否则每次都会发起真实请求。

## 方案

### 缓存存储

在 `fetch.py` 中新增 `_REFID_CACHE`，与已有的 `_FETCH_CACHE` 并存：

```
_REFID_CACHE: dict[str, Tuple[float, str, str]]  # refid -> (timestamp, final_url, html)
```

- refid 格式：`ref_` + `sha256("{mode}:{url}")` 取前 12 位 hex。
- 确定性 hash：同一 url+mode 总是生成相同 refid，覆盖旧缓存。
- 共享 `_FETCH_CACHE_TTL_SECONDS`（300s）和 `_FETCH_CACHE_MAX_SIZE`（100）限制。

### 函数变更

| 函数 | 变更 |
|------|------|
| `store_cached_fetch()` | 同时写入 `_REFID_CACHE`，**返回 refid** |
| `get_cached_by_refid(refid)` | 新增，按 refid 查询缓存 |
| `is_refid(value)` | 新增，检测字符串是否以 `ref_` 开头 |
| `get_cached_fetch()` | 保留但不再被 workflow.py 隐式调用 |

### 响应变更

所有响应中增加 `refid` 字段：

```json
{
  "success": true,
  "refid": "ref_a1b2c3d4e5f6",
  "final_url": "https://...",
  "result": "...",
  ...
}
```

### 流程变更 (`workflow.py`)

**请求处理逻辑改为：**

```
if url 以 "ref_" 开头:
    cache_entry = get_cached_by_refid(url)
    if not found:
        return error "refid 不存在或已过期"
    构造 FetchResult 从缓存
else:
    fetch_url() 真实请求
    store_cached_fetch() → 得到 refid
    # 不再有隐式 can_use_cache 判断
```

后续的 `render.cursor`、`operation=find`、`operation=links` 等操作如果需要基于已有页面内容执行，必须先传入 `refid`。

### 删除内容

- `AdvancedFetchParams.can_use_cache` 属性 → 删除
- `workflow.py` 中 `cache_hit` 相关逻辑 → 删除（不再有隐式缓存命中）
- `CACHE_HIT_WARNING` 常量 → 删除
- `get_cached_fetch()` 调用 → 删除

### 涉及文件

| 文件 | 变更 |
|------|------|
| `fetch.py` | 新增 `_REFID_CACHE`、`_generate_refid()`、`get_cached_by_refid()`、`is_refid()`；修改 `store_cached_fetch()` 返回 refid |
| `workflow.py` | 移除隐式缓存逻辑；新增 refid 输入判断；所有响应增加 refid 输出 |
| `params.py` | 删除 `can_use_cache` 属性 |

### 测试策略

- `test_workflow.py`：验证 refid 输入能命中缓存；验证普通 URL 不会隐式使用缓存；验证过期 refid 报错；验证 find/links/cursor 需要显式 refid。
- `test_fetch_and_browser.py`：验证 `store_cached_fetch` 返回 refid。

## 不涉及

- 不修改现有的 DSL/参数校验逻辑。
- 不修改 `docs_sync.py`、`config_meta.py`、`.env.example`。
- 不引入外部依赖（使用标准库 `hashlib`，本身已导入）。
- 不改变缓存 TTL 和最大容量。
