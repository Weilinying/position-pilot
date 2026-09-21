"""Application-owned Source Registry 验证测试。"""

import json

from position_pilot.application.investment_answer import UnresolvedSourceReference
from position_pilot.application.source_registry import (
    ContextSource,
    ContextSourceType,
    SourceValidator,
)


def _answer(source_refs: list[dict[str, str]]) -> str:
    return json.dumps({"answer": "测试回答", "source_refs": source_refs})


def test_successful_observed_source_can_be_declared() -> None:
    source = ContextSource(ContextSourceType.CURRENT_QUOTE, "OK", ticker="GOOG")

    answer, error = SourceValidator.evaluate(
        _answer([{"type": "CURRENT_QUOTE", "ticker": "GOOG"}]),
        (source,),
    )

    assert error is None
    assert answer is not None


def test_failed_source_cannot_support_a_reference() -> None:
    source = ContextSource(ContextSourceType.RECENT_NEWS, "NO_NEWS_FOUND", ticker="GOOG")

    answer, error = SourceValidator.evaluate(
        _answer([{"type": "RECENT_NEWS", "ticker": "GOOG"}]),
        (source,),
    )

    assert answer is None
    assert isinstance(error, UnresolvedSourceReference)


def test_unobserved_ticker_is_rejected() -> None:
    source = ContextSource(ContextSourceType.CURRENT_QUOTE, "OK", ticker="GOOG")

    answer, error = SourceValidator.evaluate(
        _answer([{"type": "CURRENT_QUOTE", "ticker": "MSFT"}]),
        (source,),
    )

    assert answer is None
    assert isinstance(error, UnresolvedSourceReference)


def test_selection_keeps_failed_attempts_but_omits_unused_successes() -> None:
    sources = (
        ContextSource(ContextSourceType.PORTFOLIO_SNAPSHOT, "OK"),
        ContextSource(ContextSourceType.CURRENT_QUOTE, "OK", ticker="GOOG"),
        ContextSource(ContextSourceType.RECENT_NEWS, "PROVIDER_UNAVAILABLE", ticker="GOOG"),
    )
    answer, error = SourceValidator.evaluate(
        _answer([{"type": "PORTFOLIO_SNAPSHOT"}]),
        sources,
    )

    assert error is None
    assert answer is not None
    assert SourceValidator.select_declared(answer, sources) == (sources[0], sources[2])
