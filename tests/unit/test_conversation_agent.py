"""Conversation 与 Production Investment Agent 适配测试。"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from position_pilot.application.conversation_agent import ConversationInvestmentAgent
from position_pilot.application.conversation_service import (
    ConversationHistoryMessage,
    ConversationMessageRole,
)
from position_pilot.application.investment_agent import (
    ContextSource,
    ContextSourceType,
    InvestmentAnswer,
    InvestmentFailureCode,
    InvestmentRequestFailure,
    InvestmentResponseStatus,
)
from position_pilot.application.llm import LLMMessage, LLMRole

ACCOUNT_ID = UUID("10000000-0000-4000-8000-000000000001")
USER_ID = UUID("20000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 9, 22, tzinfo=UTC)


@dataclass(slots=True)
class FakeHistoryAgent:
    """记录 Conversation 注入并返回固定 Investment Result。"""

    result: InvestmentAnswer | InvestmentRequestFailure
    histories: list[tuple[LLMMessage, ...]] = field(default_factory=list)

    def answer_with_history(
        self,
        user_id: UUID,
        question: str,
        conversation_history: tuple[LLMMessage, ...],
    ) -> InvestmentAnswer | InvestmentRequestFailure:
        assert user_id == USER_ID
        assert question == "现在呢？"
        self.histories.append(conversation_history)
        return self.result


def test_maps_visible_history_and_observed_sources() -> None:
    agent = FakeHistoryAgent(
        InvestmentAnswer(
            InvestmentResponseStatus.OK,
            "结合最新事实重新分析。",
            (
                ContextSource(
                    ContextSourceType.CURRENT_QUOTE,
                    "OK",
                    ticker="GOOG",
                    provider="ALPACA",
                    market_timestamp=NOW,
                    fetched_at=NOW,
                ),
            ),
        )
    )

    result = ConversationInvestmentAgent(agent).answer(
        account_id=ACCOUNT_ID,
        portfolio_user_id=USER_ID,
        question="现在呢？",
        history=(
            ConversationHistoryMessage(ConversationMessageRole.USER, "分析 GOOG"),
            ConversationHistoryMessage(ConversationMessageRole.ASSISTANT, "先观察。"),
        ),
    )

    assert [message.role for message in agent.histories[0]] == [
        LLMRole.USER,
        LLMRole.ASSISTANT,
    ]
    assert result.answer == "结合最新事实重新分析。"
    assert result.sources[0].provider_reference == "GOOG"
    assert result.sources[0].content_scope == "STRUCTURED_FACT"


def test_maps_existing_agent_failure_without_creating_answer() -> None:
    agent = FakeHistoryAgent(
        InvestmentRequestFailure(
            InvestmentFailureCode.LLM_PROVIDER_UNAVAILABLE,
            "unavailable",
        )
    )

    result = ConversationInvestmentAgent(agent).answer(
        account_id=ACCOUNT_ID,
        portfolio_user_id=USER_ID,
        question="现在呢？",
        history=(),
    )

    assert result.answer is None
    assert result.failure_code == "LLM_PROVIDER_UNAVAILABLE"
