# Refid 缓存机制

## 背景

当前 fetch 结果缓存是隐式的：`find`、`links` 操作和带有 `render.cursor` 的 `view` 操作会自动使用内存缓存（key 为 (url, mode)），而普通 `view` 操作不缓存。这种隐式缓存带来几个问题：

1. 用户无法控制是否使用缓存
2. 缓存命中是静默的，用户不知道结果来自缓存
3. 缓存 key 依赖 url+mode，不同操作的缓存策略不一致
4. 跨请求之间无法复用缓存（因为缓存不暴露给用户）

## 方案

引入显式 `refid`（Reference ID）机制：

- **每次请求返回 refid**：响应中新增 `refid` 字段，标识该次 fetch 的缓存条目
- **refid 作为 URL 复用缓存**：后续请求将 `refid` 填入 `url` 字段，跳过实际抓取直接返回缓存内容
- **不再隐式复用缓存**：去掉 `can_use_cache` 逻辑，普通 URL 请求始终抓取最新内容

### 1. refid 格式

使用 uuid4 的前 12 位 hex 字符作为 refid（如 `3a1f8c2e9b0d`），碰撞概率在 16^12 ≈ 2.8×10^14 中几乎为零。

### 2. 缓存存储

- 新增 `_REFID_CACHE: dict[str, Tuple[float, str, str, str]]`，key 为 refid，value 为 `(timestamp, url, final_url, html)`
- TTL 保持 300 秒，最大条目 100
- 每次 fetch 后生成新 refid 并存储
- 请求以 refid 作为 URL 时返回已有缓存，不生成新 refid（同一个 refid 始终指向同一份内容）

### 3. refid 检测

请求进入时先检查 `url` 是否符合 refid 格式（12 位 hex）。若匹配，从 `_REFID_CACHE` 查找；若存在则命中缓存；若不存在则报错（refid 已过期）。若不匹配 refid 格式，作为普通 URL 处理。

### 4. 移除隐式缓存

- 删除 `AdvancedFetchParams.can_use_cache` 属性
- 删除 `_FETCH_CACHE`、`get_cached_fetch()`、`_cache_key()`
- 删除 `CACHE_HIT_WARNING`
- 普通 URL 请求不再检查缓存，始终 fetch

### 5. 响应格式

所有非 eval 操作的响应中新增 `refid` 字段。eval 操作仍返回 refid，但不缓存 HTML（eval 结果不适合按 HTML 缓存）。

## 变更清单

### fetch.py
- 导入 `uuid`
- 删除 `_FETCH_CACHE`、`_cache_key()`、`get_cached_fetch()`
- 删除 `_FETCH_CACHE_MAX_SIZE`、`_FETCH_CACHE_TTL_SECONDS`
- 新增 `_REFID_CACHE`、`_REFID_CACHE_MAX_SIZE`、`_REFID_CACHE_TTL_SECONDS`
- 新增 `_REFID_PATTERN` 正则
- 新增 `_is_refid(value: str) -> bool`
- 新增 `generate_refid() -> str`
- 新增 `get_cached_fetch_by_refid(refid: str) -> Optional[Tuple[str, str]]`
- `store_cached_fetch()`：改为写入 `_REFID_CACHE`，返回 `refid`

### params.py
- 删除 `can_use_cache` 属性

### workflow.py
- 删除 `CACHE_HIT_WARNING`
- `_build_public_result()`：删除 `cache_hit` 参数，新增 `refid` 参数
- `execute_advanced_fetch()`：移除 `can_use_cache` 逻辑，添加 refid 检测与生成

### tests
- `test_dsl.py`：删除 `can_use_cache` 相关测试
- `test_workflow.py`：更新 mock 模式（`get_cached_fetch` → `get_cached_fetch_by_refid`），删除 `cache_hit` 断言，添加 `refid` 断言
- `test_server_integration.py`：无需改动（不直接涉及缓存逻辑）

## 不做的事情

- 不引入新环境变量
- 不改动 fetch 参数结构
- 不改动 server.py 签名
- 不改动 extract/sampling 逻辑
