"""Agent 回答所使用来源的 Application-owned Registry 与验证边界。"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from position_pilot.application.investment_answer import (
    InvalidStructuredAnswer,
    SourceReference,
    SourceReferenceType,
    StructuredInvestmentAnswer,
    UnresolvedSourceReference,
    parse_structured_answer,
    validate_source_references,
)


class ContextSourceType(StrEnum):
    """Final Answer 可追溯的事实来源类别。"""

    PORTFOLIO_SNAPSHOT = "PORTFOLIO_SNAPSHOT"
    CURRENT_QUOTE = "CURRENT_QUOTE"
    PRICE_HISTORY = "PRICE_HISTORY"
    RECENT_NEWS = "RECENT_NEWS"
    MARKET_CONTEXT = "MARKET_CONTEXT"


@dataclass(frozen=True, slots=True)
class ContextSource:
    """本轮成功 Context 或保留的失败 Tool Attempt。"""

    type: ContextSourceType
    status: str
    ticker: str | None = None
    provider: str | None = None
    feed: str | None = None
    market_timestamp: datetime | None = None
    fetched_at: datetime | None = None
    source_id: UUID | None = None
    url: str | None = None
    title: str | None = None
    publisher: str | None = None
    published_at: datetime | None = None
    provider_reference: str | None = None

    @property
    def source_type(self) -> str:
        """提供与持久化 Source 一致的 Citation 分类。"""

        return self.type.value

    def as_reference(self) -> SourceReference | None:
        """只有状态为 OK 的已观察 Context 才能成为回答来源。"""

        if self.status != "OK":
            return None
        return SourceReference(SourceReferenceType(self.type.value), self.ticker)


class SourceValidator:
    """验证模型声明的 Source 真实存在于本轮成功 Context。"""

    @staticmethod
    def evaluate(
        content: str,
        sources: tuple[ContextSource, ...],
    ) -> tuple[
        StructuredInvestmentAnswer | None,
        InvalidStructuredAnswer | UnresolvedSourceReference | None,
    ]:
        """解析外层回答 Contract，并校验声明的来源集合。"""

        try:
            answer = parse_structured_answer(content)
        except InvalidStructuredAnswer as error:
            return None, error
        available = tuple(
            reference for source in sources if (reference := source.as_reference()) is not None
        )
        try:
            validate_source_references(answer, available)
        except UnresolvedSourceReference as error:
            return None, error
        return answer, None

    @staticmethod
    def select_declared(
        answer: StructuredInvestmentAnswer,
        sources: tuple[ContextSource, ...],
    ) -> tuple[ContextSource, ...]:
        """返回声明的成功来源，同时保留失败 Attempt 的既有可观测性。"""

        declared = set(answer.source_refs)
        return tuple(
            source
            for source in sources
            if (reference := source.as_reference()) is None or reference in declared
        )
