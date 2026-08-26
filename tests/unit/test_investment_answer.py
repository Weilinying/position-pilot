"""Free-form Investment Answer 与 Structured Source References 测试。"""

import json

import pytest

from position_pilot.application.investment_answer import (
    InvalidStructuredAnswer,
    SourceReference,
    SourceReferenceType,
    StructuredInvestmentAnswer,
    UnresolvedSourceReference,
    parse_structured_answer,
    structured_answer_schema,
    validate_source_references,
)


def source(reference_type: SourceReferenceType, ticker: str | None = None) -> SourceReference:
    """创建固定 Source Reference。"""

    return SourceReference(reference_type, ticker)


def structured_content(answer: str, source_refs: list[dict[str, str]]) -> str:
    """创建 LLM Final Completion JSON。"""

    return json.dumps(
        {"answer": answer, "source_refs": source_refs},
        ensure_ascii=False,
    )


def test_accepts_free_form_answer_with_valid_current_quote_source() -> None:
    """Backend 只验证 GOOG Quote Source 存在，不重写 answer 的价格文本。"""

    content = structured_content(
        "GOOG 当前约为 210.25 美元，结合你的持仓成本来看……",
        [
            {"type": "CURRENT_QUOTE", "ticker": "GOOG"},
            {"type": "PORTFOLIO_SNAPSHOT"},
        ],
    )
    answer = parse_structured_answer(content)

    validate_source_references(
        answer,
        (
            source(SourceReferenceType.PORTFOLIO_SNAPSHOT),
            source(SourceReferenceType.CURRENT_QUOTE, "GOOG"),
        ),
    )

    assert answer.answer == "GOOG 当前约为 210.25 美元，结合你的持仓成本来看……"
    assert answer.source_refs[0].ticker == "GOOG"


def test_rejects_current_quote_source_without_successful_context() -> None:
    """Portfolio Cash 不能支撑未取得的 GOOG Current Quote Source。"""

    answer = StructuredInvestmentAnswer(
        answer="GOOG 当前价格为 300 美元。",
        source_refs=(source(SourceReferenceType.CURRENT_QUOTE, "GOOG"),),
    )

    with pytest.raises(UnresolvedSourceReference, match="CURRENT_QUOTE\\(GOOG\\)"):
        validate_source_references(
            answer,
            (source(SourceReferenceType.PORTFOLIO_SNAPSHOT),),
        )


def test_rejects_current_quote_source_for_wrong_ticker() -> None:
    """MSFT Quote Context 不得支撑 GOOG Source Reference。"""

    answer = StructuredInvestmentAnswer(
        answer="GOOG 当前价格为 500.50 美元。",
        source_refs=(source(SourceReferenceType.CURRENT_QUOTE, "GOOG"),),
    )

    with pytest.raises(UnresolvedSourceReference, match="GOOG"):
        validate_source_references(
            answer,
            (source(SourceReferenceType.CURRENT_QUOTE, "MSFT"),),
        )


@pytest.mark.parametrize(
    "answer_text",
    [
        "GOOG 当前价格为 210.25 美元。",
        "GOOG当前价格为 210.25 美元。",
        "GOOG 当前股价为 210.25 美元。",
        "GOOG current stock price is 210.25 USD.",
        "The current price is 210.25 USD.",
    ],
)
def test_natural_language_wording_does_not_affect_source_validation(
    answer_text: str,
) -> None:
    """自然语言表达与数字不进入 Backend Source Validation。"""

    answer = StructuredInvestmentAnswer(
        answer=answer_text,
        source_refs=(source(SourceReferenceType.CURRENT_QUOTE, "GOOG"),),
    )

    validate_source_references(
        answer,
        (source(SourceReferenceType.CURRENT_QUOTE, "GOOG"),),
    )

    assert answer.answer == answer_text


def test_unifies_all_context_source_references() -> None:
    """Portfolio、Ticker Context 与 Market Context 复用同一 Source Contract。"""

    answer = parse_structured_answer(
        structured_content(
            "结合持仓、近期路径与报道分析。",
            [
                {"type": "PORTFOLIO_SNAPSHOT"},
                {"type": "PRICE_HISTORY", "ticker": "goog"},
                {"type": "RECENT_NEWS", "ticker": "GOOG"},
                {"type": "MARKET_CONTEXT", "ticker": "SPY"},
            ],
        )
    )
    available = (
        source(SourceReferenceType.PORTFOLIO_SNAPSHOT),
        source(SourceReferenceType.PRICE_HISTORY, "GOOG"),
        source(SourceReferenceType.RECENT_NEWS, "GOOG"),
        source(SourceReferenceType.MARKET_CONTEXT, "SPY"),
    )

    validate_source_references(answer, available)

    assert answer.source_refs == available


def test_rejects_invalid_or_duplicate_source_references() -> None:
    """Source 外层 Contract 保持严格，不允许错误字段或重复身份。"""

    with pytest.raises(InvalidStructuredAnswer, match="只能包含 type"):
        parse_structured_answer(
            structured_content(
                "回答",
                [{"type": "PORTFOLIO_SNAPSHOT", "ticker": "GOOG"}],
            )
        )

    with pytest.raises(InvalidStructuredAnswer, match="不得重复"):
        parse_structured_answer(
            structured_content(
                "回答",
                [
                    {"type": "CURRENT_QUOTE", "ticker": "GOOG"},
                    {"type": "CURRENT_QUOTE", "ticker": "goog"},
                ],
            )
        )


def test_schema_exposes_answer_and_source_refs_without_fact_value_fields() -> None:
    """Schema 只结构化 Answer 外壳与来源身份，不定义金融事实值。"""

    schema = structured_answer_schema()

    assert schema["required"] == ["answer", "source_refs"]
    assert schema["additionalProperties"] is False
    assert "price" not in str(schema)
    properties = schema["properties"]
    assert isinstance(properties, dict)
    assert "parts" not in properties
