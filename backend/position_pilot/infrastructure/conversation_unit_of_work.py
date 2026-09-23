"""Conversation 持久化适配器。

Conversation 使用独立的同步 Unit of Work，避免把 Thread / Turn 的并发语义
混入 Portfolio Ledger UoW。所有读取都显式绑定 Account 与 Thread Owner；
外部 Agent 调用不应在本模块事务中发生。
"""

import base64
import binascii
from collections.abc import Sequence
from datetime import UTC, datetime
from types import TracebackType
from typing import Any, NoReturn, Self, cast
from uuid import UUID

from sqlalchemy import Select, and_, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from position_pilot.application.conversation_service import (
    ConversationIdempotencyConflict,
    ConversationMessage,
    ConversationMessagePage,
    ConversationMessageRole,
    ConversationSource,
    ConversationThread,
    ConversationThreadNotFound,
    ConversationThreadPage,
    ConversationTurn,
    ConversationTurnInProgress,
    ConversationTurnNotFound,
    ConversationTurnStatus,
    ConversationUnitOfWork,
    ConversationValidationError,
)
from position_pilot.infrastructure.conversation_models import (
    ConversationMessageModel,
    ConversationThreadModel,
    ConversationTurnModel,
    MessageSourceModel,
)


def _to_thread(model: ConversationThreadModel) -> ConversationThread:
    """将 Thread ORM Model 转为 Application DTO。"""

    return ConversationThread(
        id=model.id,
        account_id=model.account_id,
        title=model.title,
        revision=model.revision,
        next_sequence=model.next_sequence,
        created_at=_to_utc(model.created_at),
        updated_at=_to_utc(model.updated_at),
        deleted_at=_to_optional_utc(model.deleted_at),
    )


def _to_turn(model: ConversationTurnModel) -> ConversationTurn:
    """将 Turn ORM Model 转为 Application DTO。"""

    return ConversationTurn(
        id=model.id,
        thread_id=model.thread_id,
        account_id=model.account_id,
        client_request_id=model.client_request_id,
        status=ConversationTurnStatus(model.status),
        failure_code=model.failure_code,
        run_deadline_at=_to_optional_utc(model.run_deadline_at),
        created_at=_to_utc(model.created_at),
        completed_at=_to_optional_utc(model.completed_at),
        warnings=tuple(model.warnings),
    )


def _to_message(model: ConversationMessageModel) -> ConversationMessage:
    """将 Message ORM Model 转为 Application DTO。"""

    return ConversationMessage(
        id=model.id,
        thread_id=model.thread_id,
        account_id=model.account_id,
        turn_id=model.turn_id,
        sequence=model.sequence,
        role=ConversationMessageRole(model.role),
        content=model.content,
        created_at=_to_utc(model.created_at),
    )


def _to_source(model: MessageSourceModel) -> ConversationSource:
    """将实际观察到的 Source Metadata 转为 Application DTO。"""

    return ConversationSource(
        source_id=model.source_id,
        assistant_message_id=model.assistant_message_id,
        source_type=model.source_type,
        provider=model.provider,
        provider_reference=model.provider_reference,
        url=model.url,
        title=model.title,
        publisher=model.publisher,
        published_at=_to_optional_utc(model.published_at),
        event_time=_to_optional_utc(model.event_time),
        fetched_at=_to_optional_utc(model.fetched_at),
        content_scope=model.content_scope,
        status=model.status,
    )


def _to_utc(value: datetime | None) -> datetime:
    """将数据库时间转换为 Application 使用的带时区 UTC。"""

    if value is None:
        raise ValueError("必需的 Conversation 时间不能为 NULL")
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _to_optional_utc(value: datetime | None) -> datetime | None:
    """将可选数据库时间转换为带时区 UTC。"""

    return None if value is None else _to_utc(value)


def _encode_cursor(updated_at: datetime, thread_id: UUID) -> str:
    """将稳定排序键编码为不暴露 SQL 的分页 Cursor。"""

    raw = f"{updated_at.isoformat()}|{thread_id}".encode()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    """解析 Thread 列表 Cursor。"""

    if not isinstance(cursor, str) or not cursor:
        raise ConversationValidationError("Thread Cursor 无效")
    try:
        padding = "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(cursor + padding).decode("utf-8")
        timestamp, thread_id = raw.rsplit("|", 1)
        parsed_time = datetime.fromisoformat(timestamp)
        parsed_id = UUID(thread_id)
    except (ValueError, UnicodeError, binascii.Error):
        raise ConversationValidationError("Thread Cursor 无效") from None
    if parsed_time.tzinfo is None or parsed_time.utcoffset() is None:
        raise ConversationValidationError("Thread Cursor 无效")
    return parsed_time, parsed_id


class SqlAlchemyConversationUnitOfWork:
    """Conversation Thread / Turn / Message 的单事务同步适配器。"""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self._pending_turn: ConversationTurn | None = None

    def __enter__(self) -> Self:
        self._session = self._session_factory()
        self._pending_turn = None
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exception, traceback
        if self._session is not None:
            if exception_type is not None:
                self._session.rollback()
            self._session.close()
            self._session = None
            self._pending_turn = None

    @property
    def session(self) -> Session:
        """返回当前事务 Session；上下文结束后不可使用。"""

        if self._session is None:
            raise RuntimeError("Conversation Unit of Work 必须在 with 上下文中使用")
        return self._session

    def get_thread(
        self,
        account_id: UUID,
        thread_id: UUID,
        *,
        for_update: bool = False,
    ) -> ConversationThread | None:
        """按 Account 与 Thread ID 读取 Thread，可选行锁。"""

        statement: Select[tuple[ConversationThreadModel]] = select(ConversationThreadModel).where(
            ConversationThreadModel.account_id == account_id,
            ConversationThreadModel.id == thread_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = self.session.scalar(statement)
        return _to_thread(model) if model is not None else None

    def add_thread(self, thread: ConversationThread) -> None:
        """追加 Account-owned Thread。"""

        self.session.add(
            ConversationThreadModel(
                id=thread.id,
                account_id=thread.account_id,
                title=thread.title,
                revision=thread.revision,
                next_sequence=thread.next_sequence,
                created_at=thread.created_at,
                updated_at=thread.updated_at,
                deleted_at=thread.deleted_at,
            )
        )

    def update_thread(self, thread: ConversationThread) -> None:
        """按 Account Owner 原子更新 Thread 的状态与版本。"""

        result = cast(
            CursorResult[Any],
            self.session.execute(
                update(ConversationThreadModel)
                .where(
                    ConversationThreadModel.id == thread.id,
                    ConversationThreadModel.account_id == thread.account_id,
                )
                .values(
                    title=thread.title,
                    revision=thread.revision,
                    next_sequence=thread.next_sequence,
                    updated_at=thread.updated_at,
                    deleted_at=thread.deleted_at,
                )
            ),
        )
        if result.rowcount != 1:
            raise ConversationThreadNotFound(thread.id)

    def list_threads(
        self,
        account_id: UUID,
        *,
        cursor: str | None,
        limit: int,
    ) -> ConversationThreadPage:
        """按 updated_at / id 倒序读取未删除 Thread，并生成稳定 Cursor。"""

        statement = select(ConversationThreadModel).where(
            ConversationThreadModel.account_id == account_id,
            ConversationThreadModel.deleted_at.is_(None),
        )
        if cursor is not None:
            cursor_time, cursor_id = _decode_cursor(cursor)
            statement = statement.where(
                or_(
                    ConversationThreadModel.updated_at < cursor_time,
                    and_(
                        ConversationThreadModel.updated_at == cursor_time,
                        ConversationThreadModel.id < cursor_id,
                    ),
                )
            )
        statement = statement.order_by(
            ConversationThreadModel.updated_at.desc(),
            ConversationThreadModel.id.desc(),
        ).limit(limit + 1)
        models = list(self.session.scalars(statement))
        has_next = len(models) > limit
        page_models = models[:limit]
        items = tuple(_to_thread(model) for model in page_models)
        next_cursor = (
            _encode_cursor(_to_utc(page_models[-1].updated_at), page_models[-1].id)
            if has_next and page_models
            else None
        )
        return ConversationThreadPage(items, next_cursor)

    def get_turn_by_client_request_id(
        self,
        account_id: UUID,
        thread_id: UUID,
        client_request_id: UUID,
        *,
        for_update: bool = False,
    ) -> ConversationTurn | None:
        """按 Thread Owner 与 Client Request ID 读取幂等 Turn。"""

        statement: Select[tuple[ConversationTurnModel]] = select(ConversationTurnModel).where(
            ConversationTurnModel.account_id == account_id,
            ConversationTurnModel.thread_id == thread_id,
            ConversationTurnModel.client_request_id == client_request_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = self.session.scalar(statement)
        return _to_turn(model) if model is not None else None

    def get_turn(
        self,
        account_id: UUID,
        thread_id: UUID,
        turn_id: UUID,
        *,
        for_update: bool = False,
    ) -> ConversationTurn | None:
        """按 Account、Thread 与 Turn 三重 Owner 条件读取 Turn。"""

        statement: Select[tuple[ConversationTurnModel]] = select(ConversationTurnModel).where(
            ConversationTurnModel.account_id == account_id,
            ConversationTurnModel.thread_id == thread_id,
            ConversationTurnModel.id == turn_id,
        )
        if for_update:
            statement = statement.with_for_update()
        model = self.session.scalar(statement)
        return _to_turn(model) if model is not None else None

    def get_running_turn(
        self,
        account_id: UUID,
        thread_id: UUID,
        *,
        for_update: bool = False,
    ) -> ConversationTurn | None:
        """读取当前 Thread 的唯一 RUNNING Turn。"""

        statement: Select[tuple[ConversationTurnModel]] = select(ConversationTurnModel).where(
            ConversationTurnModel.account_id == account_id,
            ConversationTurnModel.thread_id == thread_id,
            ConversationTurnModel.status == ConversationTurnStatus.RUNNING.value,
        )
        if for_update:
            statement = statement.with_for_update()
        model = self.session.scalar(statement)
        return _to_turn(model) if model is not None else None

    def get_last_turn(self, account_id: UUID, thread_id: UUID) -> ConversationTurn | None:
        """按创建时间与 ID 稳定读取最近 Turn。"""

        statement: Select[tuple[ConversationTurnModel]] = (
            select(ConversationTurnModel)
            .where(
                ConversationTurnModel.account_id == account_id,
                ConversationTurnModel.thread_id == thread_id,
            )
            .order_by(ConversationTurnModel.created_at.desc(), ConversationTurnModel.id.desc())
            .limit(1)
        )
        model = self.session.scalar(statement)
        return _to_turn(model) if model is not None else None

    def get_user_message_for_turn(
        self,
        account_id: UUID,
        thread_id: UUID,
        turn_id: UUID,
    ) -> ConversationMessage | None:
        """读取当前 Owner Turn 的 User Message。"""

        model = self._get_message_model(
            account_id,
            thread_id,
            turn_id,
            ConversationMessageRole.USER,
        )
        return _to_message(model) if model is not None else None

    def get_assistant_message_for_turn(
        self,
        account_id: UUID,
        thread_id: UUID,
        turn_id: UUID,
    ) -> ConversationMessage | None:
        """读取当前 Owner Turn 的 Assistant Message。"""

        model = self._get_message_model(
            account_id,
            thread_id,
            turn_id,
            ConversationMessageRole.ASSISTANT,
        )
        return _to_message(model) if model is not None else None

    def _get_message_model(
        self,
        account_id: UUID,
        thread_id: UUID,
        turn_id: UUID,
        role: ConversationMessageRole,
    ) -> ConversationMessageModel | None:
        statement: Select[tuple[ConversationMessageModel]] = select(ConversationMessageModel).where(
            ConversationMessageModel.account_id == account_id,
            ConversationMessageModel.thread_id == thread_id,
            ConversationMessageModel.turn_id == turn_id,
            ConversationMessageModel.role == role.value,
        )
        return self.session.scalar(statement)

    def add_turn(self, turn: ConversationTurn) -> None:
        """追加 Turn，并在 Message 写入前建立复合外键父记录。"""

        self._pending_turn = turn
        self.session.add(
            ConversationTurnModel(
                id=turn.id,
                thread_id=turn.thread_id,
                account_id=turn.account_id,
                client_request_id=turn.client_request_id,
                status=turn.status.value,
                failure_code=turn.failure_code,
                run_deadline_at=turn.run_deadline_at,
                created_at=turn.created_at,
                completed_at=turn.completed_at,
                warnings=list(turn.warnings),
            )
        )
        try:
            self.session.flush()
        except IntegrityError as error:
            self._raise_turn_conflict(error)

    def update_turn(self, turn: ConversationTurn) -> None:
        """按 Account / Thread / Turn Owner 更新 Turn 状态。"""

        result = cast(
            CursorResult[Any],
            self.session.execute(
                update(ConversationTurnModel)
                .where(
                    ConversationTurnModel.id == turn.id,
                    ConversationTurnModel.thread_id == turn.thread_id,
                    ConversationTurnModel.account_id == turn.account_id,
                )
                .values(
                    client_request_id=turn.client_request_id,
                    status=turn.status.value,
                    failure_code=turn.failure_code,
                    run_deadline_at=turn.run_deadline_at,
                    completed_at=turn.completed_at,
                    warnings=list(turn.warnings),
                )
            ),
        )
        if result.rowcount != 1:
            raise ConversationTurnNotFound(turn.id)

    def add_message(self, message: ConversationMessage) -> None:
        """追加 Message，并在 Source 写入前建立外键父记录。"""

        self.session.add(
            ConversationMessageModel(
                id=message.id,
                thread_id=message.thread_id,
                account_id=message.account_id,
                turn_id=message.turn_id,
                sequence=message.sequence,
                role=message.role.value,
                content=message.content,
                created_at=message.created_at,
            )
        )
        self.session.flush()

    def add_sources(self, sources: Sequence[ConversationSource]) -> None:
        """只保存 Application 已验证的实际 Source Metadata。"""

        self.session.add_all(
            [
                MessageSourceModel(
                    source_id=source.source_id,
                    assistant_message_id=source.assistant_message_id,
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
            ]
        )

    def list_sources_for_message(
        self,
        account_id: UUID,
        thread_id: UUID,
        assistant_message_id: UUID,
    ) -> tuple[ConversationSource, ...]:
        """只读取当前 Account / Thread 的 Assistant Message Sources。"""

        statement = (
            select(MessageSourceModel)
            .join(
                ConversationMessageModel,
                ConversationMessageModel.id == MessageSourceModel.assistant_message_id,
            )
            .where(
                MessageSourceModel.assistant_message_id == assistant_message_id,
                ConversationMessageModel.account_id == account_id,
                ConversationMessageModel.thread_id == thread_id,
                ConversationMessageModel.role == ConversationMessageRole.ASSISTANT.value,
            )
            .order_by(MessageSourceModel.source_id)
        )
        return tuple(_to_source(model) for model in self.session.scalars(statement))

    def list_messages(
        self,
        account_id: UUID,
        thread_id: UUID,
        *,
        before_sequence: int | None,
        limit: int,
    ) -> ConversationMessagePage:
        """读取最近或指定序列之前的消息，并以正序返回给 Context Builder。"""

        statement = select(ConversationMessageModel).where(
            ConversationMessageModel.account_id == account_id,
            ConversationMessageModel.thread_id == thread_id,
        )
        if before_sequence is not None:
            statement = statement.where(ConversationMessageModel.sequence < before_sequence)
        statement = statement.order_by(ConversationMessageModel.sequence.desc()).limit(limit + 1)
        models = list(self.session.scalars(statement))
        has_next = len(models) > limit
        page_models = models[:limit]
        page_models.reverse()
        items = tuple(_to_message(model) for model in page_models)
        next_cursor = str(page_models[0].sequence) if has_next and page_models else None
        return ConversationMessagePage(items, next_cursor)

    def commit(self) -> None:
        """提交事务，并将已知并发约束映射为 Application Conflict。"""

        try:
            self.session.commit()
        except IntegrityError as error:
            self._raise_turn_conflict(error)

    def _raise_turn_conflict(self, error: IntegrityError) -> NoReturn:
        """回滚失败事务，并将已知 Turn 唯一约束映射为稳定冲突。"""

        pending = self._pending_turn
        self.session.rollback()
        constraint_text = str(error.orig)
        if pending is not None and (
            "uq_conversation_turns_client_request" in constraint_text
            or "conversation_turns.client_request_id" in constraint_text
        ):
            raise ConversationIdempotencyConflict(pending.client_request_id) from error
        if pending is not None and (
            "uq_conversation_turns_running_thread" in constraint_text
            or (
                pending.status is ConversationTurnStatus.RUNNING
                and "conversation_turns.thread_id" in constraint_text
                and "client_request_id" not in constraint_text
            )
        ):
            running = self.get_running_turn(
                pending.account_id,
                pending.thread_id,
                for_update=False,
            )
            if running is not None:
                raise ConversationTurnInProgress(running.id) from error
        raise error


class SqlAlchemyConversationUnitOfWorkFactory:
    """为每次 Conversation Application 操作创建独立 UoW。"""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> ConversationUnitOfWork:
        return SqlAlchemyConversationUnitOfWork(self._session_factory)
