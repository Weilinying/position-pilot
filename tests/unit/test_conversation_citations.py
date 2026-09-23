"""Conversation Citation 必须绑定本轮成功观察的来源。"""

from uuid import UUID

import pytest

from position_pilot.application.conversation_citations import (
    CitationValidationError,
    validate_citations,
)
from position_pilot.application.conversation_service import ConversationSourceInput

SOURCE_ID = UUID("80000000-0000-4000-8000-000000000001")


def _source(*, status: str = "OK", url: str | None = None) -> ConversationSourceInput:
    return ConversationSourceInput(
        source_type="RECENT_NEWS",
        provider="FIXTURE",
        source_id=SOURCE_ID,
        url=url,
        status=status,
    )


def test_inline_citation_binds_to_successful_source() -> None:
    assert validate_citations(
        f"来源报道声称这一事件。[source:{SOURCE_ID}]",
        (_source(url="https://example.com/news"),),
    ) == (SOURCE_ID,)


@pytest.mark.parametrize(
    ("answer", "sources"),
    (
        (f"失败来源不能引用。[source:{SOURCE_ID}]", (_source(status="PROVIDER_UNAVAILABLE"),)),
        ("缺少 inline Citation。", (_source(),)),
        ("伪造 URL https://other.example/news", (_source(url="https://example.com/news"),)),
        ("无效 Token [source:not-a-uuid]", (_source(),)),
    ),
)
def test_unobserved_or_unverified_citation_is_rejected(
    answer: str,
    sources: tuple[ConversationSourceInput, ...],
) -> None:
    with pytest.raises(CitationValidationError):
        validate_citations(answer, sources)


def test_no_tool_answer_needs_no_citation() -> None:
    assert validate_citations("这是对用户问题的澄清。", ()) == ()


def test_duplicate_source_ids_are_rejected() -> None:
    with pytest.raises(CitationValidationError, match="重复"):
        validate_citations(f"重复来源。[source:{SOURCE_ID}]", (_source(), _source()))


def test_explicit_url_must_belong_to_cited_source() -> None:
    other_id = UUID("80000000-0000-4000-8000-000000000002")
    other = ConversationSourceInput(
        source_type="RECENT_NEWS",
        provider="FIXTURE",
        source_id=other_id,
        url="https://other.example/article",
        status="OK",
    )

    with pytest.raises(CitationValidationError, match="显式 URL"):
        validate_citations(
            f"见 https://other.example/article [source:{SOURCE_ID}]",
            (_source(url="https://example.com/article"), other),
        )
