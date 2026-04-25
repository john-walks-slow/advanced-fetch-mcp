from __future__ import annotations

import importlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from .config_meta import ENV_VAR_NAMES, ENV_VAR_SPECS, SECTION_TITLES


ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_EXAMPLE_PATH = ROOT_DIR / ".env.example"
README_ZH_PATH = ROOT_DIR / "README.md"
README_EN_PATH = ROOT_DIR / "README.en.md"

README_BOUNDARIES = {
    "zh": {
        "schema_start": "## Schema",
        "schema_end": "## 返回值格式",
        "env_start": "## 环境变量",
        "env_end": "## 本地安装",
    },
    "en": {
        "schema_start": "## Schema",
        "schema_end": "## Response format",
        "env_start": "## Environment Variables",
        "env_end": "## Local Installation",
    },
}

SECTION_LABELS = {
    "zh": {
        "core": "通用",
        "auto_wait": "自动等待",
        "extraction": "提取 / LLM",
        "browser": "浏览器 / 会话",
        "proxy": "代理",
        "env_loading": "Env 加载",
        "misc": "其它",
        "name": "参数名",
        "type": "类型",
        "default": "默认值",
        "description": "描述",
        "path": "路径",
        "required": "必填",
        "see_below": "见下表",
        "top": "### 一、顶层参数",
        "fetch": "### 二、`fetch` 对象",
        "render": "### 三、`render` 对象",
        "find": "### 四、`find` 对象",
        "sampling": "### 五、`sampling` 对象",
        "eval": "### 六、`eval` 对象",
        "constraints": "### 七、使用约束",
        "rule": "规则",
        "rule_desc": "说明",
        "operation_specific": "操作专属配置",
        "operation_specific_desc": "仅当 `operation` 为对应值时，才可提供 `find`、`sampling` 或 `eval` 对象，且三者互斥。",
        "eval_mode": "`eval` 模式限制",
        "eval_mode_desc": "`operation=\"eval\"` 时，`fetch.mode` 必须为 `\"dynamic\"`。",
        "max_length_scope": "`max_length` 作用域",
        "max_length_scope_desc": "对 `view`、`find`、`sampling`、`eval` 均生效，限制最终返回结果。",
        "cursor_scope": "`render.cursor` 作用域",
        "cursor_scope_desc": "仅对 `view` 有效。用于从上次返回的 `next_cursor` 位置继续读取。",
        "cursor_consistency": "续读一致性",
        "cursor_consistency_desc": "使用 `cursor` 续读时，应保持 `output_format` 与 `strategy` 不变，否则偏移位置可能失效。",
    },
    "en": {
        "core": "General",
        "auto_wait": "Auto-wait",
        "extraction": "Extraction / LLM",
        "browser": "Browser / Session",
        "proxy": "Proxy",
        "env_loading": "Env loading",
        "misc": "Misc",
        "name": "Parameter",
        "type": "Type",
        "default": "Default",
        "description": "Description",
        "path": "Path",
        "required": "Required",
        "see_below": "See below",
        "top": "### 1. Top-level parameters",
        "fetch": "### 2. `fetch` object",
        "render": "### 3. `render` object",
        "find": "### 4. `find` object",
        "sampling": "### 5. `sampling` object",
        "eval": "### 6. `eval` object",
        "constraints": "### 7. Constraints",
        "rule": "Rule",
        "rule_desc": "Description",
        "operation_specific": "Operation-specific config",
        "operation_specific_desc": "The `find`, `sampling`, or `eval` object may only be provided when `operation` matches, and they are mutually exclusive.",
        "eval_mode": "`eval` mode restriction",
        "eval_mode_desc": "When `operation=\"eval\"`, `fetch.mode` must be `\"dynamic\"`.",
        "max_length_scope": "`max_length` scope",
        "max_length_scope_desc": "Applies to `view`, `find`, `sampling`, and `eval`, limiting the final returned result.",
        "cursor_scope": "`render.cursor` scope",
        "cursor_scope_desc": "Only valid for `view`. Used to continue reading from a previous `next_cursor` position.",
        "cursor_consistency": "Continue-read consistency",
        "cursor_consistency_desc": "When continuing with `cursor`, keep `output_format` and `strategy` unchanged, otherwise the offset may become invalid.",
    },
}


def render_env_example() -> str:
    lines: list[str] = []
    current_section = None
    for spec in ENV_VAR_SPECS:
        if spec.section != current_section:
            if lines:
                lines.append("")
            lines.extend(["# =========================", f"# {SECTION_TITLES[spec.section]}", "# =========================", ""])
            current_section = spec.section
        if spec.example_comment:
            lines.append(f"# {spec.example_comment}")
        lines.append(f"{spec.name}={spec.default}")
    return "\n".join(lines)


def _format_env_default(value: str) -> str:
    if value == "":
        return "空字符串"
    return f"`{value}`"


def render_readme_env_section(lang: str) -> str:
    labels = SECTION_LABELS[lang]
    title = "## 环境变量" if lang == "zh" else "## Environment Variables"
    lines = [title, ""]
    current_section = None
    for spec in ENV_VAR_SPECS:
        if spec.section != current_section:
            if current_section is not None:
                lines.append("")
            lines.append(f"### {labels[spec.section]}")
            lines.append("")
            current_section = spec.section
        description = spec.description_zh if lang == "zh" else spec.description_en
        note = spec.note_zh if lang == "zh" else spec.note_en
        if lang == "zh":
            line = f"- `{spec.name}`：{description}默认 {_format_env_default(spec.default)}。"
        else:
            default_text = "empty string" if spec.default == "" else f"`{spec.default}`"
            line = f"- `{spec.name}`: {description} Default: {default_text}."
        if note:
            line = f"{line} {note}"
        lines.append(line)
    return "\n".join(lines)


def _load_schema(lang: str) -> dict[str, Any]:
    saved = {name: os.environ.get(name) for name in ENV_VAR_NAMES}
    saved_params_module = sys.modules.get("advanced_fetch_mcp.params")
    saved_settings_module = sys.modules.get("advanced_fetch_mcp.settings")
    try:
        for name in ENV_VAR_NAMES:
            os.environ.pop(name, None)
        os.environ["SCHEMA_LANGUAGE"] = lang
        sys.modules.pop("advanced_fetch_mcp.params", None)
        sys.modules.pop("advanced_fetch_mcp.settings", None)
        module = importlib.import_module("advanced_fetch_mcp.params")
        return module.AdvancedFetchParams.model_json_schema()
    finally:
        if saved_params_module is None:
            sys.modules.pop("advanced_fetch_mcp.params", None)
        else:
            sys.modules["advanced_fetch_mcp.params"] = saved_params_module
        if saved_settings_module is None:
            sys.modules.pop("advanced_fetch_mcp.settings", None)
        else:
            sys.modules["advanced_fetch_mcp.settings"] = saved_settings_module
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _format_type(schema: dict[str, Any]) -> str:
    if "enum" in schema:
        return " | ".join(json.dumps(item, ensure_ascii=False) for item in schema["enum"])
    if "$ref" in schema:
        return "object"
    if "anyOf" in schema:
        return " | ".join(_format_type(item) for item in schema["anyOf"])
    if schema.get("type") == "array":
        return f"Array<{_format_type(schema.get('items', {}))}>"
    return schema.get("type", "object")


def _format_default(schema: dict[str, Any], *, required: bool, lang: str, see_below: bool = False) -> str:
    labels = SECTION_LABELS[lang]
    if see_below:
        return labels["see_below"]
    if "default" not in schema:
        return labels["required"] if required else "`null`"
    value = schema["default"]
    return f"`{json.dumps(value, ensure_ascii=False)}`"


def _escape_table_cell(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def _render_table(lines: list[str], header_name: str, properties: dict[str, Any], required: set[str], lang: str, prefix: str = "") -> None:
    labels = SECTION_LABELS[lang]
    lines.extend(
        [
            f"| {header_name} | {labels['type']} | {labels['default']} | {labels['description']} |",
            "| :--- | :--- | :--- | :--- |",
        ]
    )
    for name, schema in properties.items():
        path = f"{prefix}{name}"
        lines.append(
            "| `{path}` | `{type_}` | {default} | {description} |".format(
                path=path,
                type_=_escape_table_cell(_format_type(schema)),
                default=_escape_table_cell(
                    _format_default(schema, required=name in required, lang=lang, see_below=prefix == "" and name in {"fetch", "render"})
                ),
                description=_escape_table_cell(schema["description"]),
            )
        )


def render_readme_schema_section(lang: str) -> str:
    schema = _load_schema(lang)
    defs = schema["$defs"]
    labels = SECTION_LABELS[lang]
    lines = ["## Schema", "", labels["top"], ""]
    _render_table(lines, labels["name"], schema["properties"], set(schema.get("required", [])), lang)
    lines.extend(["", labels["fetch"], ""])
    _render_table(lines, labels["path"], defs["FetchParams"]["properties"], set(defs["FetchParams"].get("required", [])), lang, prefix="fetch.")
    lines.extend(["", labels["render"], ""])
    _render_table(lines, labels["path"], defs["RenderParams"]["properties"], set(defs["RenderParams"].get("required", [])), lang, prefix="render.")
    lines.extend(["", labels["find"], ""])
    _render_table(lines, labels["path"], defs["FindParams"]["properties"], set(defs["FindParams"].get("required", [])), lang, prefix="find.")
    lines.extend(["", labels["sampling"], ""])
    _render_table(lines, labels["path"], defs["SamplingParams"]["properties"], set(defs["SamplingParams"].get("required", [])), lang, prefix="sampling.")
    lines.extend(["", labels["eval"], ""])
    _render_table(lines, labels["path"], defs["EvalParams"]["properties"], set(defs["EvalParams"].get("required", [])), lang, prefix="eval.")
    lines.extend(
        [
            "",
            labels["constraints"],
            "",
            f"| {labels['rule']} | {labels['rule_desc']} |",
            "| :--- | :--- |",
            f"| {labels['operation_specific']} | {labels['operation_specific_desc']} |",
            f"| {labels['eval_mode']} | {labels['eval_mode_desc']} |",
            f"| {labels['max_length_scope']} | {labels['max_length_scope_desc']} |",
            f"| {labels['cursor_scope']} | {labels['cursor_scope_desc']} |",
            f"| {labels['cursor_consistency']} | {labels['cursor_consistency_desc']} |",
        ]
    )
    return "\n".join(lines) + "\n"


def _replace_between(text: str, start_heading: str, end_heading: str, replacement: str) -> str:
    pattern = rf"{re.escape(start_heading)}\n.*?\n+(?={re.escape(end_heading)}\n)"
    updated, count = re.subn(pattern, replacement + "\n\n", text, flags=re.DOTALL)
    if count != 1:
        raise ValueError(f"Could not replace section between {start_heading!r} and {end_heading!r}")
    return updated


def render_synced_readme_text(text: str, lang: str) -> str:
    boundaries = README_BOUNDARIES[lang]
    text = _replace_between(text, boundaries["schema_start"], boundaries["schema_end"], render_readme_schema_section(lang))
    return _replace_between(text, boundaries["env_start"], boundaries["env_end"], render_readme_env_section(lang))


def sync_docs() -> None:
    ENV_EXAMPLE_PATH.write_text(render_env_example(), encoding="utf-8")
    README_ZH_PATH.write_text(render_synced_readme_text(README_ZH_PATH.read_text(encoding="utf-8"), "zh"), encoding="utf-8")
    README_EN_PATH.write_text(render_synced_readme_text(README_EN_PATH.read_text(encoding="utf-8"), "en"), encoding="utf-8")
