"""真实 SQLite UoW 验证意图确认、scope 隔离与 Conversation 原子提交。"""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from position_pilot.application.strategy_service import StrategyError, StrategyService
from position_pilot.domain.portfolio import PositionType
from position_pilot.domain.strategy import (
    CandidateStatus,
    PositionPlanPayload,
    StrategyScope,
    StrategyVersionStatus,
)
from position_pilot.infrastructure.strategy_models import (
    StrategyCandidateModel,
    StrategyVersionModel,
)
from position_pilot.infrastructure.strategy_unit_of_work import SqlAlchemyStrategyUnitOfWorkFactory

from .support import NOW, QUESTION, Store, confirm, draft, propose


def test_active_and_pending_coexist_and_atomic_supersede(store: Store) -> None:
    conversations, strategies, factory, owner = store
    first = propose(conversations, owner)
    assert strategies.active(owner) == ()
    first_version = confirm(strategies, owner, first)
    second = propose(conversations, owner, draft(payload={"target_budget": "500"}))
    assert second.base_version == 1
    assert strategies.active(owner) == (first_version,)
    assert strategies.pending(owner) == (second,)
    second_version = confirm(strategies, owner, second)
    assert second_version.version == 2
    assert isinstance(second_version.payload, PositionPlanPayload)
    assert second_version.payload.target_budget == Decimal("500")
    assert strategies.active(owner) == (second_version,)
    with factory() as session:
        rows = tuple(
            session.scalars(select(StrategyVersionModel).order_by(StrategyVersionModel.version))
        )
        assert [r.status for r in rows] == ["SUPERSEDED", "ACTIVE"]
        assert (
            session.scalar(
                select(func.count())
                .select_from(StrategyCandidateModel)
                .where(StrategyCandidateModel.status == "PENDING")
            )
            == 0
        )


def test_pending_unique_but_different_scope_and_kind_independent(store: Store) -> None:
    conversations, strategies, _, owner = store
    first = propose(conversations, owner)
    with pytest.raises(StrategyError, match="待确认") as error:
        propose(conversations, owner)
    assert error.value.code == "STRATEGY_CANDIDATE_CONFLICT"
    swing = propose(conversations, owner, draft(scope={"ticker": "GOOG", "position_type": "SWING"}))
    thesis = propose(
        conversations,
        owner,
        draft(kind="INVESTMENT_THESIS_V1", payload={"thesis_text": "长期业务假设"}),
    )
    assert {c.id for c in strategies.pending(owner)} == {first.id, swing.id, thesis.id}
    confirm(strategies, owner, first)
    confirm(strategies, owner, swing)
    confirm(strategies, owner, thesis)
    assert len(strategies.active(owner)) == 3
    assert {v.scope.position_type for v in strategies.active(owner, "GOOG:SWING")} == {
        PositionType.SWING
    }


def test_confirm_idempotency_and_old_revision_conflict(store: Store) -> None:
    conversations, strategies, _, owner = store
    candidate = propose(conversations, owner)
    request_id = uuid4()
    version = confirm(strategies, owner, candidate, request_id)
    assert confirm(strategies, owner, candidate, request_id) == version
    with pytest.raises(StrategyError):
        confirm(strategies, owner, candidate)
    second = propose(conversations, owner)
    with pytest.raises(StrategyError):
        confirm(strategies, owner, second, request_id)
    assert strategies.active(owner) == (version,)


def test_replace_cancel_expiry_and_owner(store: Store) -> None:
    conversations, strategies, factory, owner = store
    first = propose(conversations, owner)
    replacement = propose(
        conversations,
        owner,
        draft(replaces_candidate_id=first.id, replaces_candidate_revision=first.candidate_revision),
    )
    assert strategies.get(owner, first.id).status is CandidateStatus.CANCELLED
    strategies.cancel(owner, replacement.id, candidate_revision=1)
    assert (
        strategies.cancel(owner, replacement.id, candidate_revision=1).status
        is CandidateStatus.CANCELLED
    )
    expired = propose(conversations, owner)
    later = StrategyService(
        SqlAlchemyStrategyUnitOfWorkFactory(factory), clock=lambda: NOW + timedelta(hours=24)
    )
    assert later.get(owner, expired.id).status is CandidateStatus.EXPIRED
    assert later.pending(owner) == ()
    with pytest.raises(StrategyError):
        confirm(later, owner, expired)
    with pytest.raises(StrategyError) as error:
        strategies.get(uuid4(), expired.id)
    assert error.value.code == "STRATEGY_NOT_FOUND"


def test_invalidation_and_thread_delete_do_not_revive_confirmed_state(store: Store) -> None:
    conversations, strategies, _, owner = store
    first = propose(conversations, owner)
    version = confirm(strategies, owner, first)
    pending = propose(conversations, owner)
    conversations.delete_thread(owner, pending.thread_id)
    assert strategies.active(owner) == (version,)
    assert strategies.pending(owner) == ()
    with pytest.raises(StrategyError):
        confirm(strategies, owner, pending)
    invalidation = propose(conversations, owner, draft(operation="INVALIDATE", payload=None))
    invalidated = confirm(strategies, owner, invalidation)
    assert invalidated.status is StrategyVersionStatus.INVALIDATED
    assert strategies.active(owner) == ()
    fresh = propose(conversations, owner)
    assert fresh.base_version == 2


def test_invalid_provenance_rolls_back_assistant_and_candidate(store: Store) -> None:
    conversations, strategies, _, owner = store
    thread = conversations.start_thread(owner)
    started = conversations.start_turn(
        owner,
        thread.id,
        portfolio_user_id=uuid4(),
        question=QUESTION,
        client_request_id=uuid4(),
        expected_thread_revision=0,
    )
    with pytest.raises(StrategyError):
        conversations.complete_turn(
            owner,
            thread.id,
            started.turn.id,
            answer="草案",
            strategy_draft=draft(evidence_quote="Assistant 自己建议的计划"),
        )
    history = conversations.history(owner, thread.id)
    assert len(history.messages) == 1
    assert history.messages[0].role.value == "USER"
    assert strategies.pending(owner) == ()


@pytest.mark.parametrize(
    "field",
    [
        "remaining_target_budget",
        "shares",
        "average_cost",
        "current_price",
        "tranche",
        "price_trigger",
    ],
)
def test_derived_and_recommendation_fields_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        draft(payload={"target_budget": "300", field: "123"})


def test_scope_and_typed_payload_validation() -> None:
    assert (
        StrategyScope(ticker="goog", position_type=PositionType.LONG_TERM).key == "GOOG:LONG_TERM"
    )
    with pytest.raises(ValidationError):
        StrategyScope.model_validate({"ticker": "GOOG", "position_type": "UNSPECIFIED"})
    schema = StrategyScope.model_json_schema()
    assert schema["properties"]["position_type"]["enum"] == ["LONG_TERM", "SWING"]
    with pytest.raises(ValidationError):
        draft(kind="HOLDING_HORIZON_V1", payload={"target_budget": "300"})
    with pytest.raises(ValidationError):
        draft(kind="HOLDING_HORIZON_V1", payload={"horizon_category": "UNTIL_DATE"})


def test_database_enforces_pending_uniqueness(store: Store) -> None:
    conversations, _, factory, owner = store
    candidate = propose(conversations, owner)
    thread = conversations.start_thread(owner)
    turn = conversations.start_turn(
        owner,
        thread.id,
        portfolio_user_id=uuid4(),
        question=QUESTION,
        client_request_id=uuid4(),
        expected_thread_revision=0,
    )
    completed = conversations.complete_turn(owner, thread.id, turn.turn.id, answer="普通回答")
    assert completed.assistant_message is not None
    with factory() as session:
        original = session.get(StrategyCandidateModel, candidate.id)
        assert original is not None
        values = {
            column.name: getattr(original, column.name)
            for column in StrategyCandidateModel.__table__.columns
        }
        values.update(
            id=uuid4(),
            thread_id=thread.id,
            source_user_message_id=turn.user_message.id,
            assistant_message_id=completed.assistant_message.id,
            proposal_request_id=uuid4(),
        )
        # 两个来源均合法，只验证独立 PENDING 唯一约束。
        session.add(StrategyCandidateModel(**values))
        with pytest.raises(
            IntegrityError,
            match=(
                "strategy_candidates.account_id, strategy_candidates.scope_key, "
                "strategy_candidates.kind"
            ),
        ):
            session.commit()


def test_candidate_history_recovery_and_confirmed_thread_deletion(store: Store) -> None:
    conversations, strategies, _, owner = store
    candidate = propose(conversations, owner)
    assert conversations.history(owner, candidate.thread_id).answers[0].candidate == candidate
    version = confirm(strategies, owner, candidate)
    recovered = conversations.history(owner, candidate.thread_id).answers[0].candidate
    assert recovered is not None and recovered.status is CandidateStatus.CONFIRMED
    conversations.delete_thread(owner, candidate.thread_id)
    assert strategies.active(owner) == (version,)


def test_failed_confirmation_keeps_old_active_and_pending(store: Store) -> None:
    conversations, strategies, _, owner = store
    active = confirm(strategies, owner, propose(conversations, owner))
    pending = propose(conversations, owner, draft(payload={"target_budget": "500"}))
    with pytest.raises(StrategyError):
        strategies.confirm(
            owner, pending.id, candidate_revision=1, base_version=0, client_request_id=uuid4()
        )
    assert strategies.active(owner) == (active,)
    assert strategies.pending(owner) == (pending,)


def test_invalid_financial_and_background_payloads() -> None:
    with pytest.raises(ValidationError):
        draft(payload={"target_budget": True})
    with pytest.raises(ValidationError):
        draft(kind="INVESTMENT_THESIS_V1", payload={"thesis_text": "   "})


def test_deleted_source_conflict_and_stale_candidate_cannot_confirm(store: Store) -> None:
    conversations, strategies, factory, owner = store
    candidate = propose(conversations, owner)
    conversations.delete_thread(owner, candidate.thread_id)
    with pytest.raises(StrategyError) as error:
        confirm(strategies, owner, candidate)
    assert error.value.code == "STRATEGY_CONFLICT"
    stale = propose(conversations, owner)
    with factory() as session:
        from position_pilot.infrastructure.strategy_repository import SqlAlchemyStrategyRepository

        SqlAlchemyStrategyRepository(session).save_candidate(
            stale.model_copy(update={"status": CandidateStatus.STALE})
        )
        session.commit()
    assert strategies.pending(owner) == ()
    assert strategies.active(owner) == ()
    with pytest.raises(StrategyError) as error:
        confirm(strategies, owner, stale)
    assert error.value.code == "STRATEGY_CONFLICT"
