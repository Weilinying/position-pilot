"""Structured Investment Answer 与 Current Quote Fact Resolver 测试。"""

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from position_pilot.application.investment_answer import (
    AnswerFactType,
    FactReferencePart,
    InvalidStructuredAnswer,
    StructuredInvestmentAnswer,
    TextPart,
    UnresolvedFactReference,
    parse_structured_answer,
    resolve_structured_answer,
    structured_answer_schema,
)
from position_pilot.domain.market_data import (
    MarketDataCoverage,
    MarketDataResult,
    MarketDataStatus,
    MarketQuote,
)

NOW = datetime(2026, 8, 26, 8, 0, tzinfo=UTC)


def quote(ticker: str, price: str) -> MarketDataResult[MarketQuote]:
    """创建固定成功 Current Quote。"""

    return MarketDataResult.success(
        MarketQuote(
            ticker=ticker,
            last_price=Decimal(price),
            bid_price=None,
            ask_price=None,
            last_trade_at=NOW,
            quote_at=None,
            source="ALPACA",
            feed="IEX",
            coverage=MarketDataCoverage.SINGLE_EXCHANGE,
            currency="USD",
            is_delayed=False,
            fetched_at=NOW,
        )
    )


def structured_quote_content(prefix: str, ticker: str, suffix: str = "。") -> str:
    """生成不含 authoritative price 的结构化 Quote Answer。"""

    return json.dumps(
        {
            "parts": [
                {"type": "text", "text": prefix},
                {"type": "fact_ref", "fact_type": "CURRENT_QUOTE", "ticker": ticker},
                {"type": "text", "text": suffix},
            ]
        },
        ensure_ascii=False,
    )


def test_resolves_current_quote_reference_with_authoritative_backend_value() -> None:
    """LLM 只选择 Fact，Backend 应填入 Quote Tool 的权威价格。"""

    answer = parse_structured_answer(structured_quote_content("GOOG 当前价格为 ", "GOOG"))

    resolved = resolve_structured_answer(answer, {"GOOG": quote("GOOG", "210.25")})

    assert resolved.answer == "GOOG 当前价格为 210.25 USD。"
    assert resolved.llm_text == "GOOG 当前价格为 。"
    assert resolved.referenced_current_quote_tickers == ("GOOG",)


def test_current_quote_reference_schema_does_not_allow_price() -> None:
    """Fact Reference 不需要也不允许 LLM 提供 price。"""

    content = json.dumps(
        {
            "parts": [
                {
                    "type": "fact_ref",
                    "fact_type": "CURRENT_QUOTE",
                    "ticker": "GOOG",
                    "price": "999",
                }
            ]
        }
    )

    with pytest.raises(InvalidStructuredAnswer, match="只能包含"):
        parse_structured_answer(content)

    fact_schema = structured_answer_schema()["properties"]
    assert "price" not in str(fact_schema)


def test_rejects_current_quote_reference_without_successful_tool_result() -> None:
    """Portfolio Cash 或其他 Context 不能替代缺失 Quote。"""

    answer = StructuredInvestmentAnswer((FactReferencePart(AnswerFactType.CURRENT_QUOTE, "GOOG"),))

    with pytest.raises(UnresolvedFactReference, match="GOOG"):
        resolve_structured_answer(answer, {})

    with pytest.raises(UnresolvedFactReference, match="GOOG"):
        resolve_structured_answer(
            answer,
            {
                "GOOG": MarketDataResult.failure(
                    MarketDataStatus.PROVIDER_UNAVAILABLE,
                    "固定 Provider Failure",
                )
            },
        )


def test_rejects_fact_reference_for_wrong_ticker() -> None:
    """MSFT Tool Result 不得解析 GOOG Fact Reference。"""

    answer = StructuredInvestmentAnswer((FactReferencePart(AnswerFactType.CURRENT_QUOTE, "GOOG"),))

    with pytest.raises(UnresolvedFactReference, match="GOOG"):
        resolve_structured_answer(answer, {"MSFT": quote("MSFT", "500.50")})

    with pytest.raises(UnresolvedFactReference, match="ticker 不一致"):
        resolve_structured_answer(answer, {"GOOG": quote("MSFT", "500.50")})


@pytest.mark.parametrize(
    "prefix",
    [
        "GOOG 当前价格为 ",
        "GOOG当前价格为 ",
        "GOOG 当前股价为 ",
        "GOOG current stock price: ",
        "The current price is ",
    ],
)
def test_natural_language_wording_does_not_change_quote_resolution(prefix: str) -> None:
    """TextPart 同义表达不得参与 authoritative quote grounding。"""

    answer = parse_structured_answer(structured_quote_content(prefix, "GOOG"))

    resolved = resolve_structured_answer(answer, {"GOOG": quote("GOOG", "210.25")})

    assert "210.25 USD" in resolved.answer
    assert resolved.referenced_current_quote_tickers == ("GOOG",)


def test_preserves_text_parts_without_fact_reference() -> None:
    """未迁移事实类型继续作为 LLM Text，不扩大本 Slice。"""

    answer = StructuredInvestmentAnswer((TextPart("可用现金为 300 USD。"),))

    resolved = resolve_structured_answer(answer, {})

    assert resolved.answer == "可用现金为 300 USD。"
    assert resolved.llm_text == resolved.answer
