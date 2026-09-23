"""将 Conversation Contract 适配到 Production Investment Agent。"""

from typing import Protocol
from uuid import UUID

from position_pilot.application.conversation_citations import (
    CitationValidationError,
    validate_citations,
)
from position_pilot.application.conversation_service import (
    ConversationAgentResult,
    ConversationHistoryMessage,
    ConversationMessageRole,
    ConversationSourceInput,
)
from position_pilot.application.investment_agent import (
    ContextSource,
    ContextSourceType,
    InvestmentAnswer,
    InvestmentRequestFailure,
)
from position_pilot.application.llm import LLMMessage, LLMRole


class HistoryAwareInvestmentAgent(Protocol):
    """Conversation 需要的内部 Investment Agent 能力。"""

    def answer_with_history(
        self,
        user_id: UUID,
        question: str,
        conversation_history: tuple[LLMMessage, ...],
    ) -> InvestmentAnswer | InvestmentRequestFailure: ...


class ConversationInvestmentAgent:
    """保持 Conversation 与 Agent Runtime 状态边界的 Application Adapter。"""

    def __init__(self, agent: HistoryAwareInvestmentAgent) -> None:
        self._agent = agent

    def answer(
        self,
        *,
        account_id: UUID,
        portfolio_user_id: UUID,
        question: str,
        history: tuple[ConversationHistoryMessage, ...],
    ) -> ConversationAgentResult:
        """只注入当前 Account 已授权的用户可见历史。"""

        del account_id
        result = self._agent.answer_with_history(
            portfolio_user_id,
            question,
            tuple(self._history_message(item) for item in history),
        )
        if isinstance(result, InvestmentRequestFailure):
            return ConversationAgentResult(failure_code=result.code.value)
        sources = tuple(self._source(source) for source in result.sources)
        try:
            validate_citations(result.answer, sources)
        except CitationValidationError:
            return ConversationAgentResult(failure_code="SOURCE_VALIDATION_FAILED")
        return ConversationAgentResult(
            answer=result.answer,
            sources=sources,
            warnings=result.warnings,
        )

    @staticmethod
    def _history_message(message: ConversationHistoryMessage) -> LLMMessage:
        role = LLMRole.USER if message.role is ConversationMessageRole.USER else LLMRole.ASSISTANT
        return LLMMessage(role, message.content)

    @staticmethod
    def _source(source: ContextSource) -> ConversationSourceInput:
        content_scope = (
            "TITLE_SUMMARY" if source.type is ContextSourceType.RECENT_NEWS else "STRUCTURED_FACT"
        )
        return ConversationSourceInput(
            source_type=source.type.value,
            provider=source.provider or "POSITIONPILOT",
            source_id=source.source_id,
            url=source.url,
            provider_reference=source.provider_reference or source.ticker,
            event_time=source.market_timestamp,
            fetched_at=source.fetched_at,
            title=source.title,
            publisher=source.publisher,
            published_at=source.published_at,
            content_scope=content_scope,
            status=source.status,
        )


__all__ = ["ConversationInvestmentAgent", "HistoryAwareInvestmentAgent"]
