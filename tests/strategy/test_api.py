"""真实 SQLite UoW 验证意图确认、scope 隔离与 Conversation 原子提交。"""

from uuid import UUID, uuid4

from position_pilot.application.conversation_service import ConversationService
from position_pilot.domain.strategy import (
    StrategyVersion,
)
from position_pilot.infrastructure.conversation_unit_of_work import (
    SqlAlchemyConversationUnitOfWorkFactory,
    conversation_strategy_repository,
)

from .support import NOW, QUESTION, Store, confirm, draft, propose


def test_session_owned_api_confirm_cancel_and_recovery(store: Store) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from position_pilot.api.routers.conversation import get_conversation_account_dependency
    from position_pilot.api.routers.strategy import get_strategy_service_dependency, router
    from position_pilot.application.auth_service import Account

    conversations, strategies, _, owner = store
    candidate = propose(conversations, owner)
    app = FastAPI()
    app.include_router(router)
    current_owner = owner

    def account() -> Account:
        return Account(current_owner, "fixture@example.test", "Fixture", "fixture-hash", None, NOW)

    app.dependency_overrides[get_conversation_account_dependency] = account
    app.dependency_overrides[get_strategy_service_dependency] = lambda: strategies
    with TestClient(app) as client:
        url = f"/v1/strategy-candidates/{candidate.id}"
        assert client.get(url).json()["status"] == "PENDING"
        request = {"candidate_revision": 1, "base_version": 0, "client_request_id": str(uuid4())}
        assert (
            client.post(url + "/confirm", json={**request, "account_id": str(owner)}).status_code
            == 422
        )
        assert (
            client.post(url + "/confirm", json={**request, "candidate_revision": True}).status_code
            == 422
        )
        assert client.post(url + "/confirm", json=request).status_code == 200
        assert client.post(url + "/confirm", json=request).status_code == 200
        assert client.get(url).json()["status"] == "CONFIRMED"
        assert len(client.get("/v1/strategies?scope=goog:LONG_TERM").json()) == 1
        assert client.get("/v1/strategies?scope=GOOG:SWING").json() == []
        assert client.get("/v1/strategies?scope=GOOG:UNSPECIFIED").status_code == 422
        pending = propose(conversations, owner)
        assert (
            client.post(
                f"/v1/strategy-candidates/{pending.id}/cancel", json={"candidate_revision": 1}
            ).json()["status"]
            == "CANCELLED"
        )
        current_owner = uuid4()
        assert client.get(url).status_code == 404
        assert client.post(url + "/confirm", json=request).status_code == 404
        assert client.get("/v1/strategies").json() == []


def test_ask_candidate_and_answer_are_atomic_and_restored_by_thread_api(store: Store) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from position_pilot.api.routers.conversation import (
        get_conversation_account_dependency,
        get_conversation_service_dependency,
        router,
    )
    from position_pilot.application.auth_service import Account
    from position_pilot.application.conversation_service import (
        ConversationAgentResult,
        ConversationHistoryMessage,
    )

    _, strategies, factory, owner = store
    portfolio_id = uuid4()

    class FixtureAgent:
        def answer(
            self,
            *,
            account_id: UUID,
            portfolio_user_id: UUID,
            question: str,
            history: tuple[ConversationHistoryMessage, ...],
        ) -> ConversationAgentResult:
            del history
            assert account_id == owner and portfolio_user_id == portfolio_id
            return ConversationAgentResult(
                answer="请审查草案；尚未生效。" if question == QUESTION else "未确认，不会生效。",
                strategy_draft=draft() if question == QUESTION else None,
            )

    service = ConversationService(
        SqlAlchemyConversationUnitOfWorkFactory(factory),
        clock=lambda: NOW,
        agent=FixtureAgent(),
        strategy_repository_factory=conversation_strategy_repository,
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_conversation_account_dependency] = lambda: Account(
        owner, "fixture@example.test", "Fixture", "fixture-hash", portfolio_id, NOW
    )
    app.dependency_overrides[get_conversation_service_dependency] = lambda: service
    with TestClient(app) as client:
        thread = client.post("/v1/threads", json={}).json()
        url = f"/v1/threads/{thread['id']}/messages"
        request = {
            "content": QUESTION,
            "client_request_id": str(uuid4()),
            "expected_thread_revision": thread["revision"],
        }
        response = client.post(url, json=request)
        assert response.status_code == 200, response.text
        result = response.json()
        candidate = result["answer"]["candidate"]
        assert candidate["status"] == "PENDING"
        assert strategies.active(owner) == ()
        assert client.post(url, json=request).json()["answer"]["candidate"]["id"] == candidate["id"]
        history = client.get(url).json()
        assert (
            history["answers"][result["assistant_message"]["id"]]["candidate"]["id"]
            == candidate["id"]
        )
        reply = client.post(
            url,
            json={
                "content": "好",
                "client_request_id": str(uuid4()),
                "expected_thread_revision": result["thread"]["revision"],
            },
        )
        assert reply.status_code == 200, reply.text
        assert reply.json()["answer"]["candidate"] is None
        assert strategies.active(owner) == ()


def test_conversation_reads_only_active_owner_intent_and_reloads_versions(store: Store) -> None:
    from position_pilot.application.conversation_agent import ConversationInvestmentAgent
    from position_pilot.application.investment_agent import (
        InvestmentAnswer,
        InvestmentResponseStatus,
    )
    from position_pilot.application.llm import LLMMessage

    conversations, strategies, _, owner = store
    seen: list[tuple[StrategyVersion, ...]] = []

    class FixtureNativeAgent:
        def answer_with_history(
            self, user_id: UUID, question: str, conversation_history: tuple[LLMMessage, ...]
        ) -> InvestmentAnswer:
            raise AssertionError("已启用持续意图接线")

        def answer_with_intent(
            self,
            user_id: UUID,
            question: str,
            conversation_history: tuple[LLMMessage, ...],
            confirmed: tuple[StrategyVersion, ...],
        ) -> InvestmentAnswer:
            seen.append(confirmed)
            return InvestmentAnswer(InvestmentResponseStatus.OK, "只使用当前生效意图。", ())

    adapter = ConversationInvestmentAgent(FixtureNativeAgent(), strategies)
    pending = propose(conversations, owner)
    adapter.answer(account_id=owner, portfolio_user_id=uuid4(), question="分析当前目标", history=())
    assert seen.pop() == ()
    first = confirm(strategies, owner, pending)
    replacement = propose(conversations, owner, draft(payload={"target_budget": "500"}))
    adapter.answer(account_id=owner, portfolio_user_id=uuid4(), question="分析当前目标", history=())
    assert seen.pop() == (first,)
    second = confirm(strategies, owner, replacement)
    adapter.answer(account_id=owner, portfolio_user_id=uuid4(), question="分析当前目标", history=())
    assert seen.pop() == (second,)
    adapter.answer(
        account_id=uuid4(), portfolio_user_id=uuid4(), question="分析当前目标", history=()
    )
    assert seen.pop() == ()
    invalidation = propose(conversations, owner, draft(operation="INVALIDATE", payload=None))
    confirm(strategies, owner, invalidation)
    adapter.answer(account_id=owner, portfolio_user_id=uuid4(), question="分析当前目标", history=())
    assert seen.pop() == ()
