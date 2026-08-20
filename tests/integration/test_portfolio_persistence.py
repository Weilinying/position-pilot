"""Portfolio PostgreSQL 持久化集成测试。"""

import os
from decimal import Decimal

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from position_pilot.application.portfolio_service import (
    CreateUserCommand,
    PortfolioService,
    RecordTransactionCommand,
)
from position_pilot.database import create_database_engine, create_session_factory
from position_pilot.domain.portfolio import PositionType, TransactionAction
from position_pilot.infrastructure.models import TransactionModel, UserModel
from position_pilot.infrastructure.unit_of_work import SqlAlchemyPortfolioUnitOfWorkFactory

pytestmark = pytest.mark.integration


def get_test_database_url() -> str:
    """要求调用方显式提供可清理的 PostgreSQL 测试数据库。"""

    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("需要 TEST_DATABASE_URL 才能运行 PostgreSQL 集成测试")
    return database_url


def test_persists_and_recovers_portfolio_from_transaction_ledger() -> None:
    """新 Service 实例应从 PostgreSQL Ledger 恢复 Cash 与独立 Position。"""

    engine = create_database_engine(get_test_database_url())
    session_factory = create_session_factory(engine)
    service = PortfolioService(SqlAlchemyPortfolioUnitOfWorkFactory(session_factory))
    user = service.create_user(
        CreateUserCommand(display_name="Integration User", initial_cash=Decimal("1000"))
    )

    try:
        first = service.record_transaction(
            RecordTransactionCommand(
                user_id=user.id,
                ticker="GOOG",
                action=TransactionAction.BUY,
                price=Decimal("220.5"),
                shares=Decimal("0.45"),
                position_type=PositionType.LONG_TERM,
                reason="首次建立长期仓",
            )
        )
        service.record_transaction(
            RecordTransactionCommand(
                user_id=user.id,
                ticker="GOOG",
                action=TransactionAction.BUY,
                price=Decimal("100"),
                shares=Decimal("1"),
                position_type=PositionType.SWING,
            )
        )
        service.record_transaction(
            RecordTransactionCommand(
                user_id=user.id,
                ticker="GOOG",
                action=TransactionAction.SELL,
                price=Decimal("250"),
                shares=Decimal("0.2"),
                position_type=PositionType.LONG_TERM,
            )
        )

        recovered_service = PortfolioService(
            SqlAlchemyPortfolioUnitOfWorkFactory(create_session_factory(engine))
        )
        state = recovered_service.get_portfolio(user.id)
        transactions = recovered_service.list_transactions(user.id)

        assert first.amount == Decimal("99.22500000")
        assert state.cash.available_cash == Decimal("850.77500000")
        long_term = state.get_position("GOOG", PositionType.LONG_TERM)
        assert long_term is not None
        assert long_term.shares == Decimal("0.25000000")
        assert long_term.average_cost == Decimal("220.50000000")
        assert state.get_position("GOOG", PositionType.SWING) is not None
        assert [transaction.sequence for transaction in transactions] == [1, 2, 3]
        assert [transaction.amount for transaction in transactions] == [
            Decimal("99.22500000"),
            Decimal("100.00000000"),
            Decimal("50.00000000"),
        ]
    finally:
        with engine.begin() as connection:
            connection.execute(delete(TransactionModel).where(TransactionModel.user_id == user.id))
            connection.execute(delete(UserModel).where(UserModel.id == user.id))
        engine.dispose()


def test_database_rejects_non_derived_amount() -> None:
    """绕过 Application 写入不一致 amount 时，数据库约束仍应拒绝。"""

    engine = create_database_engine(get_test_database_url())
    session_factory = create_session_factory(engine)
    service = PortfolioService(SqlAlchemyPortfolioUnitOfWorkFactory(session_factory))
    user = service.create_user(
        CreateUserCommand(display_name="Constraint User", initial_cash=Decimal("1000"))
    )

    try:
        with session_factory() as session:
            session.add(
                TransactionModel(
                    id=user.id,
                    user_id=user.id,
                    sequence=1,
                    ticker="GOOG",
                    action=TransactionAction.BUY.value,
                    price=Decimal("10"),
                    shares=Decimal("2"),
                    amount=Decimal("999"),
                    position_type=PositionType.LONG_TERM.value,
                    occurred_at=user.created_at,
                    reason=None,
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        with engine.begin() as connection:
            connection.execute(delete(TransactionModel).where(TransactionModel.user_id == user.id))
            connection.execute(delete(UserModel).where(UserModel.id == user.id))
        engine.dispose()


def test_database_accepts_domain_bankers_rounding_at_midpoint() -> None:
    """数据库约束必须接受领域层在 midpoint 产生的银行家舍入结果。"""

    engine = create_database_engine(get_test_database_url())
    session_factory = create_session_factory(engine)
    service = PortfolioService(SqlAlchemyPortfolioUnitOfWorkFactory(session_factory))
    user = service.create_user(
        CreateUserCommand(display_name="Rounding User", initial_cash=Decimal("1000"))
    )

    try:
        transaction = service.record_transaction(
            RecordTransactionCommand(
                user_id=user.id,
                ticker="GOOG",
                action=TransactionAction.BUY,
                price=Decimal("1.00000001"),
                shares=Decimal("0.5"),
                position_type=PositionType.LONG_TERM,
            )
        )

        assert transaction.amount == Decimal("0.50000000")
        assert service.list_transactions(user.id)[0].amount == Decimal("0.50000000")
    finally:
        with engine.begin() as connection:
            connection.execute(delete(TransactionModel).where(TransactionModel.user_id == user.id))
            connection.execute(delete(UserModel).where(UserModel.id == user.id))
        engine.dispose()
