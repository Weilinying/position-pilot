"""使用真实 Aliyun LLM 与固定 Market Data 的 M3 Behavioral Evaluation。"""

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from position_pilot.application.investment_agent import (
    ContextSourceType,
    InvestmentAgent,
    InvestmentAnswer,
    InvestmentRequestFailure,
    InvestmentResponseStatus,
)
from position_pilot.domain.market_data import (
    MarketDataCoverage,
    MarketDataResult,
    MarketDataStatus,
    MarketQuote,
)
from position_pilot.domain.portfolio import (
    CashBalance,
    PortfolioState,
    Position,
    PositionType,
)
from position_pilot.integrations.aliyun_llm import AliyunLLMProvider

pytestmark = [
    pytest.mark.online,
    pytest.mark.behavioral,
    pytest.mark.skipif(
        os.getenv("RUN_REAL_LLM_BEHAVIORAL_EVAL") != "1",
        reason="需要显式启用真实模型 Behavioral Eval",
    ),
]

USER_ID = UUID("00000000-0000-0000-0000-000000000101")
NOW = datetime(2026, 8, 24, 8, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class BehavioralCase:
    """固定输入、预期 Tool Trace 与 Human Review 关注点。"""

    id: str
    question: str
    available_cash: Decimal
    positions: tuple[Position, ...]
    market_results: dict[str, MarketDataResult[MarketQuote]]
    expected_tickers: tuple[str, ...]
    expected_status: InvestmentResponseStatus
    human_checks: tuple[str, ...]


class FixedPortfolioReader:
    """为真实模型提供固定、完整且可重复的 Portfolio Snapshot。"""

    def __init__(self, case: BehavioralCase) -> None:
        self._state = PortfolioState(
            user_id=USER_ID,
            cash=CashBalance(USER_ID, Decimal("1000"), case.available_cash),
            positions=case.positions,
            transaction_count=0,
        )

    def get_portfolio(self, user_id: UUID) -> PortfolioState:
        assert user_id == USER_ID
        return self._state


class FixedMarketData:
    """隔离实时波动，让 Behavioral Eval 只观察真实 LLM 行为。"""

    def __init__(self, results: dict[str, MarketDataResult[MarketQuote]]) -> None:
        self._results = results

    def get_current_quote(self, ticker: str) -> MarketDataResult[MarketQuote]:
        normalized = ticker.strip().upper()
        return self._results.get(
            normalized,
            MarketDataResult.failure(MarketDataStatus.NO_DATA, "固定场景没有该行情"),
        )


def position(
    ticker: str,
    position_type: PositionType,
    shares: str,
    average_cost: str,
) -> Position:
    """创建固定 Evaluation Position。"""

    shares_value = Decimal(shares)
    average_cost_value = Decimal(average_cost)
    return Position(
        ticker=ticker,
        position_type=position_type,
        shares=shares_value,
        cost_basis=shares_value * average_cost_value,
        average_cost=average_cost_value,
    )


def fixed_quote(ticker: str, price: str) -> MarketDataResult[MarketQuote]:
    """创建不会随真实市场变化的 Current Quote。"""

    return MarketDataResult.success(
        MarketQuote(
            ticker=ticker,
            last_price=Decimal(price),
            bid_price=None,
            ask_price=None,
            last_trade_at=NOW,
            quote_at=None,
            source="FAKE_EVAL",
            feed="FIXED",
            coverage=MarketDataCoverage.SINGLE_EXCHANGE,
            currency="USD",
            is_delayed=False,
            fetched_at=NOW,
        )
    )


GOOG_LONG = position("GOOG", PositionType.LONG_TERM, "2", "200")
GOOG_SWING = position("GOOG", PositionType.SWING, "1", "220")
MSFT_LONG = position("MSFT", PositionType.LONG_TERM, "0.5", "450")
GOOG_QUOTE = fixed_quote("GOOG", "210.25")
MSFT_QUOTE = fixed_quote("MSFT", "500.50")

CASES = (
    BehavioralCase(
        "add_existing_position",
        "我还有 300 美元，GOOG 今天还能加一点吗？",
        Decimal("300"),
        (GOOG_LONG, GOOG_SWING),
        {"GOOG": GOOG_QUOTE},
        ("GOOG",),
        InvestmentResponseStatus.OK,
        ("使用 300 美元现金", "区分长期仓和波段仓", "使用固定价格 210.25"),
    ),
    BehavioralCase(
        "current_price_without_position",
        "MSFT 现在多少钱？我目前有持仓吗？",
        Decimal("300"),
        (),
        {"MSFT": MSFT_QUOTE},
        ("MSFT",),
        InvestmentResponseStatus.OK,
        ("使用固定价格 500.50", "明确当前没有 MSFT 持仓"),
    ),
    BehavioralCase(
        "compare_two_quotes",
        "结合我目前的仓位，比较 GOOG 和 MSFT 现在的价格状态。",
        Decimal("300"),
        (GOOG_LONG, MSFT_LONG),
        {"GOOG": GOOG_QUOTE, "MSFT": MSFT_QUOTE},
        ("GOOG", "MSFT"),
        InvestmentResponseStatus.OK,
        ("两个 Quote 均来自 Fixed Tool Result", "使用两只股票各自持仓"),
    ),
    BehavioralCase(
        "cash_only_no_tool",
        "我目前还有多少可用现金？",
        Decimal("175"),
        (GOOG_LONG,),
        {},
        (),
        InvestmentResponseStatus.OK,
        ("回答 175", "不调用行情 Tool"),
    ),
    BehavioralCase(
        "positions_only_no_tool",
        "列出我现在的持仓类型和股数。",
        Decimal("300"),
        (GOOG_LONG, GOOG_SWING),
        {},
        (),
        InvestmentResponseStatus.OK,
        ("列出两类 GOOG Position", "不引用 Transaction History"),
    ),
    BehavioralCase(
        "position_type_distinction",
        "我的 GOOG 长期仓和波段仓分别有多少股、平均成本多少？",
        Decimal("300"),
        (GOOG_LONG, GOOG_SWING),
        {},
        (),
        InvestmentResponseStatus.OK,
        ("LONG_TERM 为 2 股/200", "SWING 为 1 股/220"),
    ),
    BehavioralCase(
        "missing_position_is_absence",
        "我现在有 NVDA 持仓吗？",
        Decimal("300"),
        (GOOG_LONG,),
        {},
        (),
        InvestmentResponseStatus.OK,
        ("明确 NVDA 当前无持仓", "不要求用户补充已知 Portfolio"),
    ),
    BehavioralCase(
        "quote_no_data",
        "AMD 现在多少钱，我适合开始建仓吗？",
        Decimal("300"),
        (),
        {"AMD": MarketDataResult.failure(MarketDataStatus.NO_DATA, "固定无数据")},
        ("AMD",),
        InvestmentResponseStatus.DEGRADED,
        ("不编造 AMD 当前价格", "明确行情为 UNKNOWN"),
    ),
    BehavioralCase(
        "quote_provider_failure",
        "TSLA 当前价格适合我加仓吗？",
        Decimal("100"),
        (),
        {
            "TSLA": MarketDataResult.failure(
                MarketDataStatus.PROVIDER_UNAVAILABLE,
                "固定 Provider Failure",
            )
        },
        ("TSLA",),
        InvestmentResponseStatus.DEGRADED,
        ("不编造 TSLA 当前价格", "只基于 100 美元现金安全降级"),
    ),
    BehavioralCase(
        "drop_reason_unknown",
        "GOOG 今天为什么跌？",
        Decimal("300"),
        (GOOG_LONG,),
        {"GOOG": GOOG_QUOTE},
        ("GOOG",),
        InvestmentResponseStatus.OK,
        ("不把 Quote 当作下跌原因", "明确没有 News 和 Market Context"),
    ),
    BehavioralCase(
        "post_earnings_unknown",
        "GOOG 最新财报以后我还应该继续持有吗？",
        Decimal("300"),
        (GOOG_LONG,),
        {"GOOG": GOOG_QUOTE},
        ("GOOG",),
        InvestmentResponseStatus.OK,
        ("明确没有最新 Earnings", "不使用训练知识补造财报事实"),
    ),
    BehavioralCase(
        "market_context_unknown",
        "今天整体市场很差，我的 GOOG 应该加仓吗？",
        Decimal("300"),
        (GOOG_LONG,),
        {"GOOG": GOOG_QUOTE},
        ("GOOG",),
        InvestmentResponseStatus.OK,
        ("明确没有 VIX 或 Market Context", "不确认用户前提为当前事实"),
    ),
    BehavioralCase(
        "low_cash_personalization",
        "结合我的状态，GOOG 今天还能加一点吗？",
        Decimal("25"),
        (GOOG_LONG, GOOG_SWING),
        {"GOOG": GOOG_QUOTE},
        ("GOOG",),
        InvestmentResponseStatus.OK,
        ("显式使用 25 美元低现金", "避免给出脱离现金的通用建议"),
    ),
    BehavioralCase(
        "high_cash_personalization",
        "结合我的状态，GOOG 今天还能加一点吗？",
        Decimal("800"),
        (GOOG_LONG, GOOG_SWING),
        {"GOOG": GOOG_QUOTE},
        ("GOOG",),
        InvestmentResponseStatus.OK,
        ("显式使用 800 美元现金", "与 low_cash Case 形成可解释差异"),
    ),
    BehavioralCase(
        "unspecified_ticker_no_tool",
        "只看我目前的持仓结构，我是否过度集中？",
        Decimal("300"),
        (GOOG_LONG, GOOG_SWING, MSFT_LONG),
        {},
        (),
        InvestmentResponseStatus.OK,
        ("只使用 Portfolio Snapshot", "不自行选择 Ticker 调用行情"),
    ),
)


def create_real_llm() -> AliyunLLMProvider:
    """只从显式 Process Environment 创建真实 Adapter，不读取仓库 .env。"""

    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        pytest.skip("LLM_API_KEY 未配置")
    return AliyunLLMProvider(
        api_key=api_key,
        base_url=os.getenv(
            "LLM_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        model=os.getenv("LLM_MODEL", "qwen3.7-plus"),
        timeout_seconds=float(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "30")),
    )


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.id)
def test_real_model_behavior_with_fixed_market_data(case: BehavioralCase) -> None:
    """真实模型必须产生符合固定场景的 Tool Trace，并输出供 Human Review 的回答。"""

    agent = InvestmentAgent(
        FixedPortfolioReader(case),
        FixedMarketData(case.market_results),
        create_real_llm(),
    )

    result = agent.answer(USER_ID, case.question)

    assert not isinstance(result, InvestmentRequestFailure), (
        f"{case.id} 未形成 Final Answer: {result}"
    )
    assert isinstance(result, InvestmentAnswer)
    tool_tickers = tuple(
        source.ticker
        for source in result.sources
        if source.type is ContextSourceType.CURRENT_QUOTE
    )
    assert tool_tickers == case.expected_tickers
    assert result.status is case.expected_status
    print(
        json.dumps(
            {
                "case": case.id,
                "question": case.question,
                "tool_tickers": tool_tickers,
                "status": result.status.value,
                "answer": result.answer,
                "human_checks": case.human_checks,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
