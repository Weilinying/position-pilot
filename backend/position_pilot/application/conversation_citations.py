"""Conversation Answer 的来源 ID 与显式 URL 验证。"""

import re
from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

SOURCE_TOKEN = re.compile(r"\[source:([^\]]+)\]")
URL_TOKEN = re.compile(r"https?://[^\s<>\[\]()]+")
SUCCESS_STATUSES = frozenset({"OK", "SUCCESS"})


class CitationValidationError(ValueError):
    """回答声明了未在本轮成功观察到的来源或 URL。"""


class CitationSource(Protocol):
    """Citation 验证所需的最小 Source Contract。"""

    @property
    def source_id(self) -> UUID | None: ...

    @property
    def status(self) -> str: ...

    @property
    def url(self) -> str | None: ...

    @property
    def source_type(self) -> str: ...


def validate_citations(
    answer: str,
    sources: Sequence[CitationSource],
) -> tuple[UUID, ...]:
    """验证 inline Source Token 与 URL，并按首次出现顺序返回来源 ID。"""

    source_ids = [source.source_id for source in sources if source.source_id is not None]
    if len(source_ids) != len(set(source_ids)):
        raise CitationValidationError("Source ID 重复")
    allowed = {
        source.source_id: source
        for source in sources
        if source.source_id is not None
        and source.status in SUCCESS_STATUSES
        and source.source_type != "PORTFOLIO_SNAPSHOT"
    }
    tokens = SOURCE_TOKEN.findall(answer)
    if answer.count("[source:") != len(tokens):
        raise CitationValidationError("Source Token 格式无效")
    cited: list[UUID] = []
    for token in tokens:
        try:
            source_id = UUID(token)
        except ValueError as error:
            raise CitationValidationError("Source ID 格式无效") from error
        if source_id not in allowed:
            raise CitationValidationError("Source 未在本轮成功观察")
        if source_id not in cited:
            cited.append(source_id)

    if allowed and not cited:
        raise CitationValidationError("使用 Tool 事实的回答缺少 inline Citation")
    allowed_urls = {
        allowed[source_id].url for source_id in cited if allowed[source_id].url is not None
    }
    for match in URL_TOKEN.finditer(answer):
        url = match.group().rstrip(".,;:!?)。，；：！？")
        if url not in allowed_urls:
            raise CitationValidationError("显式 URL 不属于本轮来源")
    return tuple(cited)


__all__ = ["CitationValidationError", "CitationSource", "validate_citations"]
