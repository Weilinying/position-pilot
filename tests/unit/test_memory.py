"""只读 Memory Retrieval Port 的最小边界测试。"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from position_pilot.application.memory import (
    MemoryHit,
    MemoryRetrievalContext,
    NoOpMemoryReader,
    filter_memory_hits,
)

ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER_ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000002")
AS_OF = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)


def memory(
    *,
    owner: UUID = ACCOUNT_ID,
    scope: str = "GOOG:LONG_TERM",
    confirmed: bool = True,
    effective_at: datetime = AS_OF - timedelta(days=1),
    expires_at: datetime | None = AS_OF + timedelta(days=1),
) -> MemoryHit:
    """创建一个只用于过滤边界的 Memory Fixture。"""

    return MemoryHit(
        owner=owner,
        scope=scope,
        content="用户希望长期持有，但每轮仍需结合最新事实重新分析。",
        source="user-confirmed-memory",
        confirmed=confirmed,
        effective_at=effective_at,
        expires_at=expires_at,
    )


def test_no_op_reader_returns_empty_without_persistence() -> None:
    """Production 默认未接入 Memory Service 时保持空结果。"""

    context = MemoryRetrievalContext(scope="GOOG:LONG_TERM", as_of=AS_OF)

    assert NoOpMemoryReader().retrieve(ACCOUNT_ID, context) == ()


def test_filter_memory_hits_keeps_only_owned_confirmed_active_scope() -> None:
    """Owner、Scope、确认状态与 effective/expiry 均在 Runtime 前过滤。"""

    active = memory()
    selected = filter_memory_hits(
        (
            active,
            memory(owner=OTHER_ACCOUNT_ID),
            memory(scope="MSFT:LONG_TERM"),
            memory(confirmed=False),
            memory(effective_at=AS_OF + timedelta(minutes=1)),
            memory(expires_at=AS_OF),
        ),
        account_id=ACCOUNT_ID,
        retrieval_context=MemoryRetrievalContext(scope="GOOG:LONG_TERM", as_of=AS_OF),
    )

    assert selected == (active,)
    assert selected[0].as_dict()["authority"] == "NON_AUTHORITATIVE_MEMORY_CONTEXT"


def test_filter_memory_hits_applies_explicit_limit() -> None:
    """Memory Context 只保留检索请求声明的有界结果。"""

    first = memory()
    second = memory(effective_at=AS_OF - timedelta(hours=1))

    selected = filter_memory_hits(
        (first, second),
        account_id=ACCOUNT_ID,
        retrieval_context=MemoryRetrievalContext(scope="GOOG:LONG_TERM", as_of=AS_OF, limit=1),
    )

    assert selected == (first,)


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (
            lambda: MemoryRetrievalContext(scope="", as_of=AS_OF),
            "Memory scope 不能为空",
        ),
        (
            lambda: MemoryRetrievalContext(scope="GOOG:LONG_TERM", as_of=datetime(2026, 9, 21)),
            "Memory as_of 必须包含时区",
        ),
        (
            lambda: MemoryRetrievalContext(scope="GOOG:LONG_TERM", as_of=AS_OF, limit=0),
            "Memory limit 必须为正整数",
        ),
    ],
)
def test_retrieval_context_validates_minimum_query_boundary(factory: object, message: str) -> None:
    """检索时间与结果边界必须明确。"""

    with pytest.raises(ValueError, match=message):
        factory()  # type: ignore[operator]


def test_memory_hit_rejects_naive_effective_timestamp() -> None:
    """Memory 有效期不能依赖运行环境的本地时区。"""

    with pytest.raises(ValueError, match="Memory effective_at 必须包含时区"):
        memory(effective_at=datetime(2026, 9, 21))
