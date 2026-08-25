"""M3 Final Response Grounding Guard 的确定性测试。"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from position_pilot.application.investment_context import PortfolioSnapshot
from position_pilot.application.investment_response_guard import (
    GroundingViolationCode,
    validate_final_response,
)
from position_pilot.domain.market_data import (
    MarketDataCoverage,
    MarketDataResult,
    MarketQuote,
)
from position_pilot.domain.portfolio import (
    CashBalance,
    PortfolioState,
    Position,
    PositionType,
)

USER_ID = UUID("00000000-0000-0000-0000-000000000201")
NOW = datetime(2026, 8, 24, 8, 0, tzinfo=UTC)


def snapshot() -> PortfolioSnapshot:
    """创建包含两类 GOOG Position 的完整 Snapshot。"""

    return PortfolioSnapshot.from_state(
        PortfolioState(
            user_id=USER_ID,
            cash=CashBalance(USER_ID, Decimal("1000"), Decimal("300")),
            positions=(
                Position(
                    ticker="GOOG",
                    position_type=PositionType.LONG_TERM,
                    shares=Decimal("2"),
                    cost_basis=Decimal("400"),
                    average_cost=Decimal("200"),
                ),
                Position(
                    ticker="GOOG",
                    position_type=PositionType.SWING,
                    shares=Decimal("1"),
                    cost_basis=Decimal("220"),
                    average_cost=Decimal("220"),
                ),
            ),
            transaction_count=0,
        )
    )


def quote(ticker: str, price: str) -> MarketDataResult[MarketQuote]:
    """创建固定成功 Quote。"""

    return MarketDataResult.success(
        MarketQuote(
            ticker=ticker,
            last_price=Decimal(price),
            bid_price=None,
            ask_price=None,
            last_trade_at=NOW,
            quote_at=None,
            source="FAKE_GUARD",
            feed="FIXED",
            coverage=MarketDataCoverage.SINGLE_EXCHANGE,
            currency="USD",
            is_delayed=False,
            fetched_at=NOW,
        )
    )


def violation_codes(answer: str) -> set[GroundingViolationCode]:
    """返回固定 GOOG Quote 场景的 Guard Code。"""

    return {
        violation.code
        for violation in validate_final_response(
            answer,
            snapshot(),
            {"GOOG": quote("GOOG", "210.25")},
        )
    }


def test_accepts_only_provided_numbers_relations_and_unknown_execution() -> None:
    """已提供事实的原样解释不得被 Guard 误拒绝。"""

    answer = (
        "GOOG 当前价格为 210.25 USD，可用现金为 300 USD。"
        "现金数值高于单股报价。"
        "LONG_TERM 当前价格高于平均成本 200，SWING 当前价格低于平均成本 220。"
        "实际可执行购买数量为 UNKNOWN。"
    )

    assert violation_codes(answer) == set()


def test_rejects_financial_numbers_not_present_in_context() -> None:
    """价差、剩余现金和外部阈值都属于未提供的新金融数值。"""

    codes = violation_codes("每股盈利 0.25 美元，剩余现金 $89.75，常见阈值为 20%-25%。")

    assert GroundingViolationCode.UNSUPPORTED_FINANCIAL_NUMBER in codes


def test_rejects_buying_power_claim_even_when_answer_also_says_unknown() -> None:
    """同时复述 UNKNOWN 不能抵消明确的购买能力结论。"""

    codes = violation_codes(
        "现金足够覆盖至少一股 GOOG，但 executable_purchase_quantity 为 UNKNOWN。"
    )

    assert GroundingViolationCode.BUYING_POWER_CLAIM in codes


def test_rejects_explicitly_inverted_cash_quote_relation() -> None:
    """只对模型显式复述且与代码相反的关系值进行阻断。"""

    codes = violation_codes("GOOG 的 cash_vs_one_share_price.relation=BELOW。")

    assert GroundingViolationCode.CASH_QUOTE_RELATION_CONTRADICTION in codes


def test_accepts_correct_named_cash_quote_relation_without_field_name_confusion() -> None:
    """字段名中的 price 不得与其后的 Relation 值形成伪关系。"""

    codes = violation_codes("GOOG 的 cash_vs_one_share_price 关系为 ABOVE，现金数值高于单股报价。")

    assert GroundingViolationCode.CASH_QUOTE_RELATION_CONTRADICTION not in codes


def test_does_not_mix_price_cost_relation_with_later_cash_quote_relation() -> None:
    """同一句同时出现两类关系时不得跨语义拼接操作数。"""

    codes = violation_codes(
        "GOOG 当前价格 210.25 高于平均成本 200，且可用现金与单股价格的数值关系为 ABOVE。"
    )

    assert GroundingViolationCode.CASH_QUOTE_RELATION_CONTRADICTION not in codes


def test_rejects_explicitly_inverted_price_average_cost_relation_by_position_type() -> None:
    """保留 Position Type 后检查显式结构化 Quote/Average Cost 关系值。"""

    codes = violation_codes(
        "GOOG LONG_TERM price_vs_average_cost=BELOW。GOOG SWING price_vs_average_cost=ABOVE。"
    )

    assert GroundingViolationCode.PRICE_COST_RELATION_CONTRADICTION in codes


def test_does_not_block_cross_ticker_natural_language_comparison() -> None:
    """跨 Ticker 自然语言比较由 Behavioral Review 检查，不作为生产强阻断。"""

    violations = validate_final_response(
        "就绝对价格而言，MSFT 当前报价高于 GOOG。",
        snapshot(),
        {
            "GOOG": quote("GOOG", "210.25"),
            "MSFT": quote("MSFT", "500.50"),
        },
    )

    assert violations == ()


def test_does_not_block_qualitative_relation_magnitude() -> None:
    """关系幅度属于模糊语义，由 Behavioral Review 检查而不触发 Repair。"""

    violations = validate_final_response(
        "GOOG 当前价格略高于 SWING 平均成本，处于微利状态。",
        snapshot(),
        {"GOOG": quote("GOOG", "210.25")},
    )

    assert violations == ()


def test_does_not_parse_free_form_relation_prose_as_blocking_contract() -> None:
    """自然语言操作数可能含混，Guard 不对其进行推断。"""

    codes = violation_codes("GOOG 当前价格高于平均成本，现金关系为 ABOVE。")

    assert codes == set()


def test_does_not_guess_relation_owner_in_ambiguous_multi_ticker_sentence() -> None:
    """同句包含多个 Ticker 时，关系值归属不足以用于生产阻断。"""

    violations = validate_final_response(
        "GOOG 与 MSFT 的 cash_vs_one_share_price.relation 分别为 BELOW 和 ABOVE。",
        snapshot(),
        {
            "GOOG": quote("GOOG", "210.25"),
            "MSFT": quote("MSFT", "500.50"),
        },
    )

    assert violations == ()


def test_accepts_grounded_quote_timestamp_components() -> None:
    """Tool 提供的 ISO 时间戳不属于未提供的金融计算。"""

    codes = violation_codes("GOOG 报价时间为 2026-08-24T08:00:00Z。")

    assert codes == set()


def test_does_not_treat_list_ordinals_as_new_financial_numbers() -> None:
    """回答结构编号不是金融计算结果。"""

    answer = "1. 当前价格为 210.25 USD。\n2. 实际可执行购买数量为 UNKNOWN。"

    assert violation_codes(answer) == set()
