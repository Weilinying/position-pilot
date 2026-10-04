"""Application-owned 的只读 Memory Retrieval Boundary。

Phase 4 只保留检索接口，不在此模块实现 Memory 持久化、写入、Embedding 或向量检索。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class MemoryRetrievalContext:
    """一次 Memory 检索的非权威范围与时间快照。"""

    scope: str | None
    as_of: datetime
    limit: int = 5

    def __post_init__(self) -> None:
        if self.scope is not None and not self.scope.strip():
            raise ValueError("Memory scope 不能为空")
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("Memory as_of 必须包含时区")
        if isinstance(self.limit, bool) or self.limit <= 0:
            raise ValueError("Memory limit 必须为正整数")


@dataclass(frozen=True, slots=True)
class MemoryHit:
    """一条已确认的 Application-owned Memory 检索结果。

    Memory 是解释性背景，不是 Portfolio、Ledger、Persistent User Intent 或当前用户指令的事实源。
    """

    owner: UUID
    scope: str
    content: str
    source: str
    confirmed: bool
    effective_at: datetime
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.scope.strip():
            raise ValueError("Memory scope 不能为空")
        if not self.content.strip():
            raise ValueError("Memory content 不能为空")
        if not self.source.strip():
            raise ValueError("Memory source 不能为空")
        if not isinstance(self.confirmed, bool):
            raise ValueError("Memory confirmed 必须是布尔值")
        self._validate_timestamp(self.effective_at, "effective_at")
        if self.expires_at is not None:
            self._validate_timestamp(self.expires_at, "expires_at")

    @staticmethod
    def _validate_timestamp(value: datetime, field_name: str) -> None:
        """拒绝无时区时间，避免检索有效期发生隐式本地时区比较。"""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"Memory {field_name} 必须包含时区")

    def as_dict(self) -> dict[str, object]:
        """将 Memory 映射为只读 Context 背景，保留来源与有效期元数据。"""

        return {
            "owner": str(self.owner),
            "scope": self.scope,
            "content": self.content,
            "source": self.source,
            "confirmed": self.confirmed,
            "effective_at": self.effective_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at is not None else None,
            "authority": "NON_AUTHORITATIVE_MEMORY_CONTEXT",
        }


class MemoryReader(Protocol):
    """Application-owned 的只读 Memory Retrieval Port。"""

    def retrieve(
        self,
        account_id: UUID,
        retrieval_context: MemoryRetrievalContext,
    ) -> tuple[MemoryHit, ...]:
        """返回当前 Account 与检索范围内可作为背景的 Memory 命中。"""


class NoOpMemoryReader:
    """Phase 4 Production 默认实现：未配置 Memory Service 时不返回命中。"""

    def retrieve(
        self,
        account_id: UUID,
        retrieval_context: MemoryRetrievalContext,
    ) -> tuple[MemoryHit, ...]:
        """保持显式只读空结果，不创建或读取任何持久化状态。"""

        del account_id, retrieval_context
        return ()


def filter_memory_hits(
    hits: tuple[MemoryHit, ...],
    *,
    account_id: UUID,
    retrieval_context: MemoryRetrievalContext,
) -> tuple[MemoryHit, ...]:
    """在进入 Runtime 前应用 Memory 的最小安全过滤边界。

    只有同一 Account、请求 Scope、已确认且在 `as_of` 时刻生效的命中可以作为背景；过期命中不返回。
    `scope=None` 表示由上层已确定的检索范围，允许适配器在多个已授权 Scope 中筛选。
    """

    selected = tuple(
        hit
        for hit in hits
        if hit.owner == account_id
        and (retrieval_context.scope is None or hit.scope == retrieval_context.scope)
        and hit.confirmed
        and hit.effective_at <= retrieval_context.as_of
        and (hit.expires_at is None or retrieval_context.as_of < hit.expires_at)
    )
    return selected[: retrieval_context.limit]
