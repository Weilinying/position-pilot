"""真实 SQLite UoW 验证意图确认、scope 隔离与 Conversation 原子提交。"""

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from position_pilot.application.conversation_service import ConversationService
from position_pilot.application.strategy_service import StrategyService
from position_pilot.database import Base, create_session_factory
from position_pilot.domain.strategy import (
    StrategyCandidate,
    StrategyDraft,
    StrategyVersion,
)
from position_pilot.infrastructure.conversation_unit_of_work import (
    SqlAlchemyConversationUnitOfWorkFactory,
    conversation_strategy_repository,
)
from position_pilot.infrastructure.models import AccountModel
from position_pilot.infrastructure.strategy_unit_of_work import SqlAlchemyStrategyUnitOfWorkFactory

Store = tuple[ConversationService, StrategyService, sessionmaker[Session], UUID]

NOW = datetime(2026, 10, 4, tzinfo=UTC)
QUESTION = "请持续记住 GOOG 长期仓的目标资本配置 300 美元"


@pytest.fixture
def store() -> Iterator[tuple[ConversationService, StrategyService, sessionmaker[Session], UUID]]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection: object, record: object) -> None:
        from sqlite3 import Connection

        assert isinstance(connection, Connection)
        connection.execute("PRAGMA foreign_keys=ON")

    names = (
        "users",
        "accounts",
        "conversation_threads",
        "conversation_turns",
        "conversation_messages",
        "message_sources",
        "strategy_identities",
        "strategy_candidates",
        "confirmed_strategy_versions",
    )
    Base.metadata.create_all(engine, tables=[Base.metadata.tables[name] for name in names])
    factory = create_session_factory(engine)
    owner = uuid4()
    with factory() as session:
        session.add(
            AccountModel(
                id=owner,
                email=f"{owner}@example.test",
                display_name="T6",
                password_hash="fixture-hash",
                created_at=NOW,
            )
        )
        session.commit()
    conversations = ConversationService(
        SqlAlchemyConversationUnitOfWorkFactory(factory),
        clock=lambda: NOW,
        strategy_repository_factory=conversation_strategy_repository,
    )
    strategies = StrategyService(SqlAlchemyStrategyUnitOfWorkFactory(factory), clock=lambda: NOW)
    yield conversations, strategies, factory, owner
    engine.dispose()


def draft(**changes: object) -> StrategyDraft:
    payload: dict[str, object] = {
        "operation": "UPSERT",
        "scope": {"ticker": "goog", "position_type": "LONG_TERM"},
        "kind": "POSITION_PLAN_V1",
        "payload": {"target_budget": "300"},
        "origin": "USER_STATED_INTENT",
        "evidence_quote": QUESTION,
    }
    return StrategyDraft.model_validate({**payload, **changes})


def propose(
    conversations: ConversationService, owner: UUID, value: StrategyDraft | None = None
) -> StrategyCandidate:
    thread = conversations.start_thread(owner)
    started = conversations.start_turn(
        owner,
        thread.id,
        portfolio_user_id=uuid4(),
        question=QUESTION,
        client_request_id=uuid4(),
        expected_thread_revision=0,
    )
    completed = conversations.complete_turn(
        owner,
        thread.id,
        started.turn.id,
        answer="请核对持续意图草案；尚未生效。",
        strategy_draft=value or draft(),
    )
    assert completed.candidate is not None
    return completed.candidate


def confirm(
    strategies: StrategyService,
    owner: UUID,
    candidate: StrategyCandidate,
    request_id: UUID | None = None,
) -> StrategyVersion:
    return strategies.confirm(
        owner,
        candidate.id,
        candidate_revision=candidate.candidate_revision,
        base_version=candidate.base_version,
        client_request_id=request_id or uuid4(),
    )
