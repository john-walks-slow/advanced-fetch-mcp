# Extract Links 附件提取能力

## 背景

在查看页面内容时，用户经常需要同时获取页面中的外链列表用于导航或爬取入口发现。此前只有 `find` / `sampling` / `eval` 等操作，缺少快速获取全部链接的能力。

## 实现要点

### 非独立操作，附着在 View 上

与最初误解的方案不同——链接提取不是独立 `operation`，而是加到 `view` 对象下的一个可选配置 `view.links: { limit: 30 }`。当设置了 `view.links`，任何经过渲染的操作（view/find/sampling/cursor）的响应中都会额外包含链接列表。

### extract_links() 核心逻辑

1. lxml 解析 HTML → 收集所有 `<a href>`
2. 过滤非 HTTP 协议（javascript:/mailto:/tel:/data:/sms:/fax:/file: 及 #fragment-only）
3. 相对 URL → 用 `urljoin(base_url, href)` 解析为绝对 URL
4. 以 `abs_url` 去重（保留首次出现顺序）
5. 排除：若 `abs_url` 出现在渲染后的正文文本中，视为"已在正文中显示"跳过
6. 同源链接 → 相对路径；跨域 → 保留绝对路径
7. 按 `limit` 截断

### 响应格式

```json
{
  "links": [
    {"href": "/relative/path", "text": "链接文本", "abs_url": "https://example.com/relative/path"},
    {"href": "https://external.com", "text": "外部链接", "abs_url": "https://external.com"}
  ],
  "links_total": 50,
  "links_truncated": true
}
```

### 涉及文件

| 文件 | 变更 |
|------|------|
| config_meta.py | 新增 `MAX_LINKS_COUNT` env var spec |
| settings.py | 读取 `MAX_LINKS_COUNT` |
| params.py | 新增 `LinksLimitParam` / `LinksParams`；`ViewParams` 新增 `links` 字段 |
| extract.py | 新增 `extract_links()` 含 5 个辅助函数 |
| workflow.py | 渲染后条件性调用 `extract_links()`；`_build_public_result` 新增 `links_result` 参数 |
| docs_sync.py | 新增 `view_links` 文档段落 |
| test_extract.py | 新增 15 个单元测试 |
| test_workflow.py | 新增 2 个集成测试 |

### 值得后续注意的点

- 渲染正文去重使用 Python 的 `in` 子串匹配，极低概率下可能误过滤 URL 前缀匹配的情况
- 暂无针对超多链接（>1000）的性能防护，后续如有需求可加 `max_links_scan` 上限
- `view.links` 对所有经过 render 的操作都生效（view/find/sampling/cursor），设计上是一致的
