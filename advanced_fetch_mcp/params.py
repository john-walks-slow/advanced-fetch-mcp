from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .settings import (
    AUTO_WAIT_MIN_CONTENT_LENGTH,
    AUTO_WAIT_MIN_STABLE_SECONDS,
    DEFAULT_MAX_LENGTH,
    ENABLE_PROMPT_EXTRACTION,
    FETCH_TIMEOUT_SECONDS,
    FIND_SNIPPET_MAX_CHARS,
    MAX_FIND_MATCHES,
    SCHEMA_LANGUAGE,
)

FetchMode = Literal["dynamic", "static"]
FetchEngine = Literal["trafilatura", "markdownify"]
ExtractStrategy = Literal["default", "strict", "loose"]
OutputFormat = Literal["markdown", "html"]
Operation = Literal["view", "find", "sampling", "eval"]
SemanticExtra = Literal["comments", "tables", "images", "links", "formatting"]


def schema_text(zh: str, en: str) -> str:
    return zh if SCHEMA_LANGUAGE == "zh" else en


def schema_error(zh: str, en: str) -> str:
    return zh if SCHEMA_LANGUAGE == "zh" else en


UrlParam = Annotated[
    str,
    Field(
        description=schema_text(
            "目标网页的完整 URL。",
            "Full URL of the target webpage.",
        )
    ),
]
OperationParam = Annotated[
    Operation,
    Field(
        default="view",
        description=schema_text(
            "操作类型：查看、页面内搜索、LLM 提取或执行 JS。",
            "Operation: view, in-page search, LLM extraction, or JS execution.",
        ),
    ),
]
FetchModeParam = Annotated[
    FetchMode,
    Field(
        default="dynamic",
        description=schema_text(
            "抓取方式：dynamic 用浏览器，static 直接请求源码。",
            "Fetch mode: dynamic uses a browser; static requests source HTML directly.",
        ),
    ),
]
TimeoutParam = Annotated[
    float,
    Field(
        default=FETCH_TIMEOUT_SECONDS,
        ge=0.1,
        description=schema_text(
            "抓取超时秒数。超时后返回当前已获取内容。",
            "Fetch timeout in seconds. On timeout, return the content obtained so far.",
        ),
    ),
]
RequireInterventionParam = Annotated[
    bool,
    Field(
        default=False,
        description=schema_text(
            "用于登录、验证码或人工操作。",
            "Use for login, CAPTCHA, or manual page actions.",
        ),
    ),
]
MinStableSecondsParam = Annotated[
    float,
    Field(
        default=AUTO_WAIT_MIN_STABLE_SECONDS,
        ge=0.1,
        description=schema_text(
            "动态抓取等待内容稳定的最小时长（秒）。",
            "Minimum stable duration in seconds for dynamic fetch.",
        ),
    ),
]
MinContentLengthParam = Annotated[
    int,
    Field(
        default=AUTO_WAIT_MIN_CONTENT_LENGTH,
        ge=1,
        description=schema_text(
            "动态抓取时内容长度必须达到此值且稳定时间足够才视为成功。",
            "Dynamic fetch requires content length to reach this value and stable duration to succeed.",
        ),
    ),
]
OutputFormatParam = Annotated[
    OutputFormat,
    Field(
        default="markdown",
        description=schema_text(
            "正文输出格式。",
            "Main-content output format.",
        ),
    ),
]
StrategyParam = Annotated[
    ExtractStrategy,
    Field(
        default="default",
        description=schema_text(
            "trafilatura 专用策略：strict 更干净，loose 覆盖更多。",
            "trafilatura-only strategy: strict is cleaner; loose keeps more content.",
        ),
    ),
]
FetchEngineParam = Annotated[
    FetchEngine,
    Field(
        default="trafilatura",
        description=schema_text(
            "提取引擎。trafilatura 适合文章/正文类页面；复杂页面可用 markdownify 覆盖更多页面内容。",
            "Extraction engine. trafilatura works best for articles/main content; use markdownify for complex pages where broader page content is needed.",
        ),
    ),
]
IncludeElementsParam = Annotated[
    list[SemanticExtra],
    Field(
        default=["tables", "formatting"],
        description=schema_text(
            "额外保留的内容类型，如 tables、links、images。",
            "Extra content types to keep, such as tables, links, and images.",
        ),
    ),
]
MaxLengthParam = Annotated[
    int,
    Field(
        default=DEFAULT_MAX_LENGTH,
        ge=1,
        description=schema_text(
            "结果最大长度。",
            "Maximum result length.",
        ),
    ),
]
CursorParam = Annotated[
    Optional[int],
    Field(
        default=None,
        ge=0,
        description=schema_text(
            "文本起始偏移量。仅用于继续读取长页面。",
            "Text start offset used only to continue reading long pages.",
        ),
    ),
]
FindQueryParam = Annotated[
    str,
    Field(
        description=schema_text(
            "要查找的文本或正则表达式。",
            "Text or regular expression to search for.",
        )
    ),
]
FindRegexParam = Annotated[
    bool,
    Field(
        default=False,
        description=schema_text(
            "是否将 query 视为正则表达式处理。",
            "Whether to treat query as a regular expression.",
        ),
    ),
]
FindLimitParam = Annotated[
    int,
    Field(
        default=MAX_FIND_MATCHES,
        ge=1,
        description=schema_text(
            "本次最多返回多少个匹配项。",
            "Maximum number of matches to return for this request.",
        ),
    ),
]
FindSnippetMaxCharsParam = Annotated[
    int,
    Field(
        default=FIND_SNIPPET_MAX_CHARS,
        ge=1,
        description=schema_text(
            "每个匹配项 snippet 的最大长度。",
            "Maximum snippet length for each returned match.",
        ),
    ),
]
FindStartIndexParam = Annotated[
    int,
    Field(
        default=0,
        ge=0,
        description=schema_text(
            "从第几个匹配开始返回，0 表示第一个匹配。",
            "Zero-based match index to start returning from. 0 means the first match.",
        ),
    ),
]
SamplingPromptParam = Annotated[
    str,
    Field(
        description=schema_text(
            "指导 LLM 从页面正文中提取信息的提示词。",
            "Prompt that guides the LLM to extract information from the page main content.",
        )
    ),
]
SamplingModelParam = Annotated[
    Optional[str],
    Field(
        default=None,
        description=schema_text(
            "偏好的模型名。",
            "Preferred model name.",
        ),
    ),
]
EvalScriptParam = Annotated[
    str,
    Field(
        description=schema_text(
            "在页面上下文执行的 JavaScript 代码。仅 dynamic 模式支持。",
            "JavaScript code executed in the page context. Supported only in dynamic mode.",
        )
    ),
]


class FetchParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: FetchModeParam
    min_stable_seconds: MinStableSecondsParam
    min_content_length: MinContentLengthParam
    timeout: TimeoutParam
    require_user_intervention: RequireInterventionParam


class RenderParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engine: FetchEngineParam
    output_format: OutputFormatParam
    strategy: StrategyParam
    include_elements: IncludeElementsParam
    cursor: CursorParam

    @field_validator("include_elements", mode="before")
    @classmethod
    def _normalize_include_elements(cls, value):
        if value is None:
            return ["tables", "formatting"]
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


class FindParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: FindQueryParam
    regex: FindRegexParam
    limit: FindLimitParam
    snippet_max_chars: FindSnippetMaxCharsParam
    start_index: FindStartIndexParam


class SamplingParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: SamplingPromptParam
    model: SamplingModelParam


class EvalParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    script: EvalScriptParam


FetchParam = Annotated[
    FetchParams,
    Field(
        default_factory=FetchParams,
        description=schema_text(
            "页面获取方式与等待策略配置。",
            "Page fetching mode and wait-strategy configuration.",
        ),
    ),
]
RenderParam = Annotated[
    RenderParams,
    Field(
        default_factory=RenderParams,
        description=schema_text(
            "正文提取、输出格式及续读配置。",
            "Main-content extraction, output-format, and continue-read configuration.",
        ),
    ),
]
FindParam = Annotated[
    Optional[FindParams],
    Field(
        default=None,
        description=schema_text(
            "查找配置。仅当 operation=\"find\" 时提供。",
            "Find configuration. Provide only when operation=\"find\".",
        ),
    ),
]
SamplingParam = Annotated[
    Optional[SamplingParams],
    Field(
        default=None,
        description=schema_text(
            "提取配置。仅当 operation=\"sampling\" 时提供。",
            "Sampling configuration. Provide only when operation=\"sampling\".",
        ),
    ),
]
EvalParam = Annotated[
    Optional[EvalParams],
    Field(
        default=None,
        description=schema_text(
            "脚本配置。仅当 operation=\"eval\" 时提供。",
            "Script configuration. Provide only when operation=\"eval\".",
        ),
    ),
]


class AdvancedFetchParams(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), extra="forbid")

    url: UrlParam
    operation: OperationParam
    fetch: FetchParam
    render: RenderParam
    max_length: MaxLengthParam
    find: FindParam
    sampling: SamplingParam
    eval: EvalParam

    @property
    def can_use_cache(self) -> bool:
        return self.operation == "find" or self.render.cursor is not None

    def to_render_config(self) -> "RenderConfig":
        return RenderConfig(
            output_format=self.render.output_format,
            strategy=self.render.strategy,
            include_elements=self.render.include_elements,
        )

    @model_validator(mode="after")
    def _validate_semantics(self) -> "AdvancedFetchParams":
        has_find = self.find is not None
        has_sampling = self.sampling is not None
        has_eval = self.eval is not None

        if self.operation == "view":
            if has_find or has_sampling or has_eval:
                raise ValueError(
                    schema_error(
                        "operation=view 时，不能提供 find、sampling 或 eval 对象。",
                        "When operation=view, find, sampling, and eval objects must not be provided.",
                    )
                )
        elif self.operation == "find":
            if not has_find or has_sampling or has_eval:
                raise ValueError(
                    schema_error(
                        "operation=find 时，必须提供 find 对象，且不能提供 sampling 或 eval 对象。",
                        "When operation=find, the find object is required, and sampling or eval objects must not be provided.",
                    )
                )
        elif self.operation == "sampling":
            if not ENABLE_PROMPT_EXTRACTION:
                raise ValueError(
                    schema_error(
                        "当前环境未启用 sampling 功能（ENABLE_PROMPT_EXTRACTION=false）。",
                        "sampling is disabled in the current environment (ENABLE_PROMPT_EXTRACTION=false).",
                    )
                )
            if not has_sampling or has_find or has_eval:
                raise ValueError(
                    schema_error(
                        "operation=sampling 时，必须提供 sampling 对象，且不能提供 find 或 eval 对象。",
                        "When operation=sampling, the sampling object is required, and find or eval objects must not be provided.",
                    )
                )
        elif self.operation == "eval":
            if not has_eval or has_find or has_sampling:
                raise ValueError(
                    schema_error(
                        "operation=eval 时，必须提供 eval 对象，且不能提供 find 或 sampling 对象。",
                        "When operation=eval, the eval object is required, and find or sampling objects must not be provided.",
                    )
                )
            if self.fetch.mode != "dynamic":
                raise ValueError(
                    schema_error(
                        "operation=eval 时，fetch.mode 必须为 dynamic。",
                        "When operation=eval, fetch.mode must be dynamic.",
                    )
                )

        if self.operation != "view" and self.render.cursor is not None:
            raise ValueError(
                schema_error(
                    "render.cursor 仅对 view 操作有效。",
                    "render.cursor is only valid for view operations.",
                )
            )

        if self.render.engine == "markdownify" and self.render.strategy != "default":
            raise ValueError(
                schema_error(
                    "render.engine=markdownify 时，render.strategy 只能为 default。",
                    "When render.engine=markdownify, render.strategy must be default.",
                )
            )

        return self


class RenderConfig(BaseModel):
    output_format: OutputFormatParam
    strategy: StrategyParam
    include_elements: IncludeElementsParam
