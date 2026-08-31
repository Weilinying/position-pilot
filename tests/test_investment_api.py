"""M4 投资问答 API Contract 测试。"""

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from position_pilot.application.auth_service import Account
from position_pilot.application.errors import UserNotFound
from position_pilot.application.investment_agent import (
    ContextSource,
    ContextSourceType,
    InvestmentAnswer,
    InvestmentFailureCode,
    InvestmentRequestFailure,
    InvestmentResponseStatus,
)
from position_pilot.main import (
    app,
    get_current_account_dependency,
    get_investment_agent_dependency,
)

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 8, 24, 8, 0, tzinfo=UTC)
ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000010")


def make_account() -> Account:
    """创建与固定 Portfolio 绑定的已认证 Account。"""

    return Account(
        id=ACCOUNT_ID,
        email="agent@example.com",
        display_name="Agent User",
        password_hash="not-returned",
        portfolio_user_id=USER_ID,
        created_at=NOW,
    )


class FakeInvestmentAgent:
    """返回固定 Application Result，并记录 API 规范化输入。"""

    def __init__(
        self,
        result: InvestmentAnswer | InvestmentRequestFailure | Exception,
    ) -> None:
        self.result = result
        self.calls: list[tuple[UUID, str]] = []

    def answer(
        self,
        user_id: UUID,
        question: str,
    ) -> InvestmentAnswer | InvestmentRequestFailure:
        self.calls.append((user_id, question))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def client() -> Iterator[TestClient]:
    """每个测试后恢复 FastAPI Dependency Override。"""

    app.dependency_overrides[get_current_account_dependency] = make_account
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def override_agent(agent: FakeInvestmentAgent) -> None:
    """避免 API Contract Test 读取数据库或外部 Provider。"""

    app.dependency_overrides[get_investment_agent_dependency] = lambda: agent


def test_returns_answer_with_deterministic_status_and_source_tracking(
    client: TestClient,
) -> None:
    """成功 API Response 应保留 Portfolio、Quote 与 Price History 来源。"""

    agent = FakeInvestmentAgent(
        InvestmentAnswer(
            InvestmentResponseStatus.OK,
            "基于当前持仓和行情的回答",
            (
                ContextSource(ContextSourceType.PORTFOLIO_SNAPSHOT, "OK"),
                ContextSource(
                    ContextSourceType.CURRENT_QUOTE,
                    "OK",
                    ticker="GOOG",
                    provider="ALPACA",
                    feed="IEX",
                    market_timestamp=NOW,
                    fetched_at=NOW,
                ),
                ContextSource(
                    ContextSourceType.PRICE_HISTORY,
                    "OK",
                    ticker="GOOG",
                    provider="ALPACA",
                    feed="IEX",
                    market_timestamp=NOW,
                    fetched_at=NOW,
                ),
                ContextSource(
                    ContextSourceType.RECENT_NEWS,
                    "OK",
                    ticker="GOOG",
                    provider="ALPACA",
                    feed="BENZINGA",
                    market_timestamp=None,
                    fetched_at=NOW,
                ),
                ContextSource(
                    ContextSourceType.MARKET_CONTEXT,
                    "OK",
                    ticker="SPY",
                    provider="ALPACA",
                    feed="SIP",
                    market_timestamp=NOW,
                    fetched_at=NOW,
                ),
            ),
        )
    )
    override_agent(agent)

    response = client.post(
        "/v1/investment/questions",
        json={"question": "  GOOG 现在能买吗？  "},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "OK",
        "answer": "基于当前持仓和行情的回答",
        "sources": [
            {
                "type": "PORTFOLIO_SNAPSHOT",
                "status": "OK",
                "ticker": None,
                "provider": None,
                "feed": None,
                "market_timestamp": None,
                "fetched_at": None,
            },
            {
                "type": "CURRENT_QUOTE",
                "status": "OK",
                "ticker": "GOOG",
                "provider": "ALPACA",
                "feed": "IEX",
                "market_timestamp": "2026-08-24T08:00:00Z",
                "fetched_at": "2026-08-24T08:00:00Z",
            },
            {
                "type": "PRICE_HISTORY",
                "status": "OK",
                "ticker": "GOOG",
                "provider": "ALPACA",
                "feed": "IEX",
                "market_timestamp": "2026-08-24T08:00:00Z",
                "fetched_at": "2026-08-24T08:00:00Z",
            },
            {
                "type": "RECENT_NEWS",
                "status": "OK",
                "ticker": "GOOG",
                "provider": "ALPACA",
                "feed": "BENZINGA",
                "market_timestamp": None,
                "fetched_at": "2026-08-24T08:00:00Z",
            },
            {
                "type": "MARKET_CONTEXT",
                "status": "OK",
                "ticker": "SPY",
                "provider": "ALPACA",
                "feed": "SIP",
                "market_timestamp": "2026-08-24T08:00:00Z",
                "fetched_at": "2026-08-24T08:00:00Z",
            },
        ],
    }
    assert agent.calls == [(USER_ID, "GOOG 现在能买吗？")]


def test_returns_degraded_as_successful_safe_answer(client: TestClient) -> None:
    """Market Failure 降级回答仍使用 200，由 Response status 表达事实缺口。"""

    agent = FakeInvestmentAgent(
        InvestmentAnswer(
            InvestmentResponseStatus.DEGRADED,
            "当前行情不可用，只能基于持仓回答",
            (
                ContextSource(ContextSourceType.PORTFOLIO_SNAPSHOT, "OK"),
                ContextSource(
                    ContextSourceType.CURRENT_QUOTE,
                    "PROVIDER_UNAVAILABLE",
                    ticker="GOOG",
                ),
            ),
        )
    )
    override_agent(agent)

    response = client.post(
        "/v1/investment/questions",
        json={"question": "GOOG 现在能买吗？"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "DEGRADED"


@pytest.mark.parametrize(
    ("failure_code", "expected_status"),
    [
        (InvestmentFailureCode.INVALID_QUESTION, 422),
        (InvestmentFailureCode.INVALID_TOOL_CALL, 502),
        (InvestmentFailureCode.TOOL_CALL_LIMIT_EXCEEDED, 502),
        (InvestmentFailureCode.TOOL_ROUND_LIMIT_EXCEEDED, 502),
        (InvestmentFailureCode.LLM_INVALID_PROVIDER_RESPONSE, 502),
        (InvestmentFailureCode.LLM_AUTHENTICATION_FAILED, 503),
        (InvestmentFailureCode.LLM_RATE_LIMITED, 503),
        (InvestmentFailureCode.LLM_PROVIDER_UNAVAILABLE, 503),
    ],
)
def test_maps_request_failure_to_stable_http_error(
    client: TestClient,
    failure_code: InvestmentFailureCode,
    expected_status: int,
) -> None:
    """LLM/Agent Failure 不得返回伪造 Final Answer。"""

    override_agent(FakeInvestmentAgent(InvestmentRequestFailure(failure_code, "安全错误")))

    response = client.post(
        "/v1/investment/questions",
        json={"question": "question"},
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": {"code": failure_code.value, "message": "安全错误"}}


def test_maps_missing_portfolio_user_to_404(client: TestClient) -> None:
    """Structured State 不存在时不得调用 LLM 或返回通用 500。"""

    override_agent(FakeInvestmentAgent(UserNotFound(USER_ID)))

    response = client.post(
        "/v1/investment/questions",
        json={"question": "question"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": {"code": "USER_NOT_FOUND", "message": "Portfolio User 不存在"}
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"question": "   "},
        {"user_id": str(USER_ID), "question": "question"},
        {},
    ],
)
def test_rejects_invalid_request_before_agent_call(
    client: TestClient,
    payload: dict[str, str],
) -> None:
    """API Validation 不得把非法输入交给 Agent 或 LLM。"""

    agent = FakeInvestmentAgent(InvestmentAnswer(InvestmentResponseStatus.OK, "answer", ()))
    override_agent(agent)

    response = client.post("/v1/investment/questions", json=payload)

    assert response.status_code == 422
    assert agent.calls == []
