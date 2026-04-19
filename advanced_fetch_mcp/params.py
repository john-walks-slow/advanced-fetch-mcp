from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .settings import DEFAULT_MAX_LENGTH, ENABLE_PROMPT_EXTRACTION, MEDIA_REMOVE_TAGS

FetchMode = Literal["dynamic", "static"]
ExtractStrategy = Literal["strict", "loose", "none"]
OutputFormat = Literal["markdown", "html"]
Operation = Literal["read", "find", "extract", "eval"]

UrlParam = Annotated[str, Field(description="目标网址。")]
ModeParam = Annotated[
    FetchMode,
    Field(
        default="dynamic",
        description="页面抓取方式。dynamic 使用 Playwright；static 直接获取页面响应。",
    ),
]
WaitForParam = Annotated[
    float,
    Field(
        default=0.0,
        ge=0,
        description="dynamic 模式下，networkidle 后额外等待秒数（适合有懒加载内容的页面）。",
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
        description="输出格式。markdown 返回 Markdown；html 返回原始 HTML。",
    ),
]
StrategyParam = Annotated[
    ExtractStrategy,
    Field(
        default="strict",
        description="提取策略。strict 优先提取最小正文；loose 优先避免误删；none 返回完整 body。",
    ),
]
StripSelectorsParam = Annotated[
    list[str],
    Field(
        default=list(MEDIA_REMOVE_TAGS),
        description="按这些 CSS selector 剔除节点。默认剔除媒体标签（video/audio/img 等）。传空列表保留全部。",
    ),
]
CursorParam = Annotated[
    Optional[int],
    Field(
        default=None,
        ge=0,
        description="文本位置偏移。从该位置续读或继续搜索。（受输出格式和提取策略影响）",
    ),
]
MaxLengthParam = Annotated[
    int, Field(default=DEFAULT_MAX_LENGTH, ge=1, description="结果长度上限。")
]
FindInPageParam = Annotated[
    Optional[str],
    Field(
        default=None,
        description="页面内搜索，返回 matches 列表，适合在长页面中定位关键部分。",
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
        description="在页面上下文中执行 JavaScript，返回脚本结果。（不使用缓存）",
    ),
]
RequireInterventionParam = Annotated[
    bool,
    Field(
        default=False,
        description="需要登录/过验证码时设为 true，打开可见浏览器让用户手动操作，用户操作完成后自动继续。",
    ),
]
RefreshCacheParam = Annotated[
    bool,
    Field(default=False, description="是否忽略已有缓存重新抓取。")
]


class AdvancedFetchParams(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), extra="forbid")

    url: UrlParam
    mode: ModeParam
    wait_for: WaitForParam
    timeout: TimeoutParam
    output_format: OutputFormatParam
    strategy: StrategyParam
    strip_selectors: StripSelectorsParam
    cursor: CursorParam
    max_length: MaxLengthParam
    find_in_page: FindInPageParam
    find_with_regex: FindWithRegexParam
    extract_prompt: ExtractPromptParam
    evaluate_js: EvaluateJsParam
    require_user_intervention: RequireInterventionParam
    refresh_cache: RefreshCacheParam

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
        return (
            self.require_user_intervention
            or self.evaluate_js is not None
            or self.refresh_cache
        )

    def to_render_config(self) -> "RenderConfig":
        return RenderConfig(
            output_format=self.output_format,
            strategy=self.strategy,
            strip_selectors=self.strip_selectors,
        )

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
        return self


class RenderConfig(BaseModel):
    output_format: OutputFormatParam
    strategy: StrategyParam
    strip_selectors: StripSelectorsParam