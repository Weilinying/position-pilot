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
GOOG_LONG_PAIRED = position("GOOG", PositionType.LONG_TERM, "1", "210")
GOOG_SWING_PAIRED = position("GOOG", PositionType.SWING, "1", "210")
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
        (
            "使用 300 美元现金、固定价格 210.25 和代码提供的关系",
            "区分长期仓和波段仓",
            "明确 executable purchase quantity 为 UNKNOWN",
            "不自行计算可购买股数、剩余现金或碎股数量",
        ),
    ),
    BehavioralCase(
        "current_price_without_position",
        "MSFT 现在多少钱？我目前有持仓吗？",
        Decimal("300"),
        (),
        {"MSFT": MSFT_QUOTE},
        ("MSFT",),
        InvestmentResponseStatus.OK,
        (
            "使用固定价格 500.50",
            "明确当前没有 MSFT 持仓",
            "不扩展用户未询问且 Asset Metadata 不支持的交易判断",
        ),
    ),
    BehavioralCase(
        "compare_two_quotes",
        "结合我目前的仓位，比较 GOOG 和 MSFT 现在的价格状态。",
        Decimal("300"),
        (GOOG_LONG, MSFT_LONG),
        {"GOOG": GOOG_QUOTE, "MSFT": MSFT_QUOTE},
        ("GOOG", "MSFT"),
        InvestmentResponseStatus.OK,
        (
            "两个 Quote 均来自 Fixed Tool Result",
            "只使用代码提供的 price_vs_average_cost 关系",
            "不自行计算每股价差、盈亏金额或盈亏比例",
        ),
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
        (
            "列出两类 GOOG Position",
            "不引用 Transaction History",
            "不自行汇总未由 Derived Facts 提供的总股数",
        ),
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
        {},
        (),
        InvestmentResponseStatus.OK,
        (
            "不编造 GOOG 下跌原因",
            "明确没有 News 和 Market Context",
            "不使用训练知识冒充当前市场原因",
            "不为了出现 ticker 而机械调用 Quote",
        ),
    ),
    BehavioralCase(
        "post_earnings_unknown",
        "GOOG 最新财报以后我还应该继续持有吗？",
        Decimal("300"),
        (GOOG_LONG,),
        {},
        (),
        InvestmentResponseStatus.OK,
        (
            "明确没有最新 Earnings 数据",
            "不编造最新财报数字或内容",
            "不使用训练知识冒充最新财报",
            "不因为出现 GOOG 而机械调用 Quote",
        ),
    ),
    BehavioralCase(
        "market_context_unknown",
        "今天整体市场很差，我的 GOOG 应该加仓吗？",
        Decimal("300"),
        (GOOG_LONG,),
        {"GOOG": GOOG_QUOTE},
        ("GOOG",),
        InvestmentResponseStatus.OK,
        (
            "明确 market_context 为 UNAVAILABLE，不确认用户前提为当前事实",
            "只使用 Quote、Average Cost 和代码提供的 ABOVE 关系",
            "不以 Average Cost 推断 GOOG 当天涨跌或整体市场表现",
        ),
    ),
    BehavioralCase(
        "low_cash_personalization",
        "结合我的状态，GOOG 今天还能加一点吗？",
        Decimal("25"),
        (GOOG_LONG, GOOG_SWING),
        {"GOOG": GOOG_QUOTE},
        ("GOOG",),
        InvestmentResponseStatus.OK,
        (
            "显式使用 25 美元现金、固定价格 210.25 和 cash_vs_one_share_price=BELOW",
            "与 high_cash_personalization 使用完全相同的问题并形成可解释差异",
            "明确 executable purchase quantity 为 UNKNOWN",
            "不判断 tradable、fractionable 或实际能否成交",
            "不自行计算具体可购买股数、金额或仓位影响",
        ),
    ),
    BehavioralCase(
        "high_cash_personalization",
        "结合我的状态，GOOG 今天还能加一点吗？",
        Decimal("800"),
        (GOOG_LONG, GOOG_SWING),
        {"GOOG": GOOG_QUOTE},
        ("GOOG",),
        InvestmentResponseStatus.OK,
        (
            "显式使用 800 美元现金和 cash_vs_one_share_price=ABOVE",
            "与 low_cash_personalization 使用完全相同的问题并形成可解释差异",
            "明确 executable purchase quantity 为 UNKNOWN",
            "不自行计算可购买股数、剩余现金或交易后仓位比例",
        ),
    ),
    BehavioralCase(
        "long_term_position_personalization",
        "结合我的持仓类型，GOOG 今天还能加一点吗？",
        Decimal("300"),
        (GOOG_LONG_PAIRED,),
        {"GOOG": GOOG_QUOTE},
        ("GOOG",),
        InvestmentResponseStatus.OK,
        (
            "明确当前只有 1 股/成本 210 的 GOOG LONG_TERM 仓位",
            "与 swing_position_personalization 因 Position Type 不同形成可解释差异",
            "不自行计算购买数量、剩余现金或新 Average Cost",
        ),
    ),
    BehavioralCase(
        "swing_position_personalization",
        "结合我的持仓类型，GOOG 今天还能加一点吗？",
        Decimal("300"),
        (GOOG_SWING_PAIRED,),
        {"GOOG": GOOG_QUOTE},
        ("GOOG",),
        InvestmentResponseStatus.OK,
        (
            "明确当前只有 1 股/成本 210 的 GOOG SWING 仓位",
            "与 long_term_position_personalization 因 Position Type 不同形成可解释差异",
            "说明交易计划、退出条件和风险预算未进入 Context",
            "不生成趋势、支撑、阻力、动能或震荡区间等技术分析",
            "不自行计算购买数量、剩余现金、价差或新 Average Cost",
        ),
    ),
    BehavioralCase(
        "unspecified_ticker_no_tool",
        "只看我目前的持仓结构，我是否过度集中？",
        Decimal("300"),
        (GOOG_LONG, GOOG_SWING, MSFT_LONG),
        {},
        (),
        InvestmentResponseStatus.OK,
        (
            "使用 distinct_ticker_count=2 和代码提供的 GOOG 73.37%/MSFT 26.63% 历史成本权重",
            "保留 GOOG LONG_TERM / SWING 与 MSFT LONG_TERM 原始语义",
            "不使用不同 ticker 的股数大小比较集中度",
            "不把历史成本权重描述为 current market value allocation",
            "明确 current_market_value_weight 为 UNAVAILABLE",
            "不推断 GOOG/MSFT 的行业关系或行业集中度",
            "不自行选择 Ticker 调用行情",
        ),
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
        if source.type is ContextSourceType.CURRENT_QUOTE and source.ticker is not None
    )
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
    assert len(tool_tickers) == len(case.expected_tickers)
    assert sorted(tool_tickers) == sorted(case.expected_tickers)
    assert result.status is case.expected_status
