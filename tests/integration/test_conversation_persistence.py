"""Conversation PostgreSQL Migration / UoW 集成测试。"""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, inspect, select

from position_pilot.application.conversation_service import (
    ConversationRevisionConflict,
    ConversationService,
    ConversationSourceInput,
    ConversationTurnInProgress,
)
from position_pilot.database import create_database_engine, create_session_factory
from position_pilot.infrastructure.conversation_models import (
    ConversationMessageModel,
    ConversationThreadModel,
    ConversationTurnModel,
    MessageSourceModel,
)
from position_pilot.infrastructure.conversation_unit_of_work import (
    SqlAlchemyConversationUnitOfWorkFactory,
)
from position_pilot.infrastructure.models import AccountModel

pytestmark = pytest.mark.integration


def _test_database_url() -> str:
    """只使用调用方显式提供的 PostgreSQL 测试数据库。"""

    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("需要 TEST_DATABASE_URL 才能运行 Conversation PostgreSQL 集成测试")
    return value


def test_conversation_uow_recovers_account_owned_turn_and_source() -> None:
    """真实 PostgreSQL 应恢复 Thread、Turn、Message 与 Source Metadata。"""

    engine = create_database_engine(_test_database_url())
    if not inspect(engine).has_table("conversation_threads"):
        engine.dispose()
        pytest.skip("测试数据库尚未执行 Alembic 0010")
    session_factory = create_session_factory(engine)
    account_id = uuid4()
    email = f"conversation-{account_id}@example.com"
    with session_factory() as session:
        session.add(
            AccountModel(
                id=account_id,
                email=email,
                display_name="Conversation Integration",
                password_hash="test-hash",
                portfolio_user_id=None,
                created_at=datetime.now(UTC),
            )
        )
        session.commit()

    service = ConversationService(SqlAlchemyConversationUnitOfWorkFactory(session_factory))
    thread = None
    try:
        thread = service.start_thread(account_id)
        started = service.start_turn(
            account_id,
            thread.id,
            portfolio_user_id=uuid4(),
            question="分析 GOOG",
            client_request_id=uuid4(),
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
                    content_scope="STRUCTURED_FACT",
                    status="SUCCESS",
                ),
            ),
            warnings=("USAGE_NOT_REPORTED",),
        )
        assert completed.assistant_message is not None

        recovered = ConversationService(
            SqlAlchemyConversationUnitOfWorkFactory(create_session_factory(engine))
        )
        history = recovered.history(account_id, thread.id)
        assert [message.content for message in history.messages] == ["分析 GOOG", "当前回答"]
        assert history.messages[1].role.value == "ASSISTANT"
        assert recovered.get_thread(account_id, thread.id).last_turn.warnings == (
            "USAGE_NOT_REPORTED",
        )
        with create_session_factory(engine)() as session:
            source_count = session.scalar(
                select(MessageSourceModel.source_id).where(
                    MessageSourceModel.assistant_message_id == completed.assistant_message.id,
                )
            )
            assert source_count is not None
    finally:
        with engine.begin() as connection:
            if thread is not None:
                connection.execute(
                    delete(MessageSourceModel).where(
                        MessageSourceModel.assistant_message_id.in_(
                            select(ConversationMessageModel.id).where(
                                ConversationMessageModel.thread_id == thread.id
                            )
                        )
                    )
                )
                connection.execute(
                    delete(ConversationMessageModel).where(
                        ConversationMessageModel.thread_id == thread.id
                    )
                )
                connection.execute(
                    delete(ConversationTurnModel).where(
                        ConversationTurnModel.thread_id == thread.id
                    )
                )
                connection.execute(
                    delete(ConversationThreadModel).where(ConversationThreadModel.id == thread.id)
                )
            connection.execute(delete(AccountModel).where(AccountModel.id == account_id))
        engine.dispose()


def test_concurrent_append_allows_only_one_running_turn() -> None:
    """相同 revision 的并发提交只能创建一个 User Message 与 RUNNING Turn。"""

    engine = create_database_engine(_test_database_url())
    if not inspect(engine).has_table("conversation_threads"):
        engine.dispose()
        pytest.skip("测试数据库尚未执行 Alembic 0010")
    session_factory = create_session_factory(engine)
    account_id = uuid4()
    with session_factory() as session:
        session.add(
            AccountModel(
                id=account_id,
                email=f"conversation-concurrent-{account_id}@example.com",
                display_name="Conversation Concurrent",
                password_hash="test-hash",
                portfolio_user_id=None,
                created_at=datetime.now(UTC),
            )
        )
        session.commit()
    service = ConversationService(SqlAlchemyConversationUnitOfWorkFactory(session_factory))
    thread = service.start_thread(account_id)
    barrier = Barrier(2)

    def append(question: str) -> object:
        barrier.wait(timeout=5)
        return service.start_turn(
            account_id,
            thread.id,
            portfolio_user_id=uuid4(),
            question=question,
            client_request_id=uuid4(),
            expected_thread_revision=0,
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(append, "并发问题 A"),
                executor.submit(append, "并发问题 B"),
            ]
            outcomes: list[object] = []
            for future in futures:
                try:
                    outcomes.append(future.result(timeout=10))
                except (ConversationRevisionConflict, ConversationTurnInProgress) as error:
                    outcomes.append(error)

        assert (
            sum(
                not isinstance(item, (ConversationRevisionConflict, ConversationTurnInProgress))
                for item in outcomes
            )
            == 1
        )
        with session_factory() as session:
            turn_count = session.scalar(
                select(func.count())
                .select_from(ConversationTurnModel)
                .where(
                    ConversationTurnModel.thread_id == thread.id,
                )
            )
            message_count = session.scalar(
                select(func.count())
                .select_from(ConversationMessageModel)
                .where(
                    ConversationMessageModel.thread_id == thread.id,
                )
            )
        assert turn_count == 1
        assert message_count == 1
    finally:
        with engine.begin() as connection:
            connection.execute(
                delete(ConversationMessageModel).where(
                    ConversationMessageModel.thread_id == thread.id
                )
            )
            connection.execute(
                delete(ConversationTurnModel).where(ConversationTurnModel.thread_id == thread.id)
            )
            connection.execute(
                delete(ConversationThreadModel).where(ConversationThreadModel.id == thread.id)
            )
            connection.execute(delete(AccountModel).where(AccountModel.id == account_id))
        engine.dispose()
