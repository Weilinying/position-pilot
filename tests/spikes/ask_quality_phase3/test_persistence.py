"""最小 Conversation / Confirmed Strategy Persistence Prototype 测试。"""

import os
from dataclasses import dataclass, field
from uuid import uuid4

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import create_engine

from position_pilot.application.llm import (
    LLMMessage,
    LLMResponseFormat,
    LLMResult,
    LLMRole,
    LLMToolDefinition,
)

from .contracts import RuntimeBudget, RuntimeExecutionStatus, RuntimeInput
from .current_runtime import CurrentRuntimeCandidate
from .persistence import (
    ConversationMessage,
    InMemoryStateStore,
    OwnershipViolation,
    PostgresSpikeStateStore,
    StrategyRecord,
    inject_state,
    spike_database_url,
)
from .pydantic_runtime import PydanticRuntimeCandidate


@dataclass(slots=True)
class FinalAnswerLLM:
    """保存 Current Runtime 实际接收的 Conversation。"""

    calls: list[tuple[LLMMessage, ...]] = field(default_factory=list)

    def complete(
        self,
        messages: tuple[LLMMessage, ...],
        *,
        tools: tuple[LLMToolDefinition, ...] = (),
        response_format: LLMResponseFormat = LLMResponseFormat.TEXT,
    ) -> LLMResult:
        """返回固定 Answer。"""

        del tools, response_format
        self.calls.append(messages)
        return LLMResult.success(LLMMessage(LLMRole.ASSISTANT, "已恢复上下文。"))


def _store() -> InMemoryStateStore:
    """创建两个 Account、已确认与未确认 Strategy Fixture。"""

    return InMemoryStateStore(
        thread_owners={"thread-a": "account-a", "thread-b": "account-b"},
        messages=(
            ConversationMessage("account-a", "thread-a", 1, LLMRole.USER, "先看 GOOG"),
            ConversationMessage("account-a", "thread-a", 2, LLMRole.ASSISTANT, "先核验事实"),
            ConversationMessage("account-a", "thread-a", 3, LLMRole.USER, "预算改为 500"),
            ConversationMessage("account-b", "thread-b", 1, LLMRole.USER, "私有消息"),
        ),
        strategies=(
            StrategyRecord(
                "strategy-confirmed",
                "account-a",
                "GOOG",
                "user-confirmation",
                "分三次",
                True,
            ),
            StrategyRecord(
                "strategy-draft",
                "account-a",
                "GOOG",
                "model-suggestion",
                "一次买入",
                False,
            ),
            StrategyRecord(
                "strategy-other-owner",
                "account-b",
                "GOOG",
                "user-confirmation",
                "全部卖出",
                True,
            ),
        ),
    )


def _base_input() -> RuntimeInput:
    """创建等待 Application State 注入的 Runtime Input。"""

    return RuntimeInput(
        conversation=(LLMMessage(LLMRole.USER, "placeholder"),),
        current_turn_context={"ticker": "GOOG", "budget": "500"},
        portfolio_context={"cash": "10000", "positions": ["GOOG"]},
        confirmed_strategy=(),
        tools=(),
        budget=RuntimeBudget(4, 4, 2, 2, 30),
    )


def test_store_restores_bounded_conversation_and_only_confirmed_strategy() -> None:
    """只恢复当前 Owner、Scope 与 confirmed Strategy。"""

    context = _store().load_context(
        account_id="account-a",
        thread_id="thread-a",
        scope="GOOG",
        message_limit=2,
    )

    assert [message.content for message in context.conversation] == [
        "先核验事实",
        "预算改为 500",
    ]
    assert [strategy["strategy_id"] for strategy in context.confirmed_strategy] == [
        "strategy-confirmed"
    ]
    assert context.confirmed_strategy[0]["plan"] == "分三次"
    assert all(strategy["account_id"] == "account-a" for strategy in context.confirmed_strategy)


def test_store_rejects_cross_owner_thread_before_returning_context() -> None:
    """Account B 不能读取 Account A 的 Thread 或 Strategy。"""

    with pytest.raises(OwnershipViolation, match="THREAD_NOT_OWNED_BY_ACCOUNT"):
        _store().load_context(
            account_id="account-b",
            thread_id="thread-a",
            scope="GOOG",
            message_limit=10,
        )


def test_both_runtimes_consume_the_same_application_owned_state() -> None:
    """两个 Runtime 通过相同边界取得 History 与 Confirmed Strategy。"""

    context = _store().load_context(
        account_id="account-a",
        thread_id="thread-a",
        scope="GOOG",
        message_limit=3,
    )
    runtime_input = inject_state(_base_input(), context)
    current_llm = FinalAnswerLLM()
    current_result = CurrentRuntimeCandidate(current_llm, {}).run(runtime_input)
    pydantic_calls: list[list[ModelMessage]] = []

    def pydantic_model(
        messages: list[ModelMessage],
        info: AgentInfo,
    ) -> ModelResponse:
        """保存 PydanticAI 原生 History。"""

        del info
        pydantic_calls.append(messages)
        return ModelResponse(parts=(TextPart("已恢复上下文。"),))

    pydantic_result = PydanticRuntimeCandidate(FunctionModel(pydantic_model), {}).run(runtime_input)

    assert current_result.status is RuntimeExecutionStatus.COMPLETED
    assert pydantic_result.status is RuntimeExecutionStatus.COMPLETED
    current_payload = repr(current_llm.calls[0])
    pydantic_payload = repr(pydantic_calls[0])
    for expected in ("先看 GOOG", "预算改为 500", "strategy-confirmed", "分三次"):
        assert expected in current_payload
        assert expected in pydantic_payload
    assert "strategy-draft" not in current_payload
    assert "strategy-draft" not in pydantic_payload


def test_spike_database_url_never_falls_back_to_production_database() -> None:
    """缺少显式 Spike URL 时拒绝运行，即使 Production URL 存在。"""

    with pytest.raises(RuntimeError, match="SPIKE_DATABASE_URL_REQUIRED"):
        spike_database_url(
            {"DATABASE_URL": "postgresql+psycopg://production.example/position_pilot"}
        )


@pytest.mark.integration
def test_postgres_spike_store_owner_and_confirmation_boundaries() -> None:
    """可选临时 PostgreSQL Schema 验证与离线 Store 相同的读取边界。"""

    try:
        database_url = spike_database_url(os.environ)
    except RuntimeError:
        pytest.skip("需要显式 SPIKE_DATABASE_URL 才能运行 Persistence Spike")
    engine = create_engine(database_url)
    schema = f"phase3_{uuid4().hex}"
    with engine.connect() as connection, connection.begin():
        store = PostgresSpikeStateStore(connection, schema=schema)
        store.add_thread(thread_id="thread-a", account_id="account-a")
        store.add_message(
            ConversationMessage("account-a", "thread-a", 1, LLMRole.USER, "预算改为 500")
        )
        store.add_strategy(
            StrategyRecord(
                "confirmed",
                "account-a",
                "GOOG",
                "user-confirmation",
                "分三次",
                True,
            )
        )
        store.add_strategy(
            StrategyRecord(
                "draft",
                "account-a",
                "GOOG",
                "model-suggestion",
                "一次买入",
                False,
            )
        )

        context = store.load_context(
            account_id="account-a",
            thread_id="thread-a",
            scope="GOOG",
            message_limit=10,
        )
        assert [item["strategy_id"] for item in context.confirmed_strategy] == ["confirmed"]
        with pytest.raises(OwnershipViolation):
            store.load_context(
                account_id="account-b",
                thread_id="thread-a",
                scope="GOOG",
                message_limit=10,
            )
    engine.dispose()
