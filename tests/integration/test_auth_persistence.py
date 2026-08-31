"""本地 Authentication PostgreSQL 持久化集成测试。"""

import os
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete

from position_pilot.application.auth_service import (
    AuthService,
    LoginCommand,
    RegisterAccountCommand,
    SetupPortfolioCommand,
)
from position_pilot.application.errors import AuthenticationRequired
from position_pilot.application.portfolio_service import OpeningPositionInput, PortfolioService
from position_pilot.database import create_database_engine, create_session_factory
from position_pilot.domain.portfolio import PositionType
from position_pilot.infrastructure.models import (
    AccountModel,
    AuthSessionModel,
    OpeningPositionModel,
    UserModel,
)
from position_pilot.infrastructure.unit_of_work import SqlAlchemyPortfolioUnitOfWorkFactory

pytestmark = pytest.mark.integration


def get_test_database_url() -> str:
    """要求调用方显式提供可清理的 PostgreSQL 测试数据库。"""

    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("需要 TEST_DATABASE_URL 才能运行 PostgreSQL 集成测试")
    return database_url


def test_persists_account_rotates_session_and_recovers_owned_portfolio() -> None:
    """真实 UoW 应原子保存 Account、Session、Ownership 与 Opening State。"""

    engine = create_database_engine(get_test_database_url())
    session_factory = create_session_factory(engine)
    factory = SqlAlchemyPortfolioUnitOfWorkFactory(session_factory)
    auth = AuthService(factory)
    portfolio = PortfolioService(factory)
    email = f"integration-{uuid4()}@example.com"
    registered = auth.register(
        RegisterAccountCommand(
            email=email,
            password="correct horse battery staple",
            display_name="Integration Investor",
        )
    )
    user_id = None

    try:
        assert auth.authenticate(registered.token).id == registered.account.id
        user = auth.setup_portfolio(
            SetupPortfolioCommand(
                account_id=registered.account.id,
                initial_cash=Decimal("14.3"),
                opening_positions=(
                    OpeningPositionInput(
                        ticker="GOOG",
                        shares=Decimal("2"),
                        average_cost=Decimal("180.25"),
                        position_type=PositionType.LONG_TERM,
                    ),
                ),
            )
        )
        user_id = user.id

        recovered_auth = AuthService(factory)
        logged_in = recovered_auth.login(
            LoginCommand(
                email=email,
                password="correct horse battery staple",
            ),
            current_session_token=registered.token,
        )
        with pytest.raises(AuthenticationRequired):
            recovered_auth.authenticate(registered.token)
        account = recovered_auth.authenticate(logged_in.token)
        assert account.portfolio_user_id == user.id

        snapshot = portfolio.get_portfolio(user.id)
        assert snapshot.cash.available_cash == Decimal("14.30000000")
        position = snapshot.get_position("GOOG", PositionType.LONG_TERM)
        assert position is not None
        assert position.shares == Decimal("2.00000000")

        recovered_auth.logout(logged_in.token)
        with pytest.raises(AuthenticationRequired):
            recovered_auth.authenticate(logged_in.token)
    finally:
        with engine.begin() as connection:
            connection.execute(
                delete(AuthSessionModel).where(AuthSessionModel.account_id == registered.account.id)
            )
            connection.execute(delete(AccountModel).where(AccountModel.id == registered.account.id))
            if user_id is not None:
                connection.execute(
                    delete(OpeningPositionModel).where(OpeningPositionModel.user_id == user_id)
                )
                connection.execute(delete(UserModel).where(UserModel.id == user_id))
        engine.dispose()
