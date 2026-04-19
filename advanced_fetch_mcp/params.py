from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .settings import DEFAULT_MAX_LENGTH, ENABLE_PROMPT_EXTRACTION

FetchMode = Literal["dynamic", "static"]
ExtractStrategy = Literal["strict", "loose", "none"]

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
        default=0,
        ge=0,
        description="dynamic 模式下，networkidle 后额外等待秒数（适合有懒加载内容的页面）。",
    ),
]
TimeoutParam = Annotated[
    Optional[float],
    Field(default=None, ge=0.1, description="抓取超时秒数，超时后返回当前已加载内容。"),
]
MarkdownifyParam = Annotated[
    bool,
    Field(default=True, description="是否转换成 Markdown；为 false 时返回原始 HTML。"),
]
StrategyParam = Annotated[
    ExtractStrategy,
    Field(
        default="strict",
        description="提取策略。strict 精确提取正文（避免误删）；loose 尽可能保留内容；none 返回完整 body。",
    ),
]
KeepMediaParam = Annotated[
    bool, Field(default=False, description="是否保留图片、视频、音频、SVG 等媒体节点。")
]
CursorParam = Annotated[
    Optional[int],
    Field(
        default=None,
        ge=0,
        description="文本位置偏移。普通提取时从该位置续读，find 时从该位置开始搜索。",
    ),
]
MaxLengthParam = Annotated[
    int, Field(default=DEFAULT_MAX_LENGTH, ge=1, description="文本结果长度上限。")
]
FindInPageParam = Annotated[
    Optional[str],
    Field(
        default=None,
        description="搜索关键词。返回 matches 列表，适合在长页面中定位关键部分。",
    ),
]
FindWithRegexParam = Annotated[
    bool, Field(default=False, description="是否把 find_in_page 按正则表达式处理。")
]
PromptParam = Annotated[
    Optional[str],
    Field(
        default=None,
        description="提取提示词。提供后，调用 LLM 对内容进行整理和提取，返回提取后的结果。可以避免原始页面内容污染调用方的上下文。",
    ),
]
EvaluateJSParam = Annotated[
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
        description="需要登录/过验证码时设为 true，打开可见浏览器让用户手动操作，完成后点按钮继续抓取。",
    ),
]
RefreshCacheParam = Annotated[
    bool, Field(default=False, description="是否忽略已有缓存重新抓取。")
]


class AdvancedFetchParams(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), extra="forbid")

    url: UrlParam
    mode: ModeParam = "dynamic"
    wait_for: WaitForParam = 0
    timeout: TimeoutParam = None
    markdownify: MarkdownifyParam = True
    strategy: StrategyParam = "strict"
    keep_media: KeepMediaParam = False
    cursor: CursorParam = None
    max_length: MaxLengthParam = DEFAULT_MAX_LENGTH
    find_in_page: FindInPageParam = None
    find_with_regex: FindWithRegexParam = False
    prompt: PromptParam = None
    evaluateJS: EvaluateJSParam = None
    require_user_intervention: RequireInterventionParam = False
    refresh_cache: RefreshCacheParam = False

    @model_validator(mode="after")
    def _validate_semantics(self) -> "AdvancedFetchParams":
        if self.prompt is not None and not ENABLE_PROMPT_EXTRACTION:
            raise ValueError(
                "当前环境未启用 prompt 功能（ENABLE_PROMPT_EXTRACTION=false）。"
            )
        if self.evaluateJS is not None and (
            self.prompt is not None or self.find_in_page is not None
        ):
            raise ValueError(
                "提供 evaluateJS 时，不能再同时提供 prompt 或 find_in_page。"
            )
        if self.evaluateJS is not None and self.mode == "static":
            raise ValueError("evaluateJS 只支持 dynamic 模式。")
        if self.prompt is not None and self.find_in_page is not None:
            raise ValueError("提供 prompt 时，不能再同时提供 find_in_page。")
        if self.find_in_page is None and self.find_with_regex:
            raise ValueError("find_with_regex 需要配合 find_in_page 使用。")
        return self
