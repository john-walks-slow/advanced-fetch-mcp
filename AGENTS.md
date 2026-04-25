# Project Agents

## Docs Sync

- 本项目的下列文档段落是由 `advanced_fetch_mcp/docs_sync.py` 从数据源自动生成的。
  - `.env.example` 
  - `README.md`、`README.en.md` 中 `## Schema` 表格和 `## 环境变量` / `## Environment Variables` 整段
- 环境变量选项定义以 `advanced_fetch_mcp/config_meta.py` 为单一来源。
- 请求参数定义以 `advanced_fetch_mcp/params.py` 为单一来源。
- 写 schema 描述时不要重复类型、默认值、可空性等表格已包含的信息，只说明用途、行为和选择建议。
- 提取引擎属于 `render.engine`，不要放到 `fetch` 配置下；`fetch` 只描述页面获取方式与等待策略。
- 修改参数定义后，注意不要手动修改上述文档，而是执行 `python scripts/sync_docs.py` 并检查文档更新成功。

## Extraction Libraries

- 使用 `markdownify` 选项时，先用当前安装版本做一次最小运行验证，再写入实现；文档里的符号名不一定能直接当字符串传入，否则可能触发静默回退并掩盖真实输出差异。
