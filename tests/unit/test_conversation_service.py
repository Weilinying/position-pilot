"""Conversation Service 的 Owner、并发、幂等与有界历史测试。"""

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Self
from uuid import UUID, uuid4

import pytest

from position_pilot.application.conversation_service import (
    MAX_HISTORY_SERIALIZED_CHARS,
    ConversationAgentResult,
    ConversationHistoryMessage,
    ConversationIdempotencyConflict,
    ConversationMessage,
    ConversationMessagePage,
    ConversationMessageRole,
    ConversationRevisionConflict,
    ConversationRunExpired,
    ConversationService,
    ConversationSource,
    ConversationSourceInput,
    ConversationThread,
    ConversationThreadNotFound,
    ConversationThreadPage,
    ConversationTurn,
    ConversationTurnInProgress,
    ConversationTurnStatus,
)

NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER_ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000002")
PORTFOLIO_USER_ID = UUID("10000000-0000-0000-0000-000000000001")


@dataclass(slots=True)
class FakeConversationStore:
    threads: dict[UUID, ConversationThread] = field(default_factory=dict)
    turns: dict[UUID, ConversationTurn] = field(default_factory=dict)
    messages: dict[UUID, ConversationMessage] = field(default_factory=dict)
    sources: dict[UUID, ConversationSource] = field(default_factory=dict)
    commit_count: int = 0
    in_transaction: bool = False


class FakeConversationUnitOfWork:
    """直接映射 Store 的同步 Conversation UoW。"""

    def __init__(self, store: FakeConversationStore) -> None:
        self.store = store

    def __enter__(self) -> Self:
        self.store.in_transaction = True
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exception_type, exception, traceback
        self.store.in_transaction = False

    def get_thread(
        self,
        account_id: UUID,
        thread_id: UUID,
        *,
        for_update: bool = False,
    ) -> ConversationThread | None:
        del for_update
        thread = self.store.threads.get(thread_id)
        return thread if thread is not None and thread.account_id == account_id else None

    def add_thread(self, thread: ConversationThread) -> None:
        self.store.threads[thread.id] = thread

    def update_thread(self, thread: ConversationThread) -> None:
        self.store.threads[thread.id] = thread

    def list_threads(
        self,
        account_id: UUID,
        *,
        cursor: str | None,
        limit: int,
    ) -> ConversationThreadPage:
        del cursor
        items = tuple(
            sorted(
                (
                    thread
                    for thread in self.store.threads.values()
                    if thread.account_id == account_id and thread.deleted_at is None
                ),
                key=lambda thread: thread.updated_at,
                reverse=True,
            )[:limit]
        )
        return ConversationThreadPage(items, None)

    def get_turn_by_client_request_id(
        self,
        account_id: UUID,
        thread_id: UUID,
        client_request_id: UUID,
        *,
        for_update: bool = False,
    ) -> ConversationTurn | None:
        del for_update
        return next(
            (
                turn
                for turn in self.store.turns.values()
                if turn.account_id == account_id
                and turn.thread_id == thread_id
                and turn.client_request_id == client_request_id
            ),
            None,
        )

    def get_turn(
        self,
        account_id: UUID,
        thread_id: UUID,
        turn_id: UUID,
        *,
        for_update: bool = False,
    ) -> ConversationTurn | None:
        del for_update
        turn = self.store.turns.get(turn_id)
        return (
            turn
            if turn is not None and turn.account_id == account_id and turn.thread_id == thread_id
            else None
        )

    def get_running_turn(
        self,
        account_id: UUID,
        thread_id: UUID,
        *,
        for_update: bool = False,
    ) -> ConversationTurn | None:
        del for_update
        return next(
            (
                turn
                for turn in self.store.turns.values()
                if turn.account_id == account_id
                and turn.thread_id == thread_id
                and turn.status is ConversationTurnStatus.RUNNING
            ),
            None,
        )

    def get_last_turn(self, account_id: UUID, thread_id: UUID) -> ConversationTurn | None:
        turns = [
            turn
            for turn in self.store.turns.values()
            if turn.account_id == account_id and turn.thread_id == thread_id
        ]
        return max(turns, key=lambda turn: turn.created_at, default=None)

    def get_user_message_for_turn(
        self,
        account_id: UUID,
        thread_id: UUID,
        turn_id: UUID,
    ) -> ConversationMessage | None:
        return next(
            (
                message
                for message in self.store.messages.values()
                if message.account_id == account_id
                and message.thread_id == thread_id
                and message.turn_id == turn_id
                and message.role is ConversationMessageRole.USER
            ),
            None,
        )

    def get_assistant_message_for_turn(
        self,
        account_id: UUID,
        thread_id: UUID,
        turn_id: UUID,
    ) -> ConversationMessage | None:
        return next(
            (
                message
                for message in self.store.messages.values()
                if message.account_id == account_id
                and message.thread_id == thread_id
                and message.turn_id == turn_id
                and message.role is ConversationMessageRole.ASSISTANT
            ),
            None,
        )

    def add_turn(self, turn: ConversationTurn) -> None:
        self.store.turns[turn.id] = turn

    def update_turn(self, turn: ConversationTurn) -> None:
        self.store.turns[turn.id] = turn

    def add_message(self, message: ConversationMessage) -> None:
        self.store.messages[message.id] = message

    def add_sources(self, sources: Sequence[ConversationSource]) -> None:
        self.store.sources.update({source.source_id: source for source in sources})

    def list_sources_for_message(
        self,
        account_id: UUID,
        thread_id: UUID,
        assistant_message_id: UUID,
    ) -> tuple[ConversationSource, ...]:
        del account_id, thread_id
        return tuple(
            source
            for source in self.store.sources.values()
            if source.assistant_message_id == assistant_message_id
        )

    def list_messages(
        self,
        account_id: UUID,
        thread_id: UUID,
        *,
        before_sequence: int | None,
        limit: int,
    ) -> ConversationMessagePage:
        messages = [
            message
            for message in self.store.messages.values()
            if message.account_id == account_id
            and message.thread_id == thread_id
            and (before_sequence is None or message.sequence < before_sequence)
        ]
        return ConversationMessagePage(
            tuple(sorted(messages, key=lambda message: message.sequence)[-limit:]),
            None,
        )

    def commit(self) -> None:
        self.store.commit_count += 1


def make_service(
    store: FakeConversationStore,
    *,
    agent: object | None = None,
    clock: Callable[[], datetime] | None = None,
    run_timeout: timedelta = timedelta(seconds=30),
) -> ConversationService:
    """创建测试用 Conversation Service。"""

    return ConversationService(
        lambda: FakeConversationUnitOfWork(store),
        agent=agent,  # type: ignore[arg-type]
        clock=clock or (lambda: NOW),
        run_timeout=run_timeout,
    )


class RecordingAgent:
    """记录调用参数并返回固定 Answer。"""

    def __init__(
        self,
        store: FakeConversationStore,
        *,
        answer: str = "已结合当前事实分析。",
        warnings: tuple[str, ...] = (),
        source_url: str | None = None,
        source_id: UUID | None = None,
    ) -> None:
        self.store = store
        self.answer_text = answer
        self.warnings = warnings
        self.source_url = source_url
        self.source_id = source_id
        self.calls: list[tuple[UUID, UUID, str, tuple[ConversationHistoryMessage, ...]]] = []

    def answer(
        self,
        *,
        account_id: UUID,
        portfolio_user_id: UUID,
        question: str,
        history: tuple[ConversationHistoryMessage, ...],
    ) -> ConversationAgentResult:
        assert self.store.in_transaction is False
        self.calls.append((account_id, portfolio_user_id, question, history))
        return ConversationAgentResult(
            answer=self.answer_text,
            sources=(
                ConversationSourceInput(
                    source_type="CURRENT_QUOTE",
                    provider="fixture",
                    provider_reference="GOOG:quote",
                    url=self.source_url,
                    source_id=self.source_id,
                ),
            ),
            warnings=self.warnings,
        )


def test_start_turn_commits_before_agent_and_passes_bounded_history() -> None:
    """Agent 收到 portfolio_user_id 与历史，且不会在数据库事务中执行。"""

    store = FakeConversationStore()
    agent = RecordingAgent(store)
    service = make_service(store, agent=agent)
    thread = service.start_thread(ACCOUNT_ID)

    first = service.ask(
        ACCOUNT_ID,
        thread.id,
        portfolio_user_id=PORTFOLIO_USER_ID,
        question="GOOG 可以继续观察吗？",
        client_request_id=uuid4(),
        expected_thread_revision=0,
    )

    assert first.thread.revision == 2
    assert first.assistant_message is not None
    assert first.sources[0].provider_reference == "GOOG:quote"
    assert agent.calls[0][0:3] == (
        ACCOUNT_ID,
        PORTFOLIO_USER_ID,
        "GOOG 可以继续观察吗？",
    )
    assert agent.calls[0][3] == ()
    assert store.commit_count == 3
    history = service.history(ACCOUNT_ID, thread.id, limit=1)
    assert len(history.messages) == 1
    assert history.messages[0].role is ConversationMessageRole.ASSISTANT
    assert history.thread.revision == 2


def test_idempotent_retry_returns_same_turn_without_second_agent_call() -> None:
    """同一 client_request_id 重试复用已持久化结果。"""

    store = FakeConversationStore()
    agent = RecordingAgent(store, warnings=("USAGE_NOT_REPORTED",))
    service = make_service(store, agent=agent)
    thread = service.start_thread(ACCOUNT_ID)
    request_id = uuid4()
    first = service.ask(
        ACCOUNT_ID,
        thread.id,
        portfolio_user_id=PORTFOLIO_USER_ID,
        question="当前现金是多少？",
        client_request_id=request_id,
        expected_thread_revision=0,
    )

    replay = service.ask(
        ACCOUNT_ID,
        thread.id,
        portfolio_user_id=PORTFOLIO_USER_ID,
        question="当前现金是多少？",
        client_request_id=request_id,
        expected_thread_revision=0,
    )

    assert replay.turn.id == first.turn.id
    assert replay.assistant_message == first.assistant_message
    assert replay.warnings == first.warnings == ("USAGE_NOT_REPORTED",)
    assert len(agent.calls) == 1


@pytest.mark.parametrize(
    ("source_url", "source_id"),
    (
        ("javascript:alert(1)", None),
        (None, UUID("80000000-0000-4000-8000-000000000001")),
    ),
)
def test_invalid_source_fails_turn_without_persisting_assistant(
    source_url: str | None,
    source_id: UUID | None,
) -> None:
    """URL 或 Citation Contract 失败不得留下 RUNNING Turn 或假 Assistant。"""

    store = FakeConversationStore()
    service = make_service(
        store,
        agent=RecordingAgent(store, source_url=source_url, source_id=source_id),
    )
    thread = service.start_thread(ACCOUNT_ID)

    completed = service.ask(
        ACCOUNT_ID,
        thread.id,
        portfolio_user_id=PORTFOLIO_USER_ID,
        question="GOOG 有什么变化？",
        client_request_id=uuid4(),
        expected_thread_revision=0,
    )

    assert completed.turn.status is ConversationTurnStatus.FAILED
    assert completed.turn.failure_code == "SOURCE_VALIDATION_FAILED"
    assert completed.assistant_message is None
    assert [message.role for message in store.messages.values()] == [ConversationMessageRole.USER]


def test_duplicate_source_ids_fail_turn_without_persisting_assistant() -> None:
    """重复 Source ID 应作为验证失败处理，而非数据库异常。"""

    class DuplicateSourceAgent(RecordingAgent):
        def answer(
            self,
            *,
            account_id: UUID,
            portfolio_user_id: UUID,
            question: str,
            history: tuple[ConversationHistoryMessage, ...],
        ) -> ConversationAgentResult:
            result = super().answer(
                account_id=account_id,
                portfolio_user_id=portfolio_user_id,
                question=question,
                history=history,
            )
            return ConversationAgentResult(
                answer=f"已核对行情。[source:{self.source_id}]",
                sources=(result.sources[0], result.sources[0]),
            )

    store = FakeConversationStore()
    source_id = UUID("80000000-0000-4000-8000-000000000001")
    service = make_service(store, agent=DuplicateSourceAgent(store, source_id=source_id))
    thread = service.start_thread(ACCOUNT_ID)

    completed = service.ask(
        ACCOUNT_ID,
        thread.id,
        portfolio_user_id=PORTFOLIO_USER_ID,
        question="GOOG 行情如何？",
        client_request_id=uuid4(),
        expected_thread_revision=0,
    )

    assert completed.turn.status is ConversationTurnStatus.FAILED
    assert completed.turn.failure_code == "SOURCE_VALIDATION_FAILED"
    assert completed.assistant_message is None
    assert [message.role for message in store.messages.values()] == [ConversationMessageRole.USER]


def test_revision_and_running_conflicts_are_account_owned() -> None:
    """过期 Revision、并发 Turn 和跨 Account 访问都在 Service 层拒绝。"""

    store = FakeConversationStore()
    service = make_service(store)
    thread = service.start_thread(ACCOUNT_ID)

    with pytest.raises(ConversationRevisionConflict):
        service.start_turn(
            ACCOUNT_ID,
            thread.id,
            portfolio_user_id=PORTFOLIO_USER_ID,
            question="第一次问题",
            client_request_id=uuid4(),
            expected_thread_revision=1,
        )

    started = service.start_turn(
        ACCOUNT_ID,
        thread.id,
        portfolio_user_id=PORTFOLIO_USER_ID,
        question="第一次问题",
        client_request_id=uuid4(),
        expected_thread_revision=0,
    )
    with pytest.raises(ConversationTurnInProgress) as error:
        service.start_turn(
            ACCOUNT_ID,
            thread.id,
            portfolio_user_id=PORTFOLIO_USER_ID,
            question="第二次问题",
            client_request_id=uuid4(),
            expected_thread_revision=1,
        )
    assert error.value.turn_id == started.turn.id
    with pytest.raises(ConversationThreadNotFound):
        service.get_thread(OTHER_ACCOUNT_ID, thread.id)


def test_same_request_id_with_different_question_is_rejected() -> None:
    """Idempotency Key 不能被客户端复用于另一条 Message。"""

    store = FakeConversationStore()
    service = make_service(store)
    thread = service.start_thread(ACCOUNT_ID)
    request_id = uuid4()
    service.start_turn(
        ACCOUNT_ID,
        thread.id,
        portfolio_user_id=PORTFOLIO_USER_ID,
        question="原始问题",
        client_request_id=request_id,
        expected_thread_revision=0,
    )

    with pytest.raises(ConversationIdempotencyConflict):
        service.start_turn(
            ACCOUNT_ID,
            thread.id,
            portfolio_user_id=PORTFOLIO_USER_ID,
            question="修改后的问题",
            client_request_id=request_id,
            expected_thread_revision=1,
        )


def test_history_is_bounded_to_recent_twenty_messages() -> None:
    """Agent 每轮最多收到最近 20 条 User / Assistant Message。"""

    store = FakeConversationStore()
    agent = RecordingAgent(store)
    service = make_service(store, agent=agent)
    thread = service.start_thread(ACCOUNT_ID)
    current = thread
    for index in range(11):
        result = service.ask(
            ACCOUNT_ID,
            current.id,
            portfolio_user_id=PORTFOLIO_USER_ID,
            question=f"问题 {index}",
            client_request_id=uuid4(),
            expected_thread_revision=current.revision,
        )
        current = result.thread

    assert len(agent.calls[-1][3]) == 20
    assert agent.calls[-1][3][0].content == "问题 0"
    assert agent.calls[-1][3][-1].content == "已结合当前事实分析。"


def test_agent_history_also_respects_serialized_length_limit() -> None:
    """长对话只保留可放入序列化上限的最新完整 Message。"""

    store = FakeConversationStore()
    agent = RecordingAgent(store, answer="答" * 3_000)
    service = make_service(store, agent=agent)
    current = service.start_thread(ACCOUNT_ID)
    for index in range(5):
        result = service.ask(
            ACCOUNT_ID,
            current.id,
            portfolio_user_id=PORTFOLIO_USER_ID,
            question=f"问题 {index}" + "问" * 2_990,
            client_request_id=uuid4(),
            expected_thread_revision=current.revision,
        )
        current = result.thread

    history = agent.calls[-1][3]
    serialized = json.dumps(
        [{"role": item.role.value, "content": item.content} for item in history],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    assert len(serialized) <= MAX_HISTORY_SERIALIZED_CHARS
    assert history[-1].content == "答" * 3_000
    assert len(history) < 8


def test_failure_persists_without_assistant_message_and_expired_run_is_abandoned() -> None:
    """Agent Failure 不伪造回答；下一次读取会收敛过期 RUNNING Turn。"""

    current_time = NOW
    store = FakeConversationStore()
    service = make_service(store, clock=lambda: current_time)
    thread = service.start_thread(ACCOUNT_ID)
    started = service.start_turn(
        ACCOUNT_ID,
        thread.id,
        portfolio_user_id=PORTFOLIO_USER_ID,
        question="需要失败的请求",
        client_request_id=uuid4(),
        expected_thread_revision=0,
    )
    failed = service.fail_turn(
        ACCOUNT_ID,
        thread.id,
        started.turn.id,
        failure_code="LLM_PROVIDER_UNAVAILABLE",
    )
    assert failed.turn.status is ConversationTurnStatus.FAILED
    assert failed.turn.failure_code == "LLM_PROVIDER_UNAVAILABLE"
    assert failed.assistant_message is None

    second = service.start_turn(
        ACCOUNT_ID,
        thread.id,
        portfolio_user_id=PORTFOLIO_USER_ID,
        question="会过期的请求",
        client_request_id=uuid4(),
        expected_thread_revision=2,
    )
    current_time = NOW + timedelta(seconds=31)
    snapshot = service.get_thread(ACCOUNT_ID, thread.id)
    assert snapshot.active_turn is None
    assert snapshot.last_turn is not None
    assert snapshot.last_turn.id == second.turn.id
    assert snapshot.last_turn.failure_code == "AGENT_RUN_ABANDONED"
    with pytest.raises(ConversationRunExpired):
        service.complete_turn(
            ACCOUNT_ID,
            thread.id,
            second.turn.id,
            answer="迟到的回答",
        )


def test_delete_is_soft_and_excludes_thread_from_future_reads() -> None:
    """删除只设置 deleted_at，之后列表与读取均不再暴露 Thread。"""

    store = FakeConversationStore()
    service = make_service(store)
    thread = service.start_thread(ACCOUNT_ID)
    deleted = service.delete_thread(ACCOUNT_ID, thread.id)
    assert deleted.deleted_at == NOW
    assert service.list_threads(ACCOUNT_ID).items == ()
    with pytest.raises(ConversationThreadNotFound):
        service.get_thread(ACCOUNT_ID, thread.id)
