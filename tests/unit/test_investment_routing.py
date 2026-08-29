"""Context Selection Trace 单元测试。"""

from decimal import Decimal
from uuid import UUID

from position_pilot.application.investment_context import HistoricalBuyFacts, PortfolioSnapshot
from position_pilot.application.investment_routing import (
    ContextSelectionMode,
    ContextSelectionTrace,
)
from position_pilot.application.llm import LLMToolCall
from position_pilot.domain.portfolio import (
    CashBalance,
    PortfolioState,
    Position,
    PositionType,
)

USER_ID = UUID("00000000-0000-0000-0000-000000000111")
AVAILABLE_TOOLS = (
    "get_current_quote",
    "get_recent_price_history",
    "get_recent_news",
    "get_market_context",
)


def _snapshot() -> PortfolioSnapshot:
    state = PortfolioState(
        user_id=USER_ID,
        cash=CashBalance(USER_ID, Decimal("1000"), Decimal("300")),
        positions=(
            Position(
                ticker="GOOG",
                position_type=PositionType.LONG_TERM,
                shares=Decimal("2"),
                average_cost=Decimal("200"),
                cost_basis=Decimal("400"),
            ),
            Position(
                ticker="GOOG",
                position_type=PositionType.SWING,
                shares=Decimal("1"),
                average_cost=Decimal("220"),
                cost_basis=Decimal("220"),
            ),
        ),
        transaction_count=0,
    )
    return PortfolioSnapshot.from_state(state, HistoricalBuyFacts.from_transactions(state, ()))


def test_no_tool_selection_is_explicit_and_keeps_capability_list() -> None:
    """Portfolio-only 问题应能记录为无需外部 Context。"""

    trace = ContextSelectionTrace.from_tool_calls(
        snapshot=_snapshot(),
        available_tools=AVAILABLE_TOOLS,
        model_tool_calls=(),
    )

    assert trace.mode is ContextSelectionMode.NO_EXTERNAL_CONTEXT
    assert trace.available_tools == AVAILABLE_TOOLS
    assert trace.model_selected_tools == ()
    assert trace.model_quote_request_purposes == ()
    assert trace.required_tools == ()
    assert trace.selected_tools == ()
    assert trace.selected_context_count == 0
    assert trace.selected_existing_position_types == ()
    assert trace.selected_unheld_ticker_count == 0


def test_selection_deduplicates_contexts_and_preserves_matching_position_types() -> None:
    """重复 Tool Call 不得夸大 Context 数量，并保留两类持仓匹配。"""

    trace = ContextSelectionTrace.from_tool_calls(
        snapshot=_snapshot(),
        available_tools=AVAILABLE_TOOLS,
        model_tool_calls=(
            LLMToolCall("quote-1", "get_current_quote", {"ticker": "goog"}),
            LLMToolCall("quote-2", "get_current_quote", {"ticker": " GOOG "}),
            LLMToolCall("news-1", "get_recent_news", {"ticker": "GOOG"}),
        ),
    )

    assert trace.mode is ContextSelectionMode.NATIVE_TOOL_SELECTION
    assert trace.selected_tools == ("get_current_quote", "get_recent_news")
    assert trace.selected_context_count == 2
    assert trace.selected_existing_position_count == 2
    assert trace.selected_existing_position_types == (
        PositionType.LONG_TERM,
        PositionType.SWING,
    )
    assert trace.selected_unheld_ticker_count == 0


def test_selection_counts_unheld_tickers_without_logging_their_identity() -> None:
    """未持有标的只进入数量诊断，不把 ticker 放入日志字段。"""

    trace = ContextSelectionTrace.from_tool_calls(
        snapshot=_snapshot(),
        available_tools=AVAILABLE_TOOLS,
        model_tool_calls=(
            LLMToolCall("quote-1", "get_current_quote", {"ticker": "MSFT"}),
            LLMToolCall("history-1", "get_recent_price_history", {"ticker": "MSFT"}),
        ),
    )
    log_extra = trace.as_log_extra(routing_latency_ms=12.5)

    assert trace.selected_context_count == 2
    assert trace.selected_existing_position_count == 0
    assert trace.selected_existing_position_types == ()
    assert trace.selected_unheld_ticker_count == 1
    assert log_extra["routing_latency_ms"] == 12.5
    assert "MSFT" not in repr(log_extra)


def test_global_market_context_counts_without_ticker_or_position_match() -> None:
    """无参数 Market Context 参与 Context 数量，但不伪装成持仓标的。"""

    trace = ContextSelectionTrace.from_tool_calls(
        snapshot=_snapshot(),
        available_tools=AVAILABLE_TOOLS,
        model_tool_calls=(
            LLMToolCall("market-1", "get_market_context", {}),
            LLMToolCall("market-2", "get_market_context", {}),
        ),
    )

    assert trace.selected_tools == ("get_market_context",)
    assert trace.selected_context_count == 1
    assert trace.selected_existing_position_count == 0
    assert trace.selected_existing_position_types == ()
    assert trace.selected_unheld_ticker_count == 0


def test_required_context_is_distinct_from_model_selection() -> None:
    """Required Context Floor 必须可诊断，不能伪装成模型自主选择。"""

    trace = ContextSelectionTrace.from_tool_calls(
        snapshot=_snapshot(),
        available_tools=AVAILABLE_TOOLS,
        model_tool_calls=(
            LLMToolCall(
                "quote-1",
                "get_current_quote",
                {
                    "ticker": "GOOG",
                    "request_purpose": "DISCRETIONARY_CURRENT_RISK_ACTION",
                },
            ),
        ),
        required_tool_calls=(LLMToolCall("required-market", "get_market_context", {}),),
    )

    assert trace.mode is ContextSelectionMode.NATIVE_WITH_REQUIRED_CONTEXT
    assert trace.model_selected_tools == ("get_current_quote",)
    assert trace.model_quote_request_purposes == ("DISCRETIONARY_CURRENT_RISK_ACTION",)
    assert trace.required_tools == ("get_market_context",)
    assert trace.selected_tools == ("get_current_quote", "get_market_context")
