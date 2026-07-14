from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .settings import (
    AUTO_WAIT_MIN_STABLE_SECONDS,
    DEFAULT_MAX_LENGTH,
    ENABLE_PROMPT_EXTRACTION,
    FETCH_TIMEOUT_SECONDS,
    SCHEMA_LANGUAGE,
)

FetchMode = Literal["dynamic", "static"]
MarkdownEngine = Literal["article", "full"]
OutputFormat = Literal["markdown", "html"]
Operation = Literal["view", "find", "sampling", "eval", "elicit"]


def schema_text(zh: str, en: str) -> str:
    return zh if SCHEMA_LANGUAGE == "zh" else en


def schema_error(zh: str, en: str) -> str:
    return zh if SCHEMA_LANGUAGE == "zh" else en


UrlParam = Annotated[
    str,
    Field(
        description=schema_text(
            "目标网页的完整 URL 或之前结果的引用 ID（复用抓取结果）。",
            "Full URL of the target webpage, or a refid to reuse a previous fetch result.",
        )
    ),
]
OperationParam = Annotated[
    Operation,
    Field(
        default="view",
        description=schema_text(
            "操作类型：查看、页面内搜索、LLM 提取、执行 JS 或 请求用户手动操作（当且仅当被 captcha / 登录墙阻拦时使用）。",
            "Operation: view, in-page search, LLM extraction, JS execution, or elicit (request manual user action, use only when blocked by captcha/login wall).",
        ),
    ),
]
FetchModeParam = Annotated[
    FetchMode,
    Field(
        default="static",
        description=schema_text(
            "抓取方式：dynamic=浏览器，static=request。自动复用鉴权信息。",
            "Fetch mode: dynamic uses a browser; static requests source HTML directly. Auth info is automatically reused.",
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
MarkdownEngineParam = Annotated[
    MarkdownEngine,
    Field(
        default="article",
        description=schema_text(
            "markdown 提取引擎。article 用 trafilatura 提取文章正文；full 用 markdownify 提取完整页面。",
            "Markdown extraction engine. article uses trafilatura for article main content; full uses markdownify for the full page.",
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
            "继续读取的偏移量。对 view 和 find 操作均有效。",
            "Continue-read offset. Valid for both view and find operations.",
        ),
    ),
]
OutputToFileParam = Annotated[
    Optional[str],
    Field(
        default=None,
        description=schema_text(
            "若指定，结果以 JSON 格式写入此文件路径而非直接返回，此时忽略 max_length。",
            "If set, writes the full result as JSON to this file path instead of returning it. max_length is ignored.",
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
            "在页面上下文执行的 JavaScript 代码。",
            "JavaScript code executed in the page context.",
        )
    ),
]


class FetchParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: FetchModeParam
    min_stable_seconds: MinStableSecondsParam
    timeout: TimeoutParam


class ViewParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_format: OutputFormatParam
    markdown_engine: MarkdownEngineParam
    max_length: MaxLengthParam
    links: bool = Field(
        default=True,
        description=schema_text(
            "是否提取页面中的出链。",
            "Whether to extract all links from the page.",
        ),
    )
    with_screenshot: bool = Field(
        default=False,
        description=schema_text(
            "是否截图。自动使用 dynamic 模式获取页面并截取首屏，返回 base64 编码的 PNG。",
            "Whether to capture a screenshot of the page. Forces dynamic mode and captures the initial viewport as a base64-encoded PNG.",
        ),
    )


class FindParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: FindQueryParam
    regex: FindRegexParam


class SamplingParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: SamplingPromptParam
    model: SamplingModelParam


class EvalParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    script: EvalScriptParam


class ElicitParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str | None = Field(
        default=None,
        description=schema_text(
            "向用户展示的说明文字，解释需要用户做什么。",
            "A message shown to the user explaining what action is needed.",
        ),
    )


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
ViewParam = Annotated[
    ViewParams,
    Field(
        default_factory=ViewParams,
        description=schema_text(
            "View 操作配置",
            "View operation configuration.",
        ),
    ),
]
FindParam = Annotated[
    Optional[FindParams],
    Field(
        default=None,
        description=schema_text(
            "Find 操作配置",
            "Find operation configuration.",
        ),
    ),
]
SamplingParam = Annotated[
    Optional[SamplingParams],
    Field(
        default=None,
        description=schema_text(
            "Sampling 操作配置",
            "Sampling operation configuration.",
        ),
    ),
]
EvalParam = Annotated[
    Optional[EvalParams],
    Field(
        default=None,
        description=schema_text(
            "Eval 操作配置",
            "Eval operation configuration.",
        ),
    ),
]
ElicitParam = Annotated[
    Optional[ElicitParams],
    Field(
        default=None,
        description=schema_text(
            "Elicit 操作配置",
            "Elicit operation configuration.",
        ),
    ),
]


class AdvancedFetchParams(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), extra="forbid")

    url: UrlParam
    operation: OperationParam
    fetch: FetchParam
    view: ViewParam
    find: FindParam
    sampling: SamplingParam
    eval: EvalParam
    elicit: ElicitParam
    cursor: CursorParam
    max_length: MaxLengthParam
    output_to_file: OutputToFileParam

    def to_view_config(self) -> "ViewConfig":
        return ViewConfig(
            output_format=self.view.output_format,
            markdown_engine=self.view.markdown_engine,
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
        elif self.operation == "elicit":
            if has_find or has_sampling or has_eval:
                raise ValueError(
                    schema_error(
                        "operation=elicit 时，不能提供 find、sampling 或 eval 对象。",
                        "When operation=elicit, find, sampling, and eval objects must not be provided.",
                    )
                )
            self.fetch.mode = "dynamic"
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

        if self.cursor is not None and self.operation not in ("view", "find"):
            raise ValueError(
                schema_error(
                    "cursor 仅对 view 和 find 操作有效。",
                    "cursor is only valid for view and find operations.",
                )
            )

        if self.view.with_screenshot:
            if self.operation != "view":
                raise ValueError(
                    schema_error(
                        "with_screenshot 仅对 view 操作有效。",
                        "with_screenshot is only valid for view operations.",
                    )
                )
            self.fetch.mode = "dynamic"

        return self


class ViewConfig(BaseModel):
    output_format: OutputFormatParam
    markdown_engine: MarkdownEngineParam
