"""独立 PostgreSQL 验证 scope 锁、并发确认和数据库唯一性。"""

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from position_pilot.application.conversation_service import ConversationService
from position_pilot.application.strategy_service import StrategyError, StrategyService
from position_pilot.database import create_database_engine, create_session_factory
from position_pilot.domain.portfolio import PositionType
from position_pilot.domain.strategy import (
    StrategyCandidate,
    StrategyDraft,
    StrategyKind,
    StrategyScope,
    StrategyVersion,
)
from position_pilot.infrastructure.conversation_models import (
    ConversationMessageModel,
    ConversationThreadModel,
    ConversationTurnModel,
    MessageSourceModel,
)
from position_pilot.infrastructure.conversation_unit_of_work import (
    SqlAlchemyConversationUnitOfWorkFactory,
    conversation_strategy_repository,
)
from position_pilot.infrastructure.models import AccountModel
from position_pilot.infrastructure.strategy_models import (
    StrategyCandidateModel,
    StrategyIdentityModel,
    StrategyVersionModel,
)
from position_pilot.infrastructure.strategy_repository import SqlAlchemyStrategyRepository
from position_pilot.infrastructure.strategy_unit_of_work import SqlAlchemyStrategyUnitOfWorkFactory

pytestmark = pytest.mark.integration
NOW = datetime(2026, 10, 4, tzinfo=UTC)
QUESTION = "请持续记住 GOOG 长期仓的目标配置 300 美元"
Store = tuple[ConversationService, StrategyService, sessionmaker[Session], UUID]


@pytest.fixture
def store() -> Iterator[Store]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("需要显式 TEST_DATABASE_URL 与 Migration 0011")
    engine = create_database_engine(url)
    assert inspect(engine).has_table("strategy_identities")
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
    yield (
        ConversationService(
            SqlAlchemyConversationUnitOfWorkFactory(factory),
            clock=lambda: NOW,
            strategy_repository_factory=conversation_strategy_repository,
        ),
        StrategyService(SqlAlchemyStrategyUnitOfWorkFactory(factory), clock=lambda: NOW),
        factory,
        owner,
    )
    with factory() as session:
        session.execute(
            delete(MessageSourceModel).where(
                MessageSourceModel.assistant_message_id.in_(
                    select(ConversationMessageModel.id).where(
                        ConversationMessageModel.account_id == owner
                    )
                )
            )
        )
        for model in (
            StrategyVersionModel,
            StrategyCandidateModel,
            StrategyIdentityModel,
            ConversationMessageModel,
            ConversationTurnModel,
            ConversationThreadModel,
        ):
            session.execute(delete(model).where(model.account_id == owner))
        session.execute(delete(AccountModel).where(AccountModel.id == owner))
        session.commit()
    engine.dispose()


def propose(
    service: ConversationService, owner: UUID, position_type: str = "LONG_TERM"
) -> StrategyCandidate:
    thread = service.start_thread(owner)
    started = service.start_turn(
        owner,
        thread.id,
        portfolio_user_id=uuid4(),
        question=QUESTION,
        client_request_id=uuid4(),
        expected_thread_revision=0,
    )
    draft = StrategyDraft.model_validate(
        {
            "operation": "UPSERT",
            "scope": {"ticker": "GOOG", "position_type": position_type},
            "kind": "POSITION_PLAN_V1",
            "payload": {"target_budget": "300"},
            "origin": "USER_STATED_INTENT",
            "evidence_quote": QUESTION,
        }
    )
    result = service.complete_turn(
        owner, thread.id, started.turn.id, answer="待确认草案", strategy_draft=draft
    )
    assert result.candidate is not None
    return result.candidate


def confirm(
    service: StrategyService, owner: UUID, candidate: StrategyCandidate, request_id: UUID
) -> StrategyVersion:
    return service.confirm(
        owner,
        candidate.id,
        candidate_revision=1,
        base_version=candidate.base_version,
        client_request_id=request_id,
    )


def test_same_scope_concurrent_proposal_and_confirm(store: Store) -> None:
    conversations, strategies, _, owner = store
    barrier = Barrier(2)

    def create() -> StrategyCandidate | StrategyError:
        barrier.wait(timeout=5)
        try:
            return propose(conversations, owner)
        except StrategyError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: create(), range(2)))
    candidates = [r for r in results if isinstance(r, StrategyCandidate)]
    assert len(candidates) == 1
    assert [r.code for r in results if isinstance(r, StrategyError)] == [
        "STRATEGY_CANDIDATE_CONFLICT"
    ]
    candidate = candidates[0]
    request_id = uuid4()
    with ThreadPoolExecutor(max_workers=2) as pool:
        versions = list(
            pool.map(lambda _: confirm(strategies, owner, candidate, request_id), range(2))
        )
    assert versions[0] == versions[1]
    assert strategies.active(owner) == (versions[0],)


def test_different_scope_is_not_blocked_by_long_term_lock(store: Store) -> None:
    conversations, _, factory, owner = store
    propose(conversations, owner)
    with factory() as session, ThreadPoolExecutor(max_workers=1) as pool:
        repo = SqlAlchemyStrategyRepository(session)
        repo.lock_identity(
            owner,
            StrategyScope(ticker="GOOG", position_type=PositionType.LONG_TERM),
            StrategyKind.POSITION_PLAN_V1,
        )
        swing = pool.submit(propose, conversations, owner, "SWING").result(timeout=5)
        assert swing.scope.position_type is PositionType.SWING


def test_parallel_cross_scope_request_id_conflict_is_atomic(store: Store) -> None:
    conversations, strategies, _, owner = store
    for position_type in ("LONG_TERM", "SWING"):
        confirm(strategies, owner, propose(conversations, owner, position_type), uuid4())
    candidates = [propose(conversations, owner), propose(conversations, owner, "SWING")]
    barrier = Barrier(2)
    request_id = uuid4()

    def attempt(candidate: StrategyCandidate) -> StrategyVersion | StrategyError:
        barrier.wait(timeout=5)
        try:
            return confirm(strategies, owner, candidate, request_id)
        except StrategyError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, candidates))
    assert len([r for r in results if isinstance(r, StrategyVersion)]) == 1
    assert [r.code for r in results if isinstance(r, StrategyError)] == ["STRATEGY_CONFLICT"]
    assert len(strategies.active(owner)) == 2
    assert len(strategies.pending(owner)) == 1
    assert sorted(v.version for v in strategies.active(owner)) == [1, 2]


def test_database_active_uniqueness_with_valid_candidate_fk(store: Store) -> None:
    conversations, strategies, factory, owner = store
    first = confirm(strategies, owner, propose(conversations, owner), uuid4())
    pending = propose(conversations, owner)
    with factory() as session:
        row = session.get(StrategyVersionModel, first.id)
        assert row is not None
        values = {
            column.name: getattr(row, column.name)
            for column in StrategyVersionModel.__table__.columns
        }
        values.update(
            id=uuid4(), version=2, source_candidate_id=pending.id, confirmation_request_id=uuid4()
        )
        session.add(StrategyVersionModel(**values))
        with pytest.raises(IntegrityError) as error:
            session.commit()
        assert (
            getattr(getattr(error.value.orig, "diag", None), "constraint_name", None)
            == "uq_strategy_active_scope"
        )
    assert strategies.active(owner) == (first,)
    assert strategies.pending(owner) == (pending,)


def test_delete_thread_and_confirm_have_consistent_lock_order(store: Store) -> None:
    conversations, strategies, _, owner = store
    candidate = propose(conversations, owner)
    barrier = Barrier(2)

    def remove() -> None:
        barrier.wait(timeout=5)
        conversations.delete_thread(owner, candidate.thread_id)

    def resolve() -> StrategyVersion | StrategyError:
        barrier.wait(timeout=5)
        try:
            return confirm(strategies, owner, candidate, uuid4())
        except StrategyError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        deletion = pool.submit(remove)
        confirmation = pool.submit(resolve)
        deletion.result(timeout=5)
        result = confirmation.result(timeout=5)
    assert strategies.pending(owner) == ()
    if isinstance(result, StrategyError):
        assert result.code == "STRATEGY_CONFLICT"
        assert strategies.active(owner) == ()
    else:
        assert strategies.active(owner) == (result,)
    with pytest.raises(StrategyError) as error:
        strategies.get(owner, candidate.id)
    assert error.value.code == "STRATEGY_NOT_FOUND"
