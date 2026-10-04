"""在独立临时数据库验证 0011 不改变旧账本与 Conversation 数据。"""

import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from pydantic import PostgresDsn
from sqlalchemy import create_engine, inspect, select

import position_pilot.database as database
from position_pilot.application.conversation_service import ConversationService
from position_pilot.application.strategy_service import StrategyService
from position_pilot.config import Settings
from position_pilot.database import create_session_factory
from position_pilot.domain.strategy import StrategyDraft
from position_pilot.infrastructure.conversation_unit_of_work import (
    SqlAlchemyConversationUnitOfWorkFactory,
    conversation_strategy_repository,
)
from position_pilot.infrastructure.models import AccountModel, TransactionModel, UserModel
from position_pilot.infrastructure.strategy_unit_of_work import SqlAlchemyStrategyUnitOfWorkFactory

pytestmark = pytest.mark.integration


def test_additive_0011_preserves_existing_ledger_and_conversation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url or os.environ.get("RUN_STRATEGY_MIGRATION_TEST") != "1":
        pytest.skip(
            "需要显式 TEST_DATABASE_URL 和 RUN_STRATEGY_MIGRATION_TEST=1，且允许新建临时数据库"
        )
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    name = f"p4_t6_migration_{uuid4().hex}"
    with admin.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
    trial_url = admin.url.set(database=name).render_as_string(hide_password=False)
    trial = create_engine(trial_url)
    factory = create_session_factory(trial)
    now = datetime(2026, 10, 4, tzinfo=UTC)
    owner, user_id, transaction_id = uuid4(), uuid4(), uuid4()
    # 显式禁止 dotenv；临时数据库独立于调用方现有测试数据库和正式数据库。
    settings = Settings.model_construct(database_url=PostgresDsn(trial_url))
    monkeypatch.setattr(database, "get_settings", lambda: settings)
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    try:
        command.upgrade(config, "20260922_0010")
        with factory() as session:
            session.add(
                UserModel(
                    id=user_id,
                    display_name="Fixture Ledger",
                    initial_cash=Decimal("1000"),
                    created_at=now,
                )
            )
            session.flush()
            session.add(
                AccountModel(
                    id=owner,
                    email=f"{owner}@example.test",
                    display_name="Fixture",
                    password_hash="fixture-hash",
                    portfolio_user_id=user_id,
                    created_at=now,
                )
            )
            session.add(
                TransactionModel(
                    id=transaction_id,
                    user_id=user_id,
                    sequence=1,
                    ticker="GOOG",
                    action="BUY",
                    price=Decimal("100"),
                    shares=Decimal("2"),
                    amount=Decimal("200"),
                    commission=Decimal("0"),
                    fee_schedule="BUY_COST_INCLUDED",
                    position_type="LONG_TERM",
                    occurred_at=now,
                    reason=None,
                )
            )
            session.commit()
        conversations = ConversationService(SqlAlchemyConversationUnitOfWorkFactory(factory))
        thread = conversations.start_thread(owner)
        turn = conversations.start_turn(
            owner,
            thread.id,
            portfolio_user_id=user_id,
            question="查看持仓",
            client_request_id=uuid4(),
            expected_thread_revision=0,
        )
        conversations.complete_turn(owner, thread.id, turn.turn.id, answer="已有成功回答。")
        before_history = conversations.history(owner, thread.id)
        with trial.connect() as connection:
            before = connection.execute(select(TransactionModel.__table__)).mappings().all()
            before_user = connection.execute(select(UserModel.__table__)).mappings().all()
        command.upgrade(config, "head")
        assert {"strategy_candidates", "confirmed_strategy_versions", "strategy_identities"} <= set(
            inspect(trial).get_table_names()
        )
        assert conversations.history(owner, thread.id) == before_history
        enabled = ConversationService(
            SqlAlchemyConversationUnitOfWorkFactory(factory),
            strategy_repository_factory=conversation_strategy_repository,
        )
        strategies = StrategyService(SqlAlchemyStrategyUnitOfWorkFactory(factory))
        for operation, payload in (
            ("UPSERT", {"target_budget": "300"}),
            ("UPSERT", {"target_budget": "500"}),
            ("INVALIDATE", None),
        ):
            question = (
                "取消 GOOG 长期目标"
                if operation == "INVALIDATE"
                else "请持续记住 GOOG 长期目标资本配置"
            )
            started = enabled.start_turn(
                owner,
                thread.id,
                portfolio_user_id=user_id,
                question=question,
                client_request_id=uuid4(),
                expected_thread_revision=enabled.get_thread(owner, thread.id).thread.revision,
            )
            draft = StrategyDraft.model_validate(
                {
                    "operation": operation,
                    "scope": {"ticker": "GOOG", "position_type": "LONG_TERM"},
                    "kind": "POSITION_PLAN_V1",
                    "payload": payload,
                    "origin": "USER_STATED_INTENT",
                    "evidence_quote": question,
                }
            )
            completed = enabled.complete_turn(
                owner, thread.id, started.turn.id, answer="草案待显式确认。", strategy_draft=draft
            )
            assert completed.candidate is not None
            candidate = completed.candidate
            strategies.confirm(
                owner,
                candidate.id,
                candidate_revision=candidate.candidate_revision,
                base_version=candidate.base_version,
                client_request_id=uuid4(),
            )
        assert strategies.active(owner) == ()
        with trial.connect() as connection:
            assert connection.execute(select(TransactionModel.__table__)).mappings().all() == before
            assert connection.execute(select(UserModel.__table__)).mappings().all() == before_user
    finally:
        trial.dispose()
        with admin.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE "{name}" WITH (FORCE)')
        admin.dispose()
