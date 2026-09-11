"""M8 本地 Authentication 与 Session-bound API Contract 测试。"""

from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from position_pilot.application.auth_service import (
    Account,
    AccountSession,
    LoginCommand,
    RegisterAccountCommand,
    SetupPortfolioCommand,
)
from position_pilot.application.errors import (
    AuthenticationRequired,
    EmailAlreadyRegistered,
    InvalidCredentials,
)
from position_pilot.domain.portfolio import CashBalance, PortfolioState, User
from position_pilot.main import (
    SESSION_COOKIE_NAME,
    app,
    get_auth_service_dependency,
    get_investment_agent_dependency,
    get_opening_import_service_dependency,
    get_portfolio_service_dependency,
)

ACCOUNT_ID = UUID("10000000-0000-4000-8000-000000000001")
USER_ID = UUID("20000000-0000-4000-8000-000000000001")
OTHER_USER_ID = UUID("30000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 8, 31, 9, 0, tzinfo=UTC)
TOKEN = "test-session-token"


def make_account(*, portfolio_user_id: UUID | None = None) -> Account:
    """创建 API Response 使用的固定 Account。"""

    return Account(
        id=ACCOUNT_ID,
        email="local@example.com",
        display_name="Local Investor",
        password_hash="never-returned",
        portfolio_user_id=portfolio_user_id,
        created_at=NOW,
    )


@dataclass(slots=True)
class FakeAuthService:
    """记录 API Command 并模拟 Cookie Session 生命周期。"""

    account: Account = field(default_factory=make_account)
    register_error: Exception | None = None
    login_error: Exception | None = None
    registered: list[RegisterAccountCommand] = field(default_factory=list)
    logged_in: list[LoginCommand] = field(default_factory=list)
    login_session_tokens: list[str | None] = field(default_factory=list)
    setup_commands: list[SetupPortfolioCommand] = field(default_factory=list)
    logged_out_tokens: list[str | None] = field(default_factory=list)

    def register(self, command: RegisterAccountCommand) -> AccountSession:
        self.registered.append(command)
        if self.register_error is not None:
            raise self.register_error
        return AccountSession(
            account=self.account,
            token=TOKEN,
            expires_at=NOW + timedelta(days=7),
        )

    def login(
        self,
        command: LoginCommand,
        *,
        current_session_token: str | None = None,
    ) -> AccountSession:
        self.logged_in.append(command)
        self.login_session_tokens.append(current_session_token)
        if self.login_error is not None:
            raise self.login_error
        return AccountSession(
            account=self.account,
            token=TOKEN,
            expires_at=NOW + timedelta(days=7),
        )

    def authenticate(self, token: str | None) -> Account:
        if token != TOKEN:
            raise AuthenticationRequired()
        return self.account

    def logout(self, token: str | None) -> None:
        self.logged_out_tokens.append(token)

    def setup_portfolio(self, command: SetupPortfolioCommand) -> User:
        self.setup_commands.append(command)
        self.account = replace(self.account, portfolio_user_id=USER_ID)
        return User.create(
            user_id=USER_ID,
            display_name=self.account.display_name,
            initial_cash=command.initial_cash,
            created_at=NOW,
        )


@dataclass(slots=True)
class FakePortfolioReader:
    """返回 Setup 后的固定空 Portfolio Snapshot。"""

    requested_user_ids: list[UUID] = field(default_factory=list)

    def get_portfolio(self, user_id: UUID) -> PortfolioState:
        self.requested_user_ids.append(user_id)
        return PortfolioState(
            user_id=user_id,
            cash=CashBalance(
                user_id=user_id,
                initial_cash=Decimal("14.30000000"),
                available_cash=Decimal("14.30000000"),
            ),
            positions=(),
            transaction_count=0,
        )


@dataclass(slots=True)
class FakeOpeningImportSetup:
    """把 Setup API 委托给测试中的 Fake Auth Service。"""

    auth_service: FakeAuthService

    def setup_portfolio(self, command: SetupPortfolioCommand) -> User:
        """记录并返回 Fake Auth Service 产生的 User。"""

        return self.auth_service.setup_portfolio(command)


@pytest.fixture
def client() -> Iterator[TestClient]:
    """每个 Test 使用独立 Cookie Jar 与 Dependency Override。"""

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def override_auth(service: FakeAuthService) -> None:
    """让 Auth API Test 不读取真实 Database。"""

    app.dependency_overrides[get_auth_service_dependency] = lambda: service


def test_register_sets_http_only_session_and_returns_no_secret(client: TestClient) -> None:
    """注册 Response 只返回 Account View，Cookie 具备本地 Session 边界。"""

    service = FakeAuthService()
    override_auth(service)

    response = client.post(
        "/v1/auth/register",
        json={
            "email": " Local@Example.com ",
            "password": "correct horse battery staple",
            "display_name": "Local Investor",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "account": {
            "email": "local@example.com",
            "display_name": "Local Investor",
            "portfolio_ready": False,
        }
    }
    set_cookie = response.headers["set-cookie"]
    assert f"{SESSION_COOKIE_NAME}={TOKEN}" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Path=/" in set_cookie
    assert "password" not in response.text.lower()


def test_duplicate_email_and_invalid_login_use_stable_errors(client: TestClient) -> None:
    """注册冲突与登录失败不得暴露内部 Account 数据。"""

    register_service = FakeAuthService(register_error=EmailAlreadyRegistered())
    override_auth(register_service)
    duplicate = client.post(
        "/v1/auth/register",
        json={
            "email": "local@example.com",
            "password": "correct horse battery staple",
            "display_name": "Local Investor",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "EMAIL_ALREADY_REGISTERED"

    login_service = FakeAuthService(login_error=InvalidCredentials())
    override_auth(login_service)
    invalid_login = client.post(
        "/v1/auth/login",
        json={"email": "local@example.com", "password": "wrong password"},
    )
    assert invalid_login.status_code == 401
    assert invalid_login.json()["detail"]["code"] == "INVALID_CREDENTIALS"


def test_login_rotates_current_browser_session(client: TestClient) -> None:
    """Login 把当前 Cookie 交给 Service，在成功事务中完成 Session Rotation。"""

    service = FakeAuthService()
    override_auth(service)
    client.cookies.set(SESSION_COOKIE_NAME, "old-session-token")

    response = client.post(
        "/v1/auth/login",
        json={
            "email": "local@example.com",
            "password": "correct horse battery staple",
        },
    )

    assert response.status_code == 200
    assert service.login_session_tokens == ["old-session-token"]
    assert f"{SESSION_COOKIE_NAME}={TOKEN}" in response.headers["set-cookie"]


def test_session_recovery_and_logout_are_cookie_bound(client: TestClient) -> None:
    """Session Recovery 需要有效 Cookie，Logout 撤销并清除它。"""

    service = FakeAuthService(account=make_account(portfolio_user_id=USER_ID))
    override_auth(service)

    anonymous = client.get("/v1/auth/session")
    assert anonymous.status_code == 401
    assert anonymous.json()["detail"]["code"] == "AUTHENTICATION_REQUIRED"

    client.cookies.set(SESSION_COOKIE_NAME, TOKEN)
    recovered = client.get("/v1/auth/session")
    assert recovered.status_code == 200
    assert recovered.json()["account"]["portfolio_ready"] is True

    logged_out = client.post("/v1/auth/logout")
    assert logged_out.status_code == 204
    assert service.logged_out_tokens == [TOKEN]
    clear_cookie = logged_out.headers["set-cookie"]
    assert f'{SESSION_COOKIE_NAME}=""' in clear_cookie
    assert "Max-Age=0" in clear_cookie


def test_portfolio_setup_uses_current_account_and_optional_opening_draft(
    client: TestClient,
) -> None:
    """Setup 不接收 Account / User ID，并在成功后返回后端 Snapshot。"""

    auth_service = FakeAuthService()
    portfolio_service = FakePortfolioReader()
    override_auth(auth_service)
    app.dependency_overrides[get_portfolio_service_dependency] = lambda: portfolio_service
    app.dependency_overrides[get_opening_import_service_dependency] = lambda: (
        FakeOpeningImportSetup(auth_service)
    )
    client.cookies.set(SESSION_COOKIE_NAME, TOKEN)

    response = client.post(
        "/v1/portfolio",
        json={
            "initial_cash": "14.3",
            "opening_positions": [
                {
                    "ticker": "GOOG",
                    "shares": "2",
                    "average_cost": "180.25",
                }
            ],
        },
    )

    assert response.status_code == 201
    assert response.json()["available_cash"] == "14.30000000"
    command = auth_service.setup_commands[0]
    assert command.account_id == ACCOUNT_ID
    assert command.initial_cash == Decimal("14.3")
    assert command.opening_positions[0].ticker == "GOOG"
    assert portfolio_service.requested_user_ids == [USER_ID]


def test_protected_portfolio_routes_reject_anonymous_and_other_owner(
    client: TestClient,
) -> None:
    """UUID 兼容 Route 也不能绕过 Session Ownership。"""

    service = FakeAuthService(account=make_account(portfolio_user_id=USER_ID))
    override_auth(service)

    anonymous = client.get(f"/v1/portfolios/{USER_ID}")
    assert anonymous.status_code == 401

    portfolio_service = FakePortfolioReader()
    app.dependency_overrides[get_portfolio_service_dependency] = lambda: portfolio_service
    client.cookies.set(SESSION_COOKIE_NAME, TOKEN)
    other_owner = client.get(f"/v1/portfolios/{OTHER_USER_ID}")
    assert other_owner.status_code == 404
    assert other_owner.json()["detail"]["code"] == "PORTFOLIO_NOT_FOUND"
    assert portfolio_service.requested_user_ids == []


def test_investment_question_rejects_body_identity_before_agent_call(
    client: TestClient,
) -> None:
    """Investment Question Contract 不再接受任何客户端 User Identity。"""

    service = FakeAuthService(account=make_account(portfolio_user_id=USER_ID))
    override_auth(service)
    client.cookies.set(SESSION_COOKIE_NAME, TOKEN)

    @dataclass(slots=True)
    class UnexpectedAgent:
        calls: int = 0

        def answer(self, user_id: UUID, question: str) -> object:
            del user_id, question
            self.calls += 1
            raise AssertionError("跨 Owner Request 不得调用 Agent")

    agent = UnexpectedAgent()
    app.dependency_overrides[get_investment_agent_dependency] = lambda: agent
    response = client.post(
        "/v1/investment/questions",
        json={"user_id": str(OTHER_USER_ID), "question": "GOOG 现在怎么样？"},
    )

    assert response.status_code == 422
    assert agent.calls == 0
