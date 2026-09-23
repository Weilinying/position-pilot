"""Conversation Thread / Message API Contract 测试。"""

from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from position_pilot.api.routers.conversation import (
    get_conversation_auth_service_dependency,
    get_conversation_service_dependency,
    router,
)
from position_pilot.application.auth_service import Account
from position_pilot.application.conversation_service import (
    ConversationCompletion,
    ConversationHistoryPage,
    ConversationMessage,
    ConversationMessageRole,
    ConversationRevisionConflict,
    ConversationSource,
    ConversationThread,
    ConversationThreadNotFound,
    ConversationThreadPage,
    ConversationThreadSnapshot,
    ConversationTurn,
    ConversationTurnInProgress,
    ConversationTurnStatus,
)
from position_pilot.application.errors import AuthenticationRequired

ACCOUNT_ID = UUID("10000000-0000-4000-8000-000000000001")
PORTFOLIO_USER_ID = UUID("20000000-0000-4000-8000-000000000001")
OTHER_THREAD_ID = UUID("30000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 9, 22, 8, 0, tzinfo=UTC)
TOKEN = "conversation-test-session"


def make_account() -> Account:
    """创建不含真实凭据的测试 Account。"""

    return Account(
        id=ACCOUNT_ID,
        email="investor@example.com",
        display_name="Local Investor",
        password_hash="not-returned",
        portfolio_user_id=PORTFOLIO_USER_ID,
        created_at=NOW,
    )


def make_thread(*, revision: int = 0, deleted_at: datetime | None = None) -> ConversationThread:
    """创建固定 Owner 的测试 Thread。"""

    return ConversationThread(
        id=UUID("40000000-0000-4000-8000-000000000001"),
        account_id=ACCOUNT_ID,
        title="GOOG discussion",
        revision=revision,
        next_sequence=3 if revision >= 2 else 1,
        created_at=NOW,
        updated_at=NOW,
        deleted_at=deleted_at,
    )


def make_completion() -> ConversationCompletion:
    """创建一个带真实 Source Metadata 的已完成 Turn。"""

    thread = make_thread(revision=2)
    turn_id = UUID("50000000-0000-4000-8000-000000000001")
    user_message = ConversationMessage(
        id=UUID("60000000-0000-4000-8000-000000000001"),
        thread_id=thread.id,
        account_id=ACCOUNT_ID,
        turn_id=turn_id,
        sequence=1,
        role=ConversationMessageRole.USER,
        content="分析 GOOG",
        created_at=NOW,
    )
    assistant_message = ConversationMessage(
        id=UUID("60000000-0000-4000-8000-000000000002"),
        thread_id=thread.id,
        account_id=ACCOUNT_ID,
        turn_id=turn_id,
        sequence=2,
        role=ConversationMessageRole.ASSISTANT,
        content="基于当前可用事实，建议重新评估风险。",
        created_at=NOW,
    )
    turn = ConversationTurn(
        id=turn_id,
        thread_id=thread.id,
        account_id=ACCOUNT_ID,
        client_request_id=UUID("70000000-0000-4000-8000-000000000001"),
        status=ConversationTurnStatus.COMPLETED,
        failure_code=None,
        run_deadline_at=NOW,
        created_at=NOW,
        completed_at=NOW,
    )
    source = ConversationSource(
        source_id=UUID("80000000-0000-4000-8000-000000000001"),
        assistant_message_id=assistant_message.id,
        source_type="CURRENT_QUOTE",
        provider="ALPACA_MARKET_DATA",
        provider_reference="GOOG",
        url=None,
        title=None,
        publisher=None,
        published_at=None,
        event_time=NOW,
        fetched_at=NOW,
        content_scope="STRUCTURED_FACT",
        status="OK",
    )
    return ConversationCompletion(
        thread=thread,
        turn=turn,
        user_message=user_message,
        assistant_message=assistant_message,
        sources=(source,),
        warnings=("USAGE_UNKNOWN",),
    )


@dataclass(slots=True)
class FakeAuthService:
    """只接受测试 Cookie 的 Auth Service。"""

    account: Account = field(default_factory=make_account)

    def authenticate(self, token: str | None) -> Account:
        if token != TOKEN:
            raise AuthenticationRequired()
        return self.account


@dataclass(slots=True)
class FakeConversationService:
    """提供 API Contract 所需的最小 Service Boundary。"""

    thread: ConversationThread = field(default_factory=make_thread)
    error: Exception | None = None
    completion: ConversationCompletion | None = None
    calls: list[tuple[str, UUID]] = field(default_factory=list)

    def start_thread(self, account_id: UUID, *, title: str | None = None) -> ConversationThread:
        self.calls.append(("start_thread", account_id))
        return ConversationThread(
            self.thread.id,
            self.thread.account_id,
            title or self.thread.title,
            self.thread.revision,
            self.thread.next_sequence,
            self.thread.created_at,
            self.thread.updated_at,
            self.thread.deleted_at,
        )

    def list_threads(
        self,
        account_id: UUID,
        *,
        cursor: str | None = None,
        limit: int = 20,
    ) -> ConversationThreadPage:
        del cursor, limit
        self.calls.append(("list_threads", account_id))
        if self.error is not None:
            raise self.error
        return ConversationThreadPage((self.thread,), None)

    def get_thread(self, account_id: UUID, thread_id: UUID) -> ConversationThreadSnapshot:
        self.calls.append(("get_thread", account_id))
        if self.error is not None:
            raise self.error
        return ConversationThreadSnapshot(self.thread, None, None)

    def history(
        self,
        account_id: UUID,
        thread_id: UUID,
        *,
        before_sequence: int | None = None,
        limit: int = 20,
    ) -> ConversationHistoryPage:
        del thread_id, before_sequence, limit
        self.calls.append(("history", account_id))
        if self.error is not None:
            raise self.error
        return ConversationHistoryPage(self.thread, (), None, None)

    def ask(
        self,
        account_id: UUID,
        thread_id: UUID,
        *,
        portfolio_user_id: UUID,
        question: str,
        client_request_id: UUID,
        expected_thread_revision: int,
    ) -> ConversationCompletion:
        del thread_id, portfolio_user_id, question, client_request_id, expected_thread_revision
        self.calls.append(("ask", account_id))
        if self.error is not None:
            raise self.error
        return self.completion or make_completion()

    def delete_thread(self, account_id: UUID, thread_id: UUID) -> ConversationThread:
        del thread_id
        self.calls.append(("delete_thread", account_id))
        if self.error is not None:
            raise self.error
        return ConversationThread(
            self.thread.id,
            self.thread.account_id,
            self.thread.title,
            self.thread.revision + 1,
            self.thread.next_sequence,
            self.thread.created_at,
            self.thread.updated_at,
            NOW,
        )


@pytest.fixture
def api_client() -> Iterator[tuple[TestClient, FakeAuthService, FakeConversationService]]:
    """创建只包含 Conversation Router 的测试应用。"""

    api = FastAPI()
    api.include_router(router)
    auth = FakeAuthService()
    service = FakeConversationService()
    api.dependency_overrides[get_conversation_auth_service_dependency] = lambda: auth
    api.dependency_overrides[get_conversation_service_dependency] = lambda: service
    with TestClient(api) as client:
        yield client, auth, service
    api.dependency_overrides.clear()


def auth_headers() -> dict[str, str]:
    """返回测试 Cookie。"""

    return {"Cookie": f"positionpilot_session={TOKEN}"}


def test_conversation_routes_require_session_cookie(
    api_client: tuple[TestClient, FakeAuthService, FakeConversationService],
) -> None:
    """缺少 Session 时不能通过路径或 Body 伪造 Owner。"""

    client, _, _ = api_client
    response = client.get("/v1/threads")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTHENTICATION_REQUIRED"


def test_thread_lifecycle_uses_cookie_account_and_exposes_stable_shapes(
    api_client: tuple[TestClient, FakeAuthService, FakeConversationService],
) -> None:
    """Thread、Snapshot、Messages 与 Delete 均只使用 Cookie Account。"""

    client, _, service = api_client
    created = client.post(
        "/v1/threads",
        headers=auth_headers(),
        json={"title": "  GOOG plan  "},
    )
    assert created.status_code == 201
    assert created.json()["title"] == "  GOOG plan  "
    assert created.json()["id"] == str(service.thread.id)
    assert "account_id" not in created.json()

    listed = client.get("/v1/threads?limit=1", headers=auth_headers())
    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == str(service.thread.id)

    snapshot = client.get(f"/v1/threads/{service.thread.id}", headers=auth_headers())
    assert snapshot.status_code == 200
    assert snapshot.json()["thread"]["revision"] == 0

    history = client.get(
        f"/v1/threads/{service.thread.id}/messages?before=5&limit=2",
        headers=auth_headers(),
    )
    assert history.status_code == 200
    assert history.json()["messages"] == []

    deleted = client.delete(f"/v1/threads/{service.thread.id}", headers=auth_headers())
    assert deleted.status_code == 200
    assert deleted.json()["deleted_at"] == NOW.isoformat().replace("+00:00", "Z")
    assert all(account_id == ACCOUNT_ID for _, account_id in service.calls)


def test_post_message_maps_answer_v2_without_fabricated_citations_or_candidate(
    api_client: tuple[TestClient, FakeAuthService, FakeConversationService],
) -> None:
    """T3 只暴露真实 Source，不伪造 T4A Citation 或 Strategy Candidate。"""

    client, _, service = api_client
    thread_id = service.thread.id
    response = client.post(
        f"/v1/threads/{thread_id}/messages",
        headers=auth_headers(),
        json={
            "content": "分析 GOOG",
            "client_request_id": str(uuid4()),
            "expected_thread_revision": 0,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["assistant_message"]["content"] == "基于当前可用事实，建议重新评估风险。"
    assert payload["answer"]["text"] == payload["assistant_message"]["content"]
    assert payload["answer"]["warnings"] == ["USAGE_UNKNOWN"]
    assert payload["answer"]["sources"][0]["provider"] == "ALPACA_MARKET_DATA"
    assert payload["answer"]["citations"] == []
    assert payload["answer"]["candidate"] is None
    assert "account_id" not in payload

    rejected = client.post(
        f"/v1/threads/{thread_id}/messages",
        headers=auth_headers(),
        json={
            "content": "分析 GOOG",
            "client_request_id": str(uuid4()),
            "expected_thread_revision": 0,
            "account_id": str(ACCOUNT_ID),
        },
    )
    assert rejected.status_code == 422


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    (
        (ConversationThreadNotFound(OTHER_THREAD_ID), 404, "THREAD_NOT_FOUND"),
        (ConversationRevisionConflict(0, 2), 409, "THREAD_CONFLICT"),
        (ConversationTurnInProgress(uuid4()), 409, "TURN_IN_PROGRESS"),
        (RuntimeError("provider unavailable"), 502, "AGENT_REQUEST_FAILED"),
    ),
)
def test_post_message_maps_stable_failures(
    api_client: tuple[TestClient, FakeAuthService, FakeConversationService],
    error: Exception,
    status_code: int,
    code: str,
) -> None:
    """Thread、并发与 Provider Failure 不泄露内部异常。"""

    client, _, service = api_client
    service.error = error
    response = client.post(
        f"/v1/threads/{service.thread.id}/messages",
        headers=auth_headers(),
        json={
            "content": "分析 GOOG",
            "client_request_id": str(uuid4()),
            "expected_thread_revision": 0,
        },
    )
    assert response.status_code == status_code
    assert response.json()["detail"]["code"] == code
    if isinstance(error, ConversationTurnInProgress):
        assert response.json()["detail"]["turn_id"] == str(error.turn_id)
    assert "provider unavailable" not in response.text


def test_post_message_maps_persisted_provider_failure(
    api_client: tuple[TestClient, FakeAuthService, FakeConversationService],
) -> None:
    """Agent 返回稳定 Provider Failure Code 时，API 不把失败 Turn 当成功。"""

    client, _, service = api_client
    completed = make_completion()
    failed_turn = replace(
        completed.turn,
        status=ConversationTurnStatus.FAILED,
        failure_code="LLM_PROVIDER_UNAVAILABLE",
    )
    service.completion = replace(completed, turn=failed_turn, assistant_message=None, sources=())
    response = client.post(
        f"/v1/threads/{service.thread.id}/messages",
        headers=auth_headers(),
        json={
            "content": "分析 GOOG",
            "client_request_id": str(uuid4()),
            "expected_thread_revision": 0,
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "LLM_PROVIDER_UNAVAILABLE"
