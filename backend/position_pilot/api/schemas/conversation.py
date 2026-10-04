"""Conversation Thread、Message 与 Answer V2 的 Public API Schema。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from position_pilot.application.conversation_service import (
    ConversationMessage,
    ConversationMessageRole,
    ConversationSource,
    ConversationThread,
    ConversationThreadPage,
    ConversationThreadSnapshot,
    ConversationTurn,
    ConversationTurnStatus,
)
from position_pilot.domain.strategy import StrategyCandidate


class ConversationThreadStartRequest(BaseModel):
    """创建 Thread 的可选标题。"""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=200)


class ConversationAskRequest(BaseModel):
    """提交 Conversation Message 所需的幂等与并发字段。"""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=4_000)
    client_request_id: UUID
    expected_thread_revision: int = Field(ge=0)


class ConversationThreadResponse(BaseModel):
    """不暴露 Account Owner 的 Thread Metadata。"""

    id: UUID
    title: str | None
    revision: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    @classmethod
    def from_domain(cls, thread: ConversationThread) -> "ConversationThreadResponse":
        """将 Application Thread DTO 映射为 Public Response。"""

        return cls(
            id=thread.id,
            title=thread.title,
            revision=thread.revision,
            created_at=thread.created_at,
            updated_at=thread.updated_at,
            deleted_at=thread.deleted_at,
        )


class ConversationThreadListResponse(BaseModel):
    """Thread 列表与下一页 Cursor。"""

    items: tuple[ConversationThreadResponse, ...]
    next_cursor: str | None

    @classmethod
    def from_domain(cls, page: ConversationThreadPage) -> "ConversationThreadListResponse":
        return cls(
            items=tuple(ConversationThreadResponse.from_domain(item) for item in page.items),
            next_cursor=page.next_cursor,
        )


class ConversationTurnResponse(BaseModel):
    """Turn 的可观察状态，不暴露内部 Account Owner。"""

    id: UUID
    client_request_id: UUID
    status: ConversationTurnStatus
    failure_code: str | None
    run_deadline_at: datetime | None
    created_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_domain(cls, turn: ConversationTurn | None) -> "ConversationTurnResponse | None":
        if turn is None:
            return None
        return cls(
            id=turn.id,
            client_request_id=turn.client_request_id,
            status=turn.status,
            failure_code=turn.failure_code,
            run_deadline_at=turn.run_deadline_at,
            created_at=turn.created_at,
            completed_at=turn.completed_at,
        )


class ConversationMessageResponse(BaseModel):
    """用户可见的 append-only Message。"""

    id: UUID
    thread_id: UUID
    turn_id: UUID
    sequence: int
    role: ConversationMessageRole
    content: str
    created_at: datetime

    @classmethod
    def from_domain(cls, message: ConversationMessage) -> "ConversationMessageResponse":
        return cls(
            id=message.id,
            thread_id=message.thread_id,
            turn_id=message.turn_id,
            sequence=message.sequence,
            role=message.role,
            content=message.content,
            created_at=message.created_at,
        )


class ConversationSourceResponse(BaseModel):
    """仅映射本轮 Agent 实际返回并持久化的 Source Metadata。"""

    source_id: UUID
    source_type: str
    provider: str
    provider_reference: str | None
    url: str | None
    title: str | None
    publisher: str | None
    published_at: datetime | None
    event_time: datetime | None
    fetched_at: datetime | None
    content_scope: str
    status: str

    @classmethod
    def from_domain(cls, source: ConversationSource) -> "ConversationSourceResponse":
        return cls(
            source_id=source.source_id,
            source_type=source.source_type,
            provider=source.provider,
            provider_reference=source.provider_reference,
            url=source.url,
            title=source.title,
            publisher=source.publisher,
            published_at=source.published_at,
            event_time=source.event_time,
            fetched_at=source.fetched_at,
            content_scope=source.content_scope,
            status=source.status,
        )


class CitationV2(BaseModel):
    """T4A Citation Contract 的占位 Schema；T3 不生成 Citation。"""

    source_id: UUID
    locator: str | None = None


class AnswerV2(BaseModel):
    """Conversation Answer 的最小稳定封装。"""

    text: str | None
    warnings: tuple[str, ...]
    sources: tuple[ConversationSourceResponse, ...]
    citations: tuple[CitationV2, ...]
    candidate: StrategyCandidate | None = None


class ConversationThreadSnapshotResponse(BaseModel):
    """Thread Metadata、当前 RUNNING Turn 与最近 Turn。"""

    thread: ConversationThreadResponse
    active_turn: ConversationTurnResponse | None
    last_turn: ConversationTurnResponse | None

    @classmethod
    def from_domain(
        cls,
        snapshot: ConversationThreadSnapshot,
    ) -> "ConversationThreadSnapshotResponse":
        return cls(
            thread=ConversationThreadResponse.from_domain(snapshot.thread),
            active_turn=ConversationTurnResponse.from_domain(snapshot.active_turn),
            last_turn=ConversationTurnResponse.from_domain(snapshot.last_turn),
        )


class ConversationHistoryResponse(BaseModel):
    """有界 Message 分页及提交下一轮所需的 Thread 状态。"""

    thread: ConversationThreadResponse
    messages: tuple[ConversationMessageResponse, ...]
    active_turn: ConversationTurnResponse | None
    next_cursor: str | None
    answers: dict[UUID, AnswerV2] = Field(default_factory=dict)


class ConversationAskResponse(BaseModel):
    """POST Message 的 Turn、Message 与最小 Answer V2。"""

    thread: ConversationThreadResponse
    turn: ConversationTurnResponse
    user_message: ConversationMessageResponse
    assistant_message: ConversationMessageResponse | None
    answer: AnswerV2 | None
