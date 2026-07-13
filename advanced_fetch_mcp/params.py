from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .settings import (
    AUTO_WAIT_MIN_CONTENT_LENGTH,
    AUTO_WAIT_MIN_STABLE_SECONDS,
    DEFAULT_MAX_LENGTH,
    ENABLE_PROMPT_EXTRACTION,
    FETCH_TIMEOUT_SECONDS,
    MAX_FIND_MATCHES,
    MAX_LINKS_COUNT,
    SCHEMA_LANGUAGE,
)

FetchMode = Literal["dynamic", "static"]
MarkdownEngine = Literal["article", "full"]
OutputFormat = Literal["markdown", "html"]
Operation = Literal["view", "find", "sampling", "eval", "request_human_action"]


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
            "操作类型：查看、页面内搜索、LLM 提取、执行 JS 或 请求人工介入处理鉴权（如登录、解决 captcha 等）。",
            "Operation: view, in-page search, LLM extraction, JS execution, or manual intervention.",
        ),
    ),
]
FetchModeParam = Annotated[
    FetchMode,
    Field(
        default="static",
        description=schema_text(
            "抓取方式：dynamic 用浏览器，static 静态 request。",
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
RenderImagesParam = Annotated[
    bool,
    Field(
        default=False,
        description=schema_text(
            "是否在结果中嵌入图片。true 时下载图片并转为 base64 data URI 嵌入 markdown；false 时仅保留 alt 文本。",
            "Whether to embed images in the result. When true, downloads images and embeds them as base64 data URIs in markdown; when false, keeps only alt text.",
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
LinksLimitParam = Annotated[
    int,
    Field(
        default=MAX_LINKS_COUNT,
        ge=1,
        description=schema_text(
            "本次最多返回多少条链接。",
            "Maximum number of links to return for this request.",
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
            "在页面上下文执行的 JavaScript 代码。",
            "JavaScript code executed in the page context.",
        )
    ),
]


class FetchParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: FetchModeParam
    min_stable_seconds: MinStableSecondsParam
    min_content_length: MinContentLengthParam
    timeout: TimeoutParam


class ViewParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_format: OutputFormatParam
    markdown_engine: MarkdownEngineParam
    render_images: RenderImagesParam
    cursor: CursorParam
    links: Optional[LinksParams] = Field(
        default=None,
        description=schema_text(
            "提取页面中的全部链接。提供后响应中会额外包含 links 字段。",
            "Extract all links from the page. When set, the response includes a links field.",
        ),
    )


class FindParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: FindQueryParam
    regex: FindRegexParam
    limit: FindLimitParam
    start_index: FindStartIndexParam


class SamplingParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: SamplingPromptParam
    model: SamplingModelParam


class EvalParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    script: EvalScriptParam


class LinksParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: LinksLimitParam


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
            "视图提取、输出格式、图片嵌入及续读配置。",
            "View extraction, output-format, image embedding, and continue-read configuration.",
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
    view: ViewParam
    max_length: MaxLengthParam
    find: FindParam
    sampling: SamplingParam
    eval: EvalParam

    def to_view_config(self) -> "ViewConfig":
        return ViewConfig(
            output_format=self.view.output_format,
            markdown_engine=self.view.markdown_engine,
            render_images=self.view.render_images,
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
        elif self.operation == "request_human_action":
            if has_find or has_sampling or has_eval:
                raise ValueError(
                    schema_error(
                        "operation=request_human_action 时，不能提供 find、sampling 或 eval 对象。",
                        "When operation=request_human_action, find, sampling, and eval objects must not be provided.",
                    )
                )
            if self.fetch.mode != "dynamic":
                raise ValueError(
                    schema_error(
                        "operation=request_human_action 时，fetch.mode 必须为 dynamic。",
                        "When operation=request_human_action, fetch.mode must be dynamic.",
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

        if self.operation != "view" and self.view.cursor is not None:
            raise ValueError(
                schema_error(
                    "view.cursor 仅对 view 操作有效。",
                    "view.cursor is only valid for view operations.",
                )
            )

        return self


class ViewConfig(BaseModel):
    output_format: OutputFormatParam
    markdown_engine: MarkdownEngineParam
    render_images: RenderImagesParam
