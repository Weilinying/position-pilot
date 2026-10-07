"""Conversation Thread、Turn 与用户可见 Message 的 Application Service。

本模块只定义 Conversation 的 Application Contract 与生命周期编排，不依赖 ORM、FastAPI
或 Agent Framework。持久化适配器通过 ``ConversationUnitOfWork`` 实现；LLM / Agent 调用
发生在 ``start_turn`` 提交之后，避免在外部调用期间持有数据库事务。
"""

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from types import TracebackType
from typing import Protocol, Self
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from position_pilot.application.agent_runtime import DEFAULT_WALL_CLOCK_BUDGET_SECONDS
from position_pilot.application.conversation_citations import (
    CitationValidationError,
    validate_citations,
)
from position_pilot.application.strategy_service import (
    StrategyError,
    StrategyRepository,
    StrategyService,
)
from position_pilot.domain.strategy import StrategyCandidate, StrategyDraft

MAX_THREAD_TITLE_LENGTH = 200
MAX_MESSAGE_LENGTH = 4_000
DEFAULT_HISTORY_LIMIT = 20
MAX_HISTORY_SERIALIZED_CHARS = 20_000
DEFAULT_PAGE_LIMIT = 20
# Turn 租约覆盖 Native 总预算及准备/收尾余量；不延长 Runtime 或 Provider 的执行预算。
RUN_COMPLETION_GRACE = timedelta(seconds=5)
DEFAULT_RUN_TIMEOUT = timedelta(seconds=DEFAULT_WALL_CLOCK_BUDGET_SECONDS) + RUN_COMPLETION_GRACE


class ConversationError(Exception):
    """Conversation Application 层错误基类。"""


class ConversationValidationError(ConversationError):
    """Conversation 输入不满足最小边界。"""


class ConversationThreadNotFound(ConversationError):
    """当前 Account 无权访问该 Thread，或 Thread 已软删除。"""

    def __init__(self, thread_id: UUID) -> None:
        self.thread_id = thread_id
        super().__init__("Thread 不存在或不可访问")


class ConversationTurnNotFound(ConversationError):
    """Turn 不属于当前 Account / Thread，或已不存在。"""

    def __init__(self, turn_id: UUID) -> None:
        self.turn_id = turn_id
        super().__init__("Turn 不存在或不可访问")


class ConversationRevisionConflict(ConversationError):
    """客户端提交的 Thread Revision 已过期。"""

    def __init__(self, expected: int, actual: int) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(f"Thread Revision 冲突：expected={expected}, actual={actual}")


class ConversationTurnInProgress(ConversationError):
    """同一 Thread 已有 RUNNING Turn。"""

    def __init__(self, turn_id: UUID) -> None:
        self.turn_id = turn_id
        super().__init__("该 Thread 已有 RUNNING Turn")


class ConversationIdempotencyConflict(ConversationError):
    """同一 Client Request ID 被复用于不同问题。"""

    def __init__(self, client_request_id: UUID) -> None:
        self.client_request_id = client_request_id
        super().__init__("client_request_id 已用于不同问题")


class ConversationTurnStateConflict(ConversationError):
    """Turn 不处于当前操作要求的状态。"""

    def __init__(self, turn_id: UUID, status: "ConversationTurnStatus") -> None:
        self.turn_id = turn_id
        self.status = status
        super().__init__(f"Turn 状态不允许当前操作：{status.value}")


class ConversationRunExpired(ConversationError):
    """Agent 返回时 Run 已超过其 deadline。"""

    def __init__(self, turn_id: UUID) -> None:
        self.turn_id = turn_id
        super().__init__("Agent Run 已过期")


class ConversationTurnStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ConversationMessageRole(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"


@dataclass(frozen=True, slots=True)
class ConversationThread:
    """Account-owned Thread 的 Application DTO。"""

    id: UUID
    account_id: UUID
    title: str | None
    revision: int
    next_sequence: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    """一次 Agent Run 的可持久化状态。"""

    id: UUID
    thread_id: UUID
    account_id: UUID
    client_request_id: UUID
    status: ConversationTurnStatus
    failure_code: str | None
    run_deadline_at: datetime | None
    created_at: datetime
    completed_at: datetime | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    """用户可见、append-only 的 User / Assistant Message。"""

    id: UUID
    thread_id: UUID
    account_id: UUID
    turn_id: UUID
    sequence: int
    role: ConversationMessageRole
    content: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ConversationSource:
    """Assistant Message 观察到的 Source Metadata。"""

    source_id: UUID
    assistant_message_id: UUID
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


@dataclass(frozen=True, slots=True)
class ConversationSourceInput:
    """Agent 返回的 Source Metadata；ID 与 Message Owner 由 Service 生成。"""

    source_type: str
    provider: str
    source_id: UUID | None = None
    provider_reference: str | None = None
    url: str | None = None
    title: str | None = None
    publisher: str | None = None
    published_at: datetime | None = None
    event_time: datetime | None = None
    fetched_at: datetime | None = None
    content_scope: str = "UNKNOWN"
    status: str = "OK"


@dataclass(frozen=True, slots=True)
class ConversationHistoryMessage:
    """传给 Agent 的最小有界历史，不包含 Tool Observation 或内部 Message。"""

    role: ConversationMessageRole
    content: str


@dataclass(frozen=True, slots=True)
class ConversationAgentResult:
    """Provider-neutral Agent 结果；失败由稳定 Failure Code 表达。"""

    answer: str | None = None
    sources: tuple[ConversationSourceInput, ...] = ()
    warnings: tuple[str, ...] = ()
    failure_code: str | None = None
    strategy_draft: StrategyDraft | None = None


@dataclass(frozen=True, slots=True)
class ConversationThreadPage:
    """Thread 列表及下一页 Cursor。"""

    items: tuple[ConversationThread, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class ConversationHistoryPage:
    """Message 分页，并附带提交下一轮所需的 Thread 状态。"""

    thread: ConversationThread
    messages: tuple[ConversationMessage, ...]
    active_turn: ConversationTurn | None
    next_cursor: str | None
    answers: tuple["ConversationHistoryAnswer", ...] = ()


@dataclass(frozen=True, slots=True)
class ConversationHistoryAnswer:
    """已持久化 Assistant Message 的来源与 Warning 快照。"""

    message_id: UUID
    sources: tuple[ConversationSource, ...]
    warnings: tuple[str, ...]
    candidate: StrategyCandidate | None = None


@dataclass(frozen=True, slots=True)
class ConversationMessagePage:
    """Repository 返回的 Message 分页结果。"""

    items: tuple[ConversationMessage, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class ConversationThreadSnapshot:
    """Thread Metadata、当前 RUNNING Turn 与最近 Turn。"""

    thread: ConversationThread
    active_turn: ConversationTurn | None
    last_turn: ConversationTurn | None


@dataclass(frozen=True, slots=True)
class ConversationTurnStart:
    """短事务提交后交给 Agent Run 的输入。"""

    thread: ConversationThread
    turn: ConversationTurn
    user_message: ConversationMessage
    history: tuple[ConversationHistoryMessage, ...]
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class ConversationCompletion:
    """完成 Turn 后的用户可见结果。"""

    thread: ConversationThread
    turn: ConversationTurn
    user_message: ConversationMessage
    assistant_message: ConversationMessage | None
    sources: tuple[ConversationSource, ...]
    warnings: tuple[str, ...] = ()
    candidate: StrategyCandidate | None = None


class ConversationAgent(Protocol):
    """Conversation Service 使用的 Provider-neutral Agent Port。"""

    def answer(
        self,
        *,
        account_id: UUID,
        portfolio_user_id: UUID,
        question: str,
        history: tuple[ConversationHistoryMessage, ...],
    ) -> ConversationAgentResult: ...


class ConversationUnitOfWork(Protocol):
    """Conversation Service 所需的最小同步事务与 Repository Port。"""

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def get_thread(
        self,
        account_id: UUID,
        thread_id: UUID,
        *,
        for_update: bool = False,
    ) -> ConversationThread | None: ...

    def add_thread(self, thread: ConversationThread) -> None: ...

    def update_thread(self, thread: ConversationThread) -> None: ...

    def list_threads(
        self,
        account_id: UUID,
        *,
        cursor: str | None,
        limit: int,
    ) -> ConversationThreadPage: ...

    def get_turn_by_client_request_id(
        self,
        account_id: UUID,
        thread_id: UUID,
        client_request_id: UUID,
        *,
        for_update: bool = False,
    ) -> ConversationTurn | None: ...

    def get_turn(
        self,
        account_id: UUID,
        thread_id: UUID,
        turn_id: UUID,
        *,
        for_update: bool = False,
    ) -> ConversationTurn | None: ...

    def get_running_turn(
        self,
        account_id: UUID,
        thread_id: UUID,
        *,
        for_update: bool = False,
    ) -> ConversationTurn | None: ...

    def get_last_turn(
        self,
        account_id: UUID,
        thread_id: UUID,
    ) -> ConversationTurn | None: ...

    def get_user_message_for_turn(
        self,
        account_id: UUID,
        thread_id: UUID,
        turn_id: UUID,
    ) -> ConversationMessage | None: ...

    def get_assistant_message_for_turn(
        self,
        account_id: UUID,
        thread_id: UUID,
        turn_id: UUID,
    ) -> ConversationMessage | None: ...

    def add_turn(self, turn: ConversationTurn) -> None: ...

    def update_turn(self, turn: ConversationTurn) -> None: ...

    def add_message(self, message: ConversationMessage) -> None: ...

    def add_sources(self, sources: Sequence[ConversationSource]) -> None: ...

    def list_sources_for_message(
        self,
        account_id: UUID,
        thread_id: UUID,
        assistant_message_id: UUID,
    ) -> tuple[ConversationSource, ...]: ...

    def list_messages(
        self,
        account_id: UUID,
        thread_id: UUID,
        *,
        before_sequence: int | None,
        limit: int,
    ) -> ConversationMessagePage: ...

    def commit(self) -> None: ...


ConversationUnitOfWorkFactory = Callable[[], ConversationUnitOfWork]


def _now(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ConversationValidationError("Conversation 时间必须包含时区")
    return value.astimezone(UTC)


def _validate_question(question: str) -> str:
    if not isinstance(question, str):
        raise ConversationValidationError("question 必须是字符串")
    normalized = question.strip()
    if not normalized or len(normalized) > MAX_MESSAGE_LENGTH:
        raise ConversationValidationError(f"question 必须包含 1 到 {MAX_MESSAGE_LENGTH} 个字符")
    return normalized


def _validate_limit(limit: int, *, maximum: int = 100) -> int:
    if isinstance(limit, bool) or not 1 <= limit <= maximum:
        raise ConversationValidationError(f"limit 必须在 1 到 {maximum} 之间")
    return limit


def _validate_source_url(source: ConversationSourceInput) -> None:
    """持久化前拒绝不能安全作为公开来源链接的 URL。"""

    if source.url is None:
        return
    if not isinstance(source.url, str) or any(character.isspace() for character in source.url):
        raise ConversationValidationError("Source URL 无效")
    try:
        parsed = urlsplit(source.url)
        hostname = parsed.hostname
    except ValueError as error:
        raise ConversationValidationError("Source URL 无效") from error
    if (
        parsed.scheme not in {"http", "https"}
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ConversationValidationError("Source URL 只能使用无 Credential 的 HTTP(S) 地址")


class ConversationService:
    """协调 Thread / Turn / Message 生命周期与 Agent 外部调用。"""

    def __init__(
        self,
        unit_of_work_factory: ConversationUnitOfWorkFactory,
        *,
        agent: ConversationAgent | None = None,
        clock: Callable[[], datetime] | None = None,
        run_timeout: timedelta = DEFAULT_RUN_TIMEOUT,
        strategy_repository_factory: Callable[[ConversationUnitOfWork], StrategyRepository]
        | None = None,
    ) -> None:
        if run_timeout <= timedelta(0):
            raise ConversationValidationError("run_timeout 必须为正数")
        self._unit_of_work_factory = unit_of_work_factory
        self._agent = agent
        self._clock = clock or (lambda: datetime.now(UTC))
        self._run_timeout = run_timeout
        self._strategy_repository_factory = strategy_repository_factory

    def start_thread(
        self,
        account_id: UUID,
        *,
        title: str | None = None,
    ) -> ConversationThread:
        """创建当前 Account 的空 Thread。"""

        normalized_title = self._normalize_title(title)
        now = _now(self._clock())
        thread = ConversationThread(
            id=uuid4(),
            account_id=account_id,
            title=normalized_title,
            revision=0,
            next_sequence=1,
            created_at=now,
            updated_at=now,
        )
        with self._unit_of_work_factory() as unit_of_work:
            unit_of_work.add_thread(thread)
            unit_of_work.commit()
        return thread

    def start_turn(
        self,
        account_id: UUID,
        thread_id: UUID,
        *,
        portfolio_user_id: UUID,
        question: str,
        client_request_id: UUID,
        expected_thread_revision: int,
    ) -> ConversationTurnStart:
        """短事务创建 RUNNING Turn 与 User Message，并读取有界旧历史。

        返回后事务已经提交；调用方可以安全执行 Agent，不会在模型等待期间持有数据库锁。
        """

        del portfolio_user_id
        normalized_question = _validate_question(question)
        if expected_thread_revision < 0:
            raise ConversationValidationError("expected_thread_revision 不能为负数")
        now = _now(self._clock())
        with self._unit_of_work_factory() as unit_of_work:
            thread = self._get_active_thread(unit_of_work, account_id, thread_id, for_update=True)
            existing = unit_of_work.get_turn_by_client_request_id(
                account_id,
                thread_id,
                client_request_id,
                for_update=True,
            )
            if existing is not None:
                existing_user_message = unit_of_work.get_user_message_for_turn(
                    account_id,
                    thread_id,
                    existing.id,
                )
                if (
                    existing_user_message is None
                    or existing_user_message.content != normalized_question
                ):
                    raise ConversationIdempotencyConflict(client_request_id)
                if existing.status is ConversationTurnStatus.RUNNING and self._is_expired(
                    existing, now
                ):
                    thread, existing = self._abandon_turn(unit_of_work, thread, existing, now)
                    unit_of_work.commit()
                if existing.status is ConversationTurnStatus.RUNNING:
                    raise ConversationTurnInProgress(existing.id)
                history = self._bounded_history(
                    unit_of_work,
                    account_id,
                    thread_id,
                    before_sequence=existing_user_message.sequence,
                )
                return ConversationTurnStart(
                    thread,
                    existing,
                    existing_user_message,
                    history,
                    replayed=True,
                )

            running = unit_of_work.get_running_turn(
                account_id,
                thread_id,
                for_update=True,
            )
            abandoned = False
            if running is not None and self._is_expired(running, now):
                thread, running = self._abandon_turn(unit_of_work, thread, running, now)
                running = None
                abandoned = True
            if running is not None:
                raise ConversationTurnInProgress(running.id)
            if thread.revision != expected_thread_revision:
                if abandoned:
                    unit_of_work.commit()
                raise ConversationRevisionConflict(expected_thread_revision, thread.revision)

            user_message = ConversationMessage(
                id=uuid4(),
                thread_id=thread.id,
                account_id=account_id,
                turn_id=uuid4(),
                sequence=thread.next_sequence,
                role=ConversationMessageRole.USER,
                content=normalized_question,
                created_at=now,
            )
            turn = ConversationTurn(
                id=user_message.turn_id,
                thread_id=thread.id,
                account_id=account_id,
                client_request_id=client_request_id,
                status=ConversationTurnStatus.RUNNING,
                failure_code=None,
                run_deadline_at=now + self._run_timeout,
                created_at=now,
            )
            updated_thread = replace(
                thread,
                title=thread.title or normalized_question[:MAX_THREAD_TITLE_LENGTH],
                revision=thread.revision + 1,
                next_sequence=thread.next_sequence + 1,
                updated_at=now,
            )
            history = self._bounded_history(
                unit_of_work,
                account_id,
                thread_id,
                before_sequence=thread.next_sequence,
            )
            unit_of_work.add_turn(turn)
            unit_of_work.add_message(user_message)
            unit_of_work.update_thread(updated_thread)
            unit_of_work.commit()
            return ConversationTurnStart(updated_thread, turn, user_message, history)

    def complete_turn(
        self,
        account_id: UUID,
        thread_id: UUID,
        turn_id: UUID,
        *,
        answer: str,
        sources: tuple[ConversationSourceInput, ...] = (),
        warnings: tuple[str, ...] = (),
        strategy_draft: StrategyDraft | None = None,
    ) -> ConversationCompletion:
        """短事务追加 Assistant Message、Sources 并完成 Turn。"""

        if not isinstance(answer, str) or not answer.strip():
            raise ConversationValidationError("assistant answer 不能为空")
        for source in sources:
            _validate_source_url(source)
        try:
            validate_citations(answer, sources)
        except CitationValidationError as error:
            raise ConversationValidationError("Answer Citation 与本轮来源不一致") from error
        now = _now(self._clock())
        with self._unit_of_work_factory() as unit_of_work:
            thread = self._get_active_thread(unit_of_work, account_id, thread_id, for_update=True)
            turn = self._get_turn(unit_of_work, account_id, thread_id, turn_id, for_update=True)
            if turn.status is not ConversationTurnStatus.RUNNING:
                if turn.status is ConversationTurnStatus.COMPLETED:
                    return self._completed_result(unit_of_work, thread, turn)
                if turn.failure_code == "AGENT_RUN_ABANDONED":
                    raise ConversationRunExpired(turn.id)
                raise ConversationTurnStateConflict(turn.id, turn.status)
            if self._is_expired(turn, now):
                self._abandon_turn(unit_of_work, thread, turn, now)
                unit_of_work.commit()
                raise ConversationRunExpired(turn.id)
            user_message = unit_of_work.get_user_message_for_turn(account_id, thread_id, turn.id)
            if user_message is None:
                raise ConversationTurnNotFound(turn.id)
            assistant_message = ConversationMessage(
                id=uuid4(),
                thread_id=thread.id,
                account_id=account_id,
                turn_id=turn.id,
                sequence=thread.next_sequence,
                role=ConversationMessageRole.ASSISTANT,
                content=answer.strip(),
                created_at=now,
            )
            persisted_sources = tuple(
                ConversationSource(
                    source_id=source.source_id or uuid4(),
                    assistant_message_id=assistant_message.id,
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
                for source in sources
            )
            completed_turn = replace(
                turn,
                status=ConversationTurnStatus.COMPLETED,
                completed_at=now,
                warnings=warnings,
            )
            updated_thread = replace(
                thread,
                revision=thread.revision + 1,
                next_sequence=thread.next_sequence + 1,
                updated_at=now,
            )
            unit_of_work.add_message(assistant_message)
            unit_of_work.add_sources(persisted_sources)
            unit_of_work.update_turn(completed_turn)
            unit_of_work.update_thread(updated_thread)
            candidate = None
            if strategy_draft is not None:
                if self._strategy_repository_factory is None:
                    raise StrategyError("STRATEGY_INVALID", "当前 Ask 未启用持久意图")
                candidate = StrategyService.propose_in_repository(
                    self._strategy_repository_factory(unit_of_work),
                    account_id=account_id,
                    thread_id=thread.id,
                    user_message_id=user_message.id,
                    assistant_message_id=assistant_message.id,
                    request_id=turn.client_request_id,
                    draft=strategy_draft,
                    now=now,
                )
            unit_of_work.commit()
            return ConversationCompletion(
                updated_thread,
                completed_turn,
                user_message,
                assistant_message,
                persisted_sources,
                completed_turn.warnings,
                candidate,
            )

    def fail_turn(
        self,
        account_id: UUID,
        thread_id: UUID,
        turn_id: UUID,
        *,
        failure_code: str,
    ) -> ConversationCompletion:
        """短事务记录 Turn Failure，不伪造 Assistant Message。"""

        if not isinstance(failure_code, str) or not failure_code.strip():
            raise ConversationValidationError("failure_code 不能为空")
        now = _now(self._clock())
        with self._unit_of_work_factory() as unit_of_work:
            thread = self._get_active_thread(unit_of_work, account_id, thread_id, for_update=True)
            turn = self._get_turn(unit_of_work, account_id, thread_id, turn_id, for_update=True)
            user_message = unit_of_work.get_user_message_for_turn(account_id, thread_id, turn.id)
            if user_message is None:
                raise ConversationTurnNotFound(turn.id)
            if turn.status is not ConversationTurnStatus.RUNNING:
                if turn.status is ConversationTurnStatus.COMPLETED:
                    return self._completed_result(unit_of_work, thread, turn)
                return ConversationCompletion(thread, turn, user_message, None, ())
            failure = "AGENT_RUN_ABANDONED" if self._is_expired(turn, now) else failure_code.strip()
            failed_turn = replace(
                turn,
                status=ConversationTurnStatus.FAILED,
                failure_code=failure,
                completed_at=now,
            )
            updated_thread = replace(thread, revision=thread.revision + 1, updated_at=now)
            unit_of_work.update_turn(failed_turn)
            unit_of_work.update_thread(updated_thread)
            unit_of_work.commit()
            return ConversationCompletion(updated_thread, failed_turn, user_message, None, ())

    def ask(
        self,
        account_id: UUID,
        thread_id: UUID,
        *,
        portfolio_user_id: UUID,
        question: str,
        client_request_id: UUID,
        expected_thread_revision: int,
    ) -> ConversationCompletion:
        """执行一次完整 Ask；Agent 调用始终在 start_turn 事务之外。"""

        if self._agent is None:
            raise ConversationValidationError("Conversation Agent 尚未配置")
        started = self.start_turn(
            account_id,
            thread_id,
            portfolio_user_id=portfolio_user_id,
            question=question,
            client_request_id=client_request_id,
            expected_thread_revision=expected_thread_revision,
        )
        if started.replayed:
            return self._replay_completion(account_id, thread_id, started)
        try:
            result = self._agent.answer(
                account_id=account_id,
                portfolio_user_id=portfolio_user_id,
                question=question.strip(),
                history=started.history,
            )
        except Exception:
            self.fail_turn(
                account_id,
                thread_id,
                started.turn.id,
                failure_code="AGENT_REQUEST_FAILED",
            )
            raise
        if result.failure_code is not None:
            return self.fail_turn(
                account_id,
                thread_id,
                started.turn.id,
                failure_code=result.failure_code,
            )
        if result.answer is None:
            return self.fail_turn(
                account_id,
                thread_id,
                started.turn.id,
                failure_code="AGENT_INVALID_RESPONSE",
            )
        try:
            return self.complete_turn(
                account_id,
                thread_id,
                started.turn.id,
                answer=result.answer,
                sources=result.sources,
                warnings=result.warnings,
                strategy_draft=result.strategy_draft,
            )
        except StrategyError as error:
            self.fail_turn(account_id, thread_id, started.turn.id, failure_code=error.code)
            raise
        except ConversationValidationError:
            return self.fail_turn(
                account_id,
                thread_id,
                started.turn.id,
                failure_code="SOURCE_VALIDATION_FAILED",
            )

    def delete_thread(self, account_id: UUID, thread_id: UUID) -> ConversationThread:
        """软删除 Thread；RUNNING Turn 存在时不删除。"""

        now = _now(self._clock())
        with self._unit_of_work_factory() as unit_of_work:
            thread = self._get_active_thread(unit_of_work, account_id, thread_id, for_update=True)
            running = unit_of_work.get_running_turn(account_id, thread_id, for_update=True)
            if running is not None:
                if self._is_expired(running, now):
                    thread, running = self._abandon_turn(unit_of_work, thread, running, now)
                else:
                    raise ConversationTurnInProgress(running.id)
            deleted = replace(thread, deleted_at=now, revision=thread.revision + 1, updated_at=now)
            unit_of_work.update_thread(deleted)
            if self._strategy_repository_factory is not None:
                self._strategy_repository_factory(unit_of_work).cancel_thread(
                    account_id, thread_id, now
                )
            unit_of_work.commit()
            return deleted

    def list_threads(
        self,
        account_id: UUID,
        *,
        cursor: str | None = None,
        limit: int = DEFAULT_PAGE_LIMIT,
    ) -> ConversationThreadPage:
        """列出当前 Account 未删除 Thread。"""

        limit = _validate_limit(limit)
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.list_threads(account_id, cursor=cursor, limit=limit)

    def get_thread(self, account_id: UUID, thread_id: UUID) -> ConversationThreadSnapshot:
        """读取 Thread，并在锁内收敛已过期 RUNNING Turn。"""

        now = _now(self._clock())
        with self._unit_of_work_factory() as unit_of_work:
            thread = self._get_active_thread(unit_of_work, account_id, thread_id, for_update=True)
            running = unit_of_work.get_running_turn(account_id, thread_id, for_update=True)
            last_turn: ConversationTurn | None
            if running is not None and self._is_expired(running, now):
                thread, running = self._abandon_turn(unit_of_work, thread, running, now)
                unit_of_work.commit()
                last_turn = running
                running = None
            else:
                last_turn = unit_of_work.get_last_turn(account_id, thread_id)
            return ConversationThreadSnapshot(thread, running, last_turn)

    def history(
        self,
        account_id: UUID,
        thread_id: UUID,
        *,
        before_sequence: int | None = None,
        limit: int = DEFAULT_HISTORY_LIMIT,
    ) -> ConversationHistoryPage:
        """读取用户可见 Message；首次 Agent Context 使用最近 20 条。"""

        limit = _validate_limit(limit)
        now = _now(self._clock())
        with self._unit_of_work_factory() as unit_of_work:
            thread = self._get_active_thread(unit_of_work, account_id, thread_id, for_update=True)
            running = unit_of_work.get_running_turn(account_id, thread_id, for_update=True)
            if running is not None and self._is_expired(running, now):
                thread, running = self._abandon_turn(unit_of_work, thread, running, now)
                unit_of_work.commit()
                running = None
            message_page = unit_of_work.list_messages(
                account_id,
                thread_id,
                before_sequence=before_sequence,
                limit=limit,
            )
            answers: list[ConversationHistoryAnswer] = []
            for message in message_page.items:
                if message.role is not ConversationMessageRole.ASSISTANT:
                    continue
                turn = unit_of_work.get_turn(account_id, thread_id, message.turn_id)
                if turn is None:
                    raise ConversationTurnNotFound(message.turn_id)
                answers.append(
                    ConversationHistoryAnswer(
                        message.id,
                        unit_of_work.list_sources_for_message(account_id, thread_id, message.id),
                        turn.warnings,
                        self._message_candidate(unit_of_work, account_id, message.id),
                    )
                )
            return ConversationHistoryPage(
                thread,
                message_page.items,
                running,
                message_page.next_cursor,
                tuple(answers),
            )

    def _get_active_thread(
        self,
        unit_of_work: ConversationUnitOfWork,
        account_id: UUID,
        thread_id: UUID,
        *,
        for_update: bool,
    ) -> ConversationThread:
        thread = unit_of_work.get_thread(account_id, thread_id, for_update=for_update)
        if thread is None or thread.deleted_at is not None:
            raise ConversationThreadNotFound(thread_id)
        return thread

    @staticmethod
    def _get_turn(
        unit_of_work: ConversationUnitOfWork,
        account_id: UUID,
        thread_id: UUID,
        turn_id: UUID,
        *,
        for_update: bool,
    ) -> ConversationTurn:
        turn = unit_of_work.get_turn(account_id, thread_id, turn_id, for_update=for_update)
        if turn is None:
            raise ConversationTurnNotFound(turn_id)
        return turn

    @staticmethod
    def _normalize_title(title: str | None) -> str | None:
        if title is None:
            return None
        if not isinstance(title, str):
            raise ConversationValidationError("title 必须是字符串")
        normalized = title.strip()
        if not normalized:
            return None
        if len(normalized) > MAX_THREAD_TITLE_LENGTH:
            raise ConversationValidationError(f"title 最多 {MAX_THREAD_TITLE_LENGTH} 个字符")
        return normalized

    @staticmethod
    def _is_expired(turn: ConversationTurn, now: datetime) -> bool:
        return turn.run_deadline_at is not None and turn.run_deadline_at <= now

    @staticmethod
    def _abandon_turn(
        unit_of_work: ConversationUnitOfWork,
        thread: ConversationThread,
        turn: ConversationTurn,
        now: datetime,
    ) -> tuple[ConversationThread, ConversationTurn]:
        abandoned = replace(
            turn,
            status=ConversationTurnStatus.FAILED,
            failure_code="AGENT_RUN_ABANDONED",
            completed_at=now,
        )
        updated_thread = replace(thread, revision=thread.revision + 1, updated_at=now)
        unit_of_work.update_turn(abandoned)
        unit_of_work.update_thread(updated_thread)
        return updated_thread, abandoned

    @staticmethod
    def _bounded_history(
        unit_of_work: ConversationUnitOfWork,
        account_id: UUID,
        thread_id: UUID,
        *,
        before_sequence: int,
    ) -> tuple[ConversationHistoryMessage, ...]:
        message_page = unit_of_work.list_messages(
            account_id,
            thread_id,
            before_sequence=before_sequence,
            limit=DEFAULT_HISTORY_LIMIT,
        )
        history = tuple(
            ConversationHistoryMessage(message.role, message.content)
            for message in sorted(message_page.items, key=lambda item: item.sequence)
        )
        selected: tuple[ConversationHistoryMessage, ...] = ()
        for message in reversed(history):
            candidate = (message, *selected)
            serialized = json.dumps(
                [{"role": item.role.value, "content": item.content} for item in candidate],
                ensure_ascii=False,
                separators=(",", ":"),
            )
            if len(serialized) > MAX_HISTORY_SERIALIZED_CHARS:
                break
            selected = candidate
        return selected

    def _replay_completion(
        self,
        account_id: UUID,
        thread_id: UUID,
        started: ConversationTurnStart,
    ) -> ConversationCompletion:
        with self._unit_of_work_factory() as unit_of_work:
            assistant = unit_of_work.get_assistant_message_for_turn(
                account_id,
                thread_id,
                started.turn.id,
            )
            sources = (
                unit_of_work.list_sources_for_message(
                    account_id,
                    thread_id,
                    assistant.id,
                )
                if assistant is not None
                else ()
            )
            return ConversationCompletion(
                started.thread,
                started.turn,
                started.user_message,
                assistant,
                tuple(sources),
                started.turn.warnings,
                self._message_candidate(unit_of_work, account_id, assistant.id)
                if assistant
                else None,
            )

    def _completed_result(
        self,
        unit_of_work: ConversationUnitOfWork,
        thread: ConversationThread,
        turn: ConversationTurn,
    ) -> ConversationCompletion:
        user_message = unit_of_work.get_user_message_for_turn(
            turn.account_id,
            turn.thread_id,
            turn.id,
        )
        if user_message is None:
            raise ConversationTurnNotFound(turn.id)
        assistant = unit_of_work.get_assistant_message_for_turn(
            turn.account_id,
            turn.thread_id,
            turn.id,
        )
        sources = (
            unit_of_work.list_sources_for_message(turn.account_id, turn.thread_id, assistant.id)
            if assistant is not None
            else ()
        )
        return ConversationCompletion(
            thread,
            turn,
            user_message,
            assistant,
            tuple(sources),
            turn.warnings,
            self._message_candidate(unit_of_work, turn.account_id, assistant.id)
            if assistant
            else None,
        )

    def _message_candidate(
        self, uow: ConversationUnitOfWork, owner: UUID, message_id: UUID
    ) -> StrategyCandidate | None:
        if self._strategy_repository_factory is None:
            return None
        candidate = self._strategy_repository_factory(uow).by_message(owner, message_id)
        return StrategyService.visible(candidate, self._clock()) if candidate is not None else None


__all__ = [
    "ConversationAgent",
    "ConversationAgentResult",
    "ConversationCompletion",
    "ConversationError",
    "ConversationHistoryMessage",
    "ConversationHistoryPage",
    "ConversationIdempotencyConflict",
    "ConversationMessage",
    "ConversationMessagePage",
    "ConversationMessageRole",
    "MAX_HISTORY_SERIALIZED_CHARS",
    "ConversationRevisionConflict",
    "ConversationRunExpired",
    "ConversationService",
    "ConversationSource",
    "ConversationSourceInput",
    "ConversationThread",
    "ConversationThreadNotFound",
    "ConversationThreadPage",
    "ConversationThreadSnapshot",
    "ConversationTurn",
    "ConversationTurnInProgress",
    "ConversationTurnNotFound",
    "ConversationTurnStart",
    "ConversationTurnStateConflict",
    "ConversationTurnStatus",
    "ConversationUnitOfWork",
    "ConversationValidationError",
]
