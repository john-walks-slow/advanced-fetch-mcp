from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .settings import DEFAULT_MAX_LENGTH, ENABLE_PROMPT_EXTRACTION

FetchMode = Literal["dynamic", "static"]
Scope = Literal["full", "body", "content"]


class FindInPageOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: Optional[str] = Field(
        default=None,
        description="要搜索的关键词或模式。首次搜索时提供。",
    )
    regex: bool = Field(
        default=False,
        description="是否把 query 按正则表达式处理。",
    )
    cursor: Optional[str] = Field(
        default=None,
        description="续读或跳转游标。可以使用上一次返回的 next_cursor，也可以使用 matches 里的 cursor。",
    )

    @model_validator(mode="after")
    def _validate(self) -> "FindInPageOptions":
        if not self.query and not self.cursor:
            raise ValueError("find_in_page 至少需要提供 query 或 cursor。")
        if self.query and self.cursor:
            raise ValueError("find_in_page.query 和 find_in_page.cursor 不能同时提供。")
        if self.cursor and self.regex:
            raise ValueError("使用 find_in_page.cursor 时，不需要再提供 regex。")
        return self


class AdvancedFetchParams(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), extra="forbid")

    mode: FetchMode = Field(
        default="dynamic",
        description="页面抓取方式。dynamic 使用浏览器加载页面；static 直接请求页面响应。",
    )
    wait_for: float = Field(
        default=0,
        ge=0,
        description="仅在 dynamic 模式下生效。页面导航完成后额外追加等待的秒数。",
    )
    require_user_intervention: bool = Field(
        default=False,
        description="是否要求人工在浏览器里完成登录、验证或其他操作后再继续。",
    )

    markdownify: bool = Field(
        default=True,
        description="是否把选中的页面范围转换成 Markdown 文本；为 false 时返回原始 HTML。",
    )
    scope: Scope = Field(
        default="content",
        description="基础范围。可选 full、body、content。",
    )
    selector: Optional[str] = Field(
        default=None,
        description="在基础范围内，再用 CSS selector 选出一个更小的子区域。",
    )
    strip: list[str] = Field(
        default_factory=list,
        description="在当前范围内，按这些 CSS selector 删除节点。",
    )
    keep_media: bool = Field(
        default=False,
        description="是否保留图片、视频、音频、SVG 等媒体节点。",
    )

    prompt: Optional[str] = Field(
        default=None,
        description="提取提示词。提供后，会先得到当前视图文本，再交给模型整理。",
    )
    find_in_page: Optional[FindInPageOptions] = Field(
        default=None,
        description="在当前提取文本里搜索，或用游标继续读取/跳转。",
    )
    evaluateJS: Optional[str] = Field(
        default=None,
        description="在真实页面上下文中执行 JavaScript，并返回脚本结果。",
    )

    max_length: int = Field(
        default=DEFAULT_MAX_LENGTH,
        ge=1,
        description="文本结果长度上限。普通提取、prompt 和 evaluateJS 会按这个长度截断；搜索时表示窗口大小。",
    )
    refresh_cache: bool = Field(
        default=False,
        description="是否忽略当前 URL 的已有缓存并重新抓取；重新抓到的结果仍会写回缓存。evaluateJS 始终忽略缓存。",
    )

    @model_validator(mode="after")
    def _validate_semantics(self) -> "AdvancedFetchParams":
        if self.prompt is not None and not ENABLE_PROMPT_EXTRACTION:
            raise ValueError("当前环境未启用 prompt 功能（ENABLE_PROMPT_EXTRACTION=false）。")

        explicit_view_fields = self.model_fields_set & {"markdownify", "scope", "selector", "strip", "keep_media", "prompt", "find_in_page"}
        if self.evaluateJS is not None and explicit_view_fields:
            raise ValueError("提供 evaluateJS 时，不能再同时提供 markdownify、scope、selector、strip、keep_media、prompt 或 find_in_page。")
        if self.evaluateJS is not None and self.mode == "static":
            raise ValueError("evaluateJS 只支持 dynamic 模式。")
        if self.prompt is not None and self.find_in_page is not None:
            raise ValueError("prompt 和 find_in_page 互斥。")
        return self
