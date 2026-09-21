"""Investment Context Builder 边界测试。"""

import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from position_pilot.application.investment_agent import SYSTEM_PROMPT, InvestmentAgent
from position_pilot.application.investment_context import (
    InvestmentPortfolioContext,
    PortfolioSnapshot,
)
from position_pilot.application.investment_context_builder import InvestmentContextBuilder
from position_pilot.application.llm import LLMRole
from position_pilot.application.position_funding import PositionPlanIntent
from position_pilot.domain.portfolio import PositionType, User, rebuild_portfolio

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 9, 21, tzinfo=UTC)


def _context() -> InvestmentPortfolioContext:
    state = rebuild_portfolio(
        User.create(
            user_id=USER_ID,
            display_name="Context Test",
            initial_cash=Decimal("1000"),
            created_at=NOW,
        ),
        [],
        [],
    )
    return InvestmentPortfolioContext.from_ledger(state, ())


def test_empty_optional_context_preserves_historical_payload_shape() -> None:
    context = _context()
    messages = InvestmentContextBuilder(SYSTEM_PROMPT).build(context, "我的现金是多少？")

    assert messages[0].role is LLMRole.SYSTEM
    assert messages[0].content == SYSTEM_PROMPT
    payload = json.loads(messages[1].content or "")
    assert set(payload) == {
        "question",
        "context_capabilities",
        "decision_context",
        "portfolio_snapshot",
        "available_source_reference",
        "response_contract",
        "structured_answer_schema",
    }
    assert messages == InvestmentAgent._initial_messages(
        PortfolioSnapshot.from_context(context),
        "我的现金是多少？",
    )


def test_confirmed_intent_and_memory_are_injected_with_explicit_authority() -> None:
    messages = InvestmentContextBuilder("system").build(
        _context(),
        "如何配置 GOOG？",
        position_plan_intents=(PositionPlanIntent("GOOG", PositionType.LONG_TERM, Decimal("300")),),
        memory_context=("用户偏好分批思考",),
    )

    payload = json.loads(messages[1].content or "")
    assert payload["position_funding_snapshots"][0]["remaining_target_budget"] == "300"
    assert payload["memory_context"] == {
        "authority": "NON_AUTHORITATIVE_BACKGROUND",
        "items": ["用户偏好分批思考"],
    }
