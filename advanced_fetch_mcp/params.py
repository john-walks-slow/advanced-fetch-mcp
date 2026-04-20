from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .settings import DEFAULT_MAX_LENGTH, ENABLE_PROMPT_EXTRACTION, SCHEMA_LANGUAGE

FetchMode = Literal["dynamic", "static"]
ExtractStrategy = Literal["strict", "loose"] | None
OutputFormat = Literal["markdown", "html"]
Operation = Literal["view", "find", "sampling", "eval"]
WaitForValue = float | Literal["auto"]
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
            "操作类型。view：获取页面正文。find：在正文中查找匹配项。sampling：使用 LLM 从正文中提取信息。eval：在页面环境中执行 JavaScript 并返回结果。",
            "Operation type. view: get the page main content. find: search matches in the main content. sampling: use an LLM to extract information from the main content. eval: execute JavaScript in the page context and return the result.",
        ),
    ),
]
FetchModeParam = Annotated[
    FetchMode,
    Field(
        default="dynamic",
        description=schema_text(
            "抓取方式。dynamic：使用浏览器加载并执行页面脚本。static：直接 HTTP 请求页面源码。",
            "Fetch mode. dynamic: use a browser to load the page and execute scripts. static: request the page source directly over HTTP.",
        ),
    ),
]
WaitForParam = Annotated[
    WaitForValue,
    Field(
        default="auto",
        description=schema_text(
            "等待策略（仅 dynamic 模式有效）。auto：自动等待网络空闲且正文区域稳定。数字：页面加载后额外等待的秒数。",
            "Wait strategy (only effective in dynamic mode). auto: automatically wait until the network is idle and the main-content area is stable. Number: extra seconds to wait after page load.",
        ),
    ),
]
TimeoutParam = Annotated[
    Optional[float],
    Field(
        default=None,
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
            "用于需要登录、验证码或人工操作的页面。设为 true 时将弹出可见浏览器窗口，等待用户操作完成后自动继续抓取。",
            "For pages that require login, CAPTCHA, or manual actions. When set to true, a visible browser window is opened and fetching resumes automatically after the user finishes.",
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
        default=None,
        description=schema_text(
            "正文提取策略。strict：优先保证内容纯度。loose：优先保证内容覆盖。null：使用默认平衡策略。",
            "Main-content extraction strategy. strict: prioritize content purity. loose: prioritize content coverage. null: use the default balanced strategy.",
        ),
    ),
]
IncludeElementsParam = Annotated[
    list[SemanticExtra],
    Field(
        default=["tables", "formatting"],
        description=schema_text(
            "除正文外需要包含的内容类型。可选值：tables、formatting、images、links、comments。",
            "Content types to include in addition to the main content. Allowed values: tables, formatting, images, links, comments.",
        ),
    ),
]
MaxLengthParam = Annotated[
    int,
    Field(
        default=DEFAULT_MAX_LENGTH,
        ge=1,
        description=schema_text(
            "文本最大长度。",
            "Maximum text length.",
        ),
    ),
]
CursorParam = Annotated[
    Optional[int],
    Field(
        default=None,
        ge=0,
        description=schema_text(
            "文本起始偏移量。用于继续读取或继续搜索长页面。",
            "Text start offset used to continue reading or continue searching on long pages.",
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
SamplingPromptParam = Annotated[
    str,
    Field(
        description=schema_text(
            "指导 LLM 从页面正文中提取信息的提示词。",
            "Prompt that guides the LLM to extract information from the page main content.",
        )
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
    wait_for: WaitForParam
    timeout: TimeoutParam
    require_user_intervention: RequireInterventionParam

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

    @model_validator(mode="after")
    def _validate_wait_for(self) -> "FetchParams":
        if self.wait_for != "auto" and self.wait_for < 0:
            raise ValueError(
                schema_error(
                    "fetch.wait_for 必须为非负数或 auto。",
                    "fetch.wait_for must be a non-negative number or auto.",
                )
            )
        return self


class RenderParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_format: OutputFormatParam
    strategy: StrategyParam
    include_elements: IncludeElementsParam
    max_length: MaxLengthParam
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


class SamplingParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: SamplingPromptParam


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
            "正文提取、输出格式及结果窗口控制。",
            "Main-content extraction, output-format, and result-window configuration.",
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
    find: FindParam
    sampling: SamplingParam
    eval: EvalParam

    @property
    def should_skip_cache(self) -> bool:
        return not (self.operation == "find" or self.render.cursor is not None)

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

        if self.operation not in {"view", "find"} and self.render.cursor is not None:
            raise ValueError(
                schema_error(
                    "render.cursor 仅对 view 和 find 操作有效。",
                    "render.cursor is only valid for view and find operations.",
                )
            )

        return self


class RenderConfig(BaseModel):
    output_format: OutputFormatParam
    strategy: StrategyParam
    include_elements: IncludeElementsParam
