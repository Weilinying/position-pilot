"""本地 Account、Password 与 Session Application Service 测试。"""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import TracebackType
from typing import Self
from uuid import UUID

import pytest

from position_pilot.application.auth_service import (
    Account,
    AccountSession,
    AuthService,
    AuthSession,
    LoginCommand,
    RegisterAccountCommand,
    SetupPortfolioCommand,
    digest_session_token,
    hash_password,
    verify_password,
)
from position_pilot.application.errors import (
    AuthenticationRequired,
    EmailAlreadyRegistered,
    InvalidCredentials,
    PortfolioAlreadyExists,
)
from position_pilot.application.portfolio_service import OpeningPositionInput
from position_pilot.domain.errors import InvalidPortfolioValue
from position_pilot.domain.portfolio import OpeningPosition, PositionType, User

NOW = datetime(2026, 8, 31, 8, 0, tzinfo=UTC)


@dataclass(slots=True)
class FakeAuthStore:
    """测试所需的最小 Account / Session / Portfolio 持久化状态。"""

    accounts_by_id: dict[UUID, Account] = field(default_factory=dict)
    account_ids_by_email: dict[str, UUID] = field(default_factory=dict)
    sessions: dict[str, AuthSession] = field(default_factory=dict)
    users: dict[UUID, User] = field(default_factory=dict)
    opening_positions: list[OpeningPosition] = field(default_factory=list)
    commits: int = 0


class FakeAuthUnitOfWork:
    """直接映射 Fake Store 的同步 Auth Unit of Work。"""

    def __init__(self, store: FakeAuthStore) -> None:
        self.store = store

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def get_account_by_email(
        self,
        email: str,
        *,
        for_update: bool = False,
    ) -> Account | None:
        del for_update
        account_id = self.store.account_ids_by_email.get(email)
        return self.store.accounts_by_id.get(account_id) if account_id is not None else None

    def get_account_by_id(
        self,
        account_id: UUID,
        *,
        for_update: bool = False,
    ) -> Account | None:
        del for_update
        return self.store.accounts_by_id.get(account_id)

    def add_account(self, account: Account) -> None:
        self.store.accounts_by_id[account.id] = account
        self.store.account_ids_by_email[account.email] = account.id

    def set_account_portfolio(self, account_id: UUID, user_id: UUID) -> None:
        account = self.store.accounts_by_id[account_id]
        self.store.accounts_by_id[account_id] = replace(account, portfolio_user_id=user_id)

    def get_auth_session(self, token_digest: str) -> AuthSession | None:
        return self.store.sessions.get(token_digest)

    def add_auth_session(self, auth_session: AuthSession) -> None:
        self.store.sessions[auth_session.token_digest] = auth_session

    def delete_auth_session(self, token_digest: str) -> None:
        self.store.sessions.pop(token_digest, None)

    def add_user(self, user: User) -> None:
        self.store.users[user.id] = user

    def add_opening_positions(self, opening_positions: list[OpeningPosition]) -> None:
        self.store.opening_positions.extend(opening_positions)

    def commit(self) -> None:
        self.store.commits += 1


def make_service(
    store: FakeAuthStore,
    *,
    clock: Callable[[], datetime] | None = None,
) -> AuthService:
    """创建使用单一 Fake Store 的 Auth Service。"""

    return AuthService(
        lambda: FakeAuthUnitOfWork(store),
        clock=clock or (lambda: NOW),
    )


def register(
    service: AuthService,
    email: str = "User@Example.com",
) -> AccountSession:
    """创建测试 Account 并返回 Session Result。"""

    return service.register(
        RegisterAccountCommand(
            email=email,
            password="correct horse battery staple",
            display_name="Local Investor",
        )
    )


def test_password_hash_uses_salt_and_never_contains_plaintext() -> None:
    """相同 Password 应产生不同 Hash，并只允许正确值通过。"""

    first = hash_password("correct horse battery staple")
    second = hash_password("correct horse battery staple")

    assert first != second
    assert "correct horse" not in first
    assert verify_password("correct horse battery staple", first) is True
    assert verify_password("wrong password", first) is False
    assert verify_password("correct horse battery staple", "invalid") is False


def test_register_normalizes_email_and_stores_only_token_digest() -> None:
    """注册应原子创建 Account 与 Session，Raw Token 只返回调用方。"""

    store = FakeAuthStore()
    result = register(make_service(store))

    assert result.account.email == "user@example.com"
    assert result.account.password_hash != "correct horse battery staple"
    assert result.token not in store.sessions
    assert digest_session_token(result.token) in store.sessions
    assert store.commits == 1


def test_duplicate_email_is_rejected_before_second_session() -> None:
    """规范化后重复 Email 不得创建第二个 Account 或 Session。"""

    store = FakeAuthStore()
    service = make_service(store)
    register(service)

    with pytest.raises(EmailAlreadyRegistered):
        register(service, " user@example.com ")

    assert len(store.accounts_by_id) == 1
    assert len(store.sessions) == 1


def test_login_uses_generic_invalid_credentials_and_rotates_token() -> None:
    """失败登录保留旧 Session，成功登录原子撤销它并创建新 Token。"""

    store = FakeAuthStore()
    service = make_service(store)
    registered = register(service)

    with pytest.raises(InvalidCredentials):
        service.login(LoginCommand(email="missing@example.com", password="wrong password"))
    with pytest.raises(InvalidCredentials):
        service.login(
            LoginCommand(email="user@example.com", password="wrong password"),
            current_session_token=registered.token,
        )
    assert digest_session_token(registered.token) in store.sessions

    logged_in = service.login(
        LoginCommand(
            email="user@example.com",
            password="correct horse battery staple",
        ),
        current_session_token=registered.token,
    )
    assert logged_in.token != registered.token
    assert digest_session_token(registered.token) not in store.sessions
    assert digest_session_token(logged_in.token) in store.sessions
    assert len(store.sessions) == 1


def test_expired_or_logged_out_session_is_rejected() -> None:
    """过期 Session 应被清理，Logout 后同一 Raw Token 不再有效。"""

    store = FakeAuthStore()
    current_time = NOW
    service = make_service(store, clock=lambda: current_time)
    first = register(service)
    assert service.authenticate(first.token).id == first.account.id

    current_time = NOW + timedelta(days=8)
    with pytest.raises(AuthenticationRequired):
        service.authenticate(first.token)
    assert digest_session_token(first.token) not in store.sessions

    current_time = NOW
    second = service.login(
        LoginCommand(
            email="user@example.com",
            password="correct horse battery staple",
        )
    )
    service.logout(second.token)
    with pytest.raises(AuthenticationRequired):
        service.authenticate(second.token)


def test_setup_portfolio_binds_one_user_and_optional_opening_state() -> None:
    """Account 可稍后原子建立 Initial Cash 与 Existing Positions。"""

    store = FakeAuthStore()
    service = make_service(store)
    account = register(service).account

    user = service.setup_portfolio(
        SetupPortfolioCommand(
            account_id=account.id,
            initial_cash=Decimal("14.3"),
            opening_positions=(
                OpeningPositionInput(
                    ticker="goog",
                    shares=Decimal("2"),
                    average_cost=Decimal("180.25"),
                    position_type=None,
                ),
                OpeningPositionInput(
                    ticker="GOOG",
                    shares=Decimal("1"),
                    average_cost=Decimal("200"),
                    position_type=PositionType.SWING,
                ),
            ),
        )
    )

    assert user.initial_cash == Decimal("14.30000000")
    assert store.accounts_by_id[account.id].portfolio_user_id == user.id
    assert [item.position_type for item in store.opening_positions] == [
        PositionType.SWING,
        PositionType.UNSPECIFIED,
    ]
    with pytest.raises(PortfolioAlreadyExists):
        service.setup_portfolio(
            SetupPortfolioCommand(account_id=account.id, initial_cash=Decimal("0"))
        )


def test_invalid_setup_does_not_add_partial_user() -> None:
    """重复规范化 Position Key 必须在写入 User 前失败。"""

    store = FakeAuthStore()
    service = make_service(store)
    account = register(service).account

    with pytest.raises(InvalidPortfolioValue):
        service.setup_portfolio(
            SetupPortfolioCommand(
                account_id=account.id,
                initial_cash=Decimal("0"),
                opening_positions=(
                    OpeningPositionInput(
                        ticker="goog",
                        shares=Decimal("1"),
                        average_cost=Decimal("100"),
                    ),
                    OpeningPositionInput(
                        ticker="GOOG",
                        shares=Decimal("2"),
                        average_cost=Decimal("120"),
                    ),
                ),
            )
        )

    assert store.users == {}
    assert store.opening_positions == []
    assert store.accounts_by_id[account.id].portfolio_user_id is None
