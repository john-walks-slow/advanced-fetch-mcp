# Refid 缓存机制

## 背景

原有 fetch 缓存机制是隐式的：`find`、`links` 操作和 `render.cursor` 续读会自动使用内存缓存。用户无法控制缓存行为，且缓存不对外暴露，导致跨请求间无法复用。

## 方案

引入显式 `refid`（Reference ID）机制：

- **每次请求返回 `refid`**：响应中新增 `refid` 字段，标识该次 fetch 的缓存条目
- **`refid` 作为 URL 复用缓存**：后续请求将 `refid` 填入 `url` 字段，跳过实际抓取直接返回缓存内容
- **移除隐式缓存**：去掉 `AdvancedFetchParams.can_use_cache` 属性，普通 URL 请求始终抓取最新内容

## 变更文件

### fetch.py
- 删除 `_FETCH_CACHE`、`_cache_key()`、`get_cached_fetch()` 及相关常量
- 新增 `_REFID_CACHE`、`_REFID_PATTERN`、`generate_refid()`、`_is_refid()`、`get_cached_fetch_by_refid()`
- `store_cached_fetch()` 改为写入 `_REFID_CACHE`，返回 `refid`（str）
- `refid` 格式：uuid4 前 12 位 hex 字符，TTL 300s，最大 100 条

### params.py
- 删除 `can_use_cache` 属性

### workflow.py
- 删除 `CACHE_HIT_WARNING`
- `_build_public_result()`：删除 `cache_hit` 参数，新增 `refid` 参数
- `execute_advanced_fetch()`：新增 `_is_refid()` 检测 → 命中则使用缓存，否则正常抓取并存入缓存
- refid 过期返回明确错误信息

### 测试
- `test_dsl.py`：删除 4 个 `can_use_cache` 测试
- `test_workflow.py`：将所有 `get_cached_fetch` mock 替换为 `get_cached_fetch_by_refid` mock，新增 `refid` 断言；新增 3 个 refid 测试（命中、过期、view 不隐式缓存）
- `test_fetch_and_browser.py`：将 `_FETCH_CACHE` 引用替换为 `_REFID_CACHE`；`test_cache_is_partitioned_by_url_and_mode` 改为 `test_cache_stores_and_retrieves_by_refid`

### 文档
- README.md / README.en.md：响应格式中 `cache_hit` → `refid`；缓存章节重写为 refid 缓存说明
