"""Conversation SQLAlchemy UoW 的离线行为测试。"""

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Table, create_engine
from sqlalchemy.engine import Engine

from position_pilot.application.conversation_service import (
    ConversationMessage,
    ConversationMessageRole,
    ConversationService,
    ConversationSourceInput,
    ConversationThread,
    ConversationTurn,
    ConversationTurnStatus,
    ConversationValidationError,
)
from position_pilot.database import Base, create_session_factory
from position_pilot.infrastructure.conversation_models import (
    ConversationMessageModel,
    ConversationThreadModel,
    ConversationTurnModel,
    MessageSourceModel,
)
from position_pilot.infrastructure.conversation_unit_of_work import (
    SqlAlchemyConversationUnitOfWorkFactory,
)
from position_pilot.infrastructure.models import AccountModel, UserModel


def _factory() -> tuple[Engine, SqlAlchemyConversationUnitOfWorkFactory, UUID]:
    """创建包含现有 Account Schema 的内存数据库。"""

    engine = create_engine("sqlite:///:memory:")
    tables = [
        cast(Table, UserModel.__table__),
        cast(Table, AccountModel.__table__),
        cast(Table, ConversationThreadModel.__table__),
        cast(Table, ConversationTurnModel.__table__),
        cast(Table, ConversationMessageModel.__table__),
        cast(Table, MessageSourceModel.__table__),
    ]
    Base.metadata.create_all(engine, tables=tables)
    session_factory = create_session_factory(engine)
    account_id = uuid4()
    with session_factory() as session:
        session.add(
            AccountModel(
                id=account_id,
                email=f"conversation-{account_id}@example.com",
                display_name="Conversation Test",
                password_hash="test-hash",
                portfolio_user_id=None,
                created_at=datetime.now(UTC),
            )
        )
        session.commit()
    return engine, SqlAlchemyConversationUnitOfWorkFactory(session_factory), account_id


def test_service_persists_bounded_messages_and_sources() -> None:
    """Service 应恢复最近消息、Assistant Source，并保持 Message 序列稳定。"""

    engine, factory, account_id = _factory()
    service = ConversationService(factory)
    thread = service.start_thread(account_id)
    request_id = uuid4()
    started = service.start_turn(
        account_id,
        thread.id,
        portfolio_user_id=uuid4(),
        question="分析 GOOG",
        client_request_id=request_id,
        expected_thread_revision=0,
    )
    completed = service.complete_turn(
        account_id,
        thread.id,
        started.turn.id,
        answer="当前回答",
        sources=(
            ConversationSourceInput(
                source_type="QUOTE",
                provider="FIXTURE",
                provider_reference="quote:GOOG",
                url=None,
                title=None,
                publisher=None,
                published_at=None,
                event_time=None,
                fetched_at=datetime.now(UTC),
                content_scope="STRUCTURED_FACT",
                status="SUCCESS",
            ),
        ),
    )

    # Service 会为 Source 生成实际 Assistant Message ID；输入 ID 不应被写入。
    assert completed.assistant_message is not None
    assert completed.sources[0].assistant_message_id == completed.assistant_message.id
    assert completed.sources[0].assistant_message_id != completed.user_message.id
    history = service.history(account_id, thread.id, limit=20)
    assert [message.role for message in history.messages] == [
        ConversationMessageRole.USER,
        ConversationMessageRole.ASSISTANT,
    ]
    assert [message.sequence for message in history.messages] == [1, 2]
    assert history.thread.revision == 2
    with factory() as unit_of_work:
        sources = unit_of_work.list_sources_for_message(
            account_id,
            thread.id,
            completed.assistant_message.id,
        )
    assert len(sources) == 1
    assert sources[0].provider_reference == "quote:GOOG"
    engine.dispose()


def test_uow_enforces_owner_and_returns_recent_messages_in_sequence_order() -> None:
    """查询必须带 Account Owner，分页读取最近消息后仍按正序返回。"""

    engine, factory, account_id = _factory()
    other_account = uuid4()
    now = datetime.now(UTC)
    thread = ConversationThread(
        id=uuid4(),
        account_id=account_id,
        title="Test",
        revision=0,
        next_sequence=4,
        created_at=now,
        updated_at=now,
    )
    turns = tuple(
        ConversationTurn(
            id=uuid4(),
            thread_id=thread.id,
            account_id=account_id,
            client_request_id=uuid4(),
            status=ConversationTurnStatus.COMPLETED,
            failure_code=None,
            run_deadline_at=None,
            created_at=now + timedelta(seconds=turn_number),
            completed_at=now + timedelta(seconds=turn_number),
        )
        for turn_number in range(1, 4)
    )
    messages = tuple(
        ConversationMessage(
            id=uuid4(),
            thread_id=thread.id,
            account_id=account_id,
            turn_id=turn.id,
            sequence=sequence,
            role=ConversationMessageRole.USER,
            content=f"message-{sequence}",
            created_at=now + timedelta(seconds=sequence),
        )
        for sequence, turn in enumerate(turns, start=1)
    )
    with factory() as unit_of_work:
        unit_of_work.add_thread(thread)
        for turn in turns:
            unit_of_work.add_turn(turn)
        for message in messages:
            unit_of_work.add_message(message)
        unit_of_work.commit()
        assert unit_of_work.get_thread(other_account, thread.id) is None
        assert [
            message.sequence
            for message in unit_of_work.list_messages(
                account_id,
                thread.id,
                before_sequence=None,
                limit=2,
            ).items
        ] == [2, 3]
        assert [
            message.sequence
            for message in unit_of_work.list_messages(
                account_id,
                thread.id,
                before_sequence=3,
                limit=2,
            ).items
        ] == [1, 2]
    engine.dispose()


def test_thread_cursor_uses_updated_at_and_id_as_stable_order() -> None:
    """相同更新时间也必须由 Thread ID 形成稳定 Cursor。"""

    engine, factory, account_id = _factory()
    now = datetime.now(UTC)
    with factory() as unit_of_work:
        for _ in range(3):
            unit_of_work.add_thread(
                ConversationThread(
                    id=uuid4(),
                    account_id=account_id,
                    title=None,
                    revision=0,
                    next_sequence=1,
                    created_at=now,
                    updated_at=now,
                )
            )
        unit_of_work.commit()
        first_page = unit_of_work.list_threads(account_id, cursor=None, limit=1)
        second_page = unit_of_work.list_threads(
            account_id,
            cursor=first_page.next_cursor,
            limit=2,
        )
    assert first_page.next_cursor is not None
    assert len(first_page.items) == 1
    assert len(second_page.items) == 2
    assert set(item.id for item in first_page.items).isdisjoint(
        item.id for item in second_page.items
    )
    engine.dispose()


def test_invalid_thread_cursor_is_rejected_before_query() -> None:
    """Cursor 不能被客户端任意伪造为 SQL 条件。"""

    engine, factory, account_id = _factory()
    with factory() as unit_of_work:
        with pytest.raises(ConversationValidationError, match="Thread Cursor 无效"):
            unit_of_work.list_threads(account_id, cursor="not-a-cursor", limit=20)
    engine.dispose()
