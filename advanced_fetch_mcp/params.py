from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .settings import DEFAULT_MAX_LENGTH, ENABLE_PROMPT_EXTRACTION

FetchMode = Literal["dynamic", "static"]
ExtractStrategy = Literal["strict", "loose", "none"]
OutputFormat = Literal["markdown", "html"]
Operation = Literal["read", "find", "extract", "eval"]
WaitForValue = float | Literal["auto"]
SemanticExtra = Literal["comments", "tables", "images", "links", "formatting"]

UrlParam = Annotated[str, Field(description="目标网址。")]
ModeParam = Annotated[
    FetchMode,
    Field(
        default="dynamic",
        description="页面抓取方式。dynamic（推荐）使用 Playwright；static 直接获取页面响应。",
    ),
]
WaitForParam = Annotated[
    WaitForValue,
    Field(
        default="auto",
        description=(
            "dynamic 模式下的额外等待策略。"
            "auto（默认）会在页面加载后自动等待正文变得更完整；"
            "也可传入秒数，表示在页面加载后额外等待指定秒数。"
        ),
    ),
]
TimeoutParam = Annotated[
    Optional[float],
    Field(default=None, ge=0.1, description="抓取超时秒数，超时后返回当前已加载内容。"),
]
OutputFormatParam = Annotated[
    OutputFormat,
    Field(
        default="markdown",
        description="输出格式。markdown 返回 Trafilatura 生成的 Markdown；html 返回 Trafilatura 抽取后的 HTML。",
    ),
]
StrategyParam = Annotated[
    ExtractStrategy,
    Field(
        default="strict",
        description="提取策略。strict 偏正文纯度；loose 偏召回；none 使用 Trafilatura 默认平衡策略。",
    ),
]
ExtraElementsParam = Annotated[
    list[SemanticExtra],
    Field(
        default=["tables"],
        description=(
            "基于 Trafilatura 语义提取时额外保留的元素。"
            "可选值：comments、tables、images、links、formatting。"
            "默认仅保留 tables。"
        ),
    ),
]
CursorParam = Annotated[
    Optional[int],
    Field(
        default=None,
        ge=0,
        description="文本位置偏移，从该位置续读或继续搜索。（受输出格式和提取策略影响；给定此参数则优先使用缓存)",
    ),
]
MaxLengthParam = Annotated[
    int, Field(default=DEFAULT_MAX_LENGTH, ge=1, description="结果长度上限。")
]
FindInPageParam = Annotated[
    Optional[str],
    Field(
        default=None,
        description="页面内搜索，返回 matches 列表，适合在长页面中定位关键部分。(给定此参数则优先使用缓存)",
    ),
]
FindWithRegexParam = Annotated[
    bool,
    Field(
        default=False,
        description="是否把 find_in_page 按正则表达式处理。",
    ),
]
ExtractPromptParam = Annotated[
    Optional[str],
    Field(
        default=None,
        description="提取提示词。提供后，调用 LLM 整理内容，返回提取后的结果。可以避免原始页面内容污染调用方的上下文。",
    ),
]
EvaluateJsParam = Annotated[
    Optional[str],
    Field(
        default=None,
        description="在页面上下文中执行 JavaScript，返回脚本结果。",
    ),
]
RequireInterventionParam = Annotated[
    bool,
    Field(
        default=False,
        description="需要登录/过验证码时设为 true，打开可见浏览器让用户手动操作，用户操作完成后自动继续。",
    ),
]


class AdvancedFetchParams(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), extra="forbid")

    url: UrlParam
    mode: ModeParam
    wait_for: WaitForParam
    timeout: TimeoutParam
    output_format: OutputFormatParam
    strategy: StrategyParam
    extra_elements: ExtraElementsParam
    cursor: CursorParam
    max_length: MaxLengthParam
    find_in_page: FindInPageParam
    find_with_regex: FindWithRegexParam
    extract_prompt: ExtractPromptParam
    evaluate_js: EvaluateJsParam
    require_user_intervention: RequireInterventionParam

    @property
    def operation(self) -> Operation:
        if self.evaluate_js is not None:
            return "eval"
        if self.find_in_page is not None:
            return "find"
        if self.extract_prompt is not None:
            return "extract"
        return "read"

    @property
    def should_skip_cache(self) -> bool:
        return not (self.find_in_page or self.cursor)

    def to_render_config(self) -> "RenderConfig":
        return RenderConfig(
            output_format=self.output_format,
            strategy=self.strategy,
            extra_elements=self.extra_elements,
        )

    @field_validator("wait_for", mode="before")
    @classmethod
    def _normalize_wait_for(cls, value):
        if value is None or value == "":
            return "auto"
        if isinstance(value, str):
            stripped = value.strip().lower()
            if stripped == "auto":
                return "auto"
            return float(stripped)
        return value

    @field_validator("extra_elements", mode="before")
    @classmethod
    def _normalize_extra_elements(cls, value):
        if value is None:
            return ["tables"]
        if isinstance(value, str):
            value = [value]
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            text = str(item).strip().lower()
            if not text or text in seen:
                continue
            seen.add(text)
            normalized.append(text)
        return normalized

    @model_validator(mode="after")
    def _validate_semantics(self) -> "AdvancedFetchParams":
        if self.extract_prompt is not None and not ENABLE_PROMPT_EXTRACTION:
            raise ValueError(
                "当前环境未启用 extract_prompt 功能（ENABLE_PROMPT_EXTRACTION=false）。"
            )
        if self.evaluate_js is not None and (
            self.extract_prompt is not None or self.find_in_page is not None
        ):
            raise ValueError(
                "提供 evaluate_js 时，不能再同时提供 extract_prompt 或 find_in_page。"
            )
        if self.evaluate_js is not None and self.mode == "static":
            raise ValueError("evaluate_js 只支持 dynamic 模式。")
        if self.extract_prompt is not None and self.find_in_page is not None:
            raise ValueError("提供 extract_prompt 时，不能再同时提供 find_in_page。")
        if self.find_in_page is None and self.find_with_regex:
            raise ValueError("find_with_regex 需要配合 find_in_page 使用。")
        if self.wait_for != "auto" and self.wait_for < 0:
            raise ValueError("wait_for 必须为非负数或 auto。")
        return self


class RenderConfig(BaseModel):
    output_format: OutputFormatParam
    strategy: StrategyParam
    extra_elements: ExtraElementsParam
