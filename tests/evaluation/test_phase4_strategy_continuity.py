"""连续 Ask 的确认 / 替代 / 账本重算与 ordinary Tool Loop，使用离线模型。"""

import json
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from ask_quality_cases import CASES_BY_ID
from behavioral_harness import (
    NOW,
    USER_ID,
    FixedMarketContext,
    FixedMarketData,
    FixedNews,
    fixed_quote,
)
from phase4_strategy_fixture import strategy_fixture
from phase4_strategy_harness import StrategyRecordingRuntime
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from position_pilot.application.investment_context import InvestmentPortfolioContext
from position_pilot.application.native_investment_agent import NativeInvestmentAgent
from position_pilot.domain.portfolio import (
    LotAllocation,
    PositionType,
    Transaction,
    TransactionAction,
    User,
    rebuild_portfolio,
)
from position_pilot.domain.strategy import StrategyKind, StrategyOperation
from position_pilot.integrations.pydantic_ai_runtime import PydanticAIRuntime

PLAN = "请持续记住 GOOG LONG_TERM 的目标资本配置 300 美元。"


def test_continuous_ask_rebuilds_current_ledger_and_does_not_freeze_recommendation() -> None:
    user = User.create(
        user_id=USER_ID, display_name="Fixture", initial_cash=Decimal("1000"), created_at=NOW
    )
    transactions: list[Transaction] = []
    schemas: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []

    class CurrentLedger:
        def get_investment_context(self, user_id: UUID) -> InvestmentPortfolioContext:
            assert user_id == USER_ID
            state = rebuild_portfolio(
                user,
                transactions,
                [],
                lot_allocations=[
                    LotAllocation.create(
                        user_id=USER_ID,
                        sell_transaction_id=tx.id,
                        lot_id=transactions[0].id,
                        shares=tx.shares,
                    )
                    for tx in transactions
                    if tx.action is TransactionAction.SELL
                ],
            )
            return InvestmentPortfolioContext.from_ledger(state, tuple(transactions))

    def transact(
        action: TransactionAction, position_type: PositionType, price: str, shares: str
    ) -> None:
        transactions.append(
            Transaction.create(
                user_id=USER_ID,
                sequence=len(transactions) + 1,
                ticker="GOOG",
                action=action,
                price=Decimal(price),
                shares=Decimal(shares),
                position_type=position_type,
                occurred_at=NOW,
            )
        )

    def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        output = info.model_request_parameters.output_object
        assert output is not None
        schemas.append(output.json_schema)
        latest = messages[-1]
        assert isinstance(latest, ModelRequest)
        part = latest.parts[-1]
        candidate = None
        sources: list[dict[str, str]] = [{"type": "PORTFOLIO_SNAPSHOT"}]
        answer = "固定回答，不代表行为评分或生效策略。"
        if isinstance(part, ToolReturnPart):
            assert isinstance(part.content, str)
            observation = json.loads(part.content)
            observations.append(observation)
            source = observation["sources"][0]
            sources.append({"type": "CURRENT_QUOTE", "ticker": "GOOG"})
            answer = f"本轮报价已获取 [source:{source['source_id']}]。"
        else:
            assert isinstance(part, UserPromptPart) and isinstance(part.content, str)
            question = json.loads(part.content)["question"]
            if question == PLAN:
                candidate = {
                    "operation": "UPSERT",
                    "scope": {"ticker": "GOOG", "position_type": "LONG_TERM"},
                    "kind": "POSITION_PLAN_V1",
                    "payload": {"target_budget": "300"},
                    "origin": "USER_STATED_INTENT",
                    "evidence_quote": PLAN,
                }
            elif "320" in question or "重新分析" in question:
                return ModelResponse(
                    parts=[
                        ToolCallPart(
                            "get_current_quote",
                            {
                                "ticker": "GOOG",
                                "request_purpose": "INFORMATION_RETRIEVAL",
                            },
                        )
                    ]
                )
        return ModelResponse(
            parts=[
                TextPart(
                    json.dumps(
                        {
                            "answer": answer,
                            "source_refs": sources,
                            "candidate": candidate,
                        }
                    )
                )
            ]
        )

    transact(TransactionAction.BUY, PositionType.LONG_TERM, "100", "2")
    runtime = StrategyRecordingRuntime(
        PydanticAIRuntime(FunctionModel(model), output_mechanism="NATIVE")
    )
    results = {"GOOG": fixed_quote("GOOG", "210.25")}
    agent = NativeInvestmentAgent(
        CurrentLedger(),
        FixedMarketData(results, {}),
        runtime,
        news=FixedNews({}),
        market_context=FixedMarketContext(CASES_BY_ID["AQ03"].market_context_result),
        clock=lambda: NOW,
    )
    with strategy_fixture(agent) as store:
        thread = store.conversations.start_thread(store.owner)
        for question in ("那我该怎么办？", "我还有 500 美元，可以加仓吗？", PLAN):
            result = store.ask(thread, question)
            assert result.assistant_message is not None
        candidate = result.candidate
        assert candidate is not None and store.active() == []
        store.confirm(candidate, phase="CASE_ACTION")
        store.reconnect()
        thread = store.conversations.start_thread(store.owner)
        assert store.ask(thread, "如果跌到 320 美元呢？").candidate is None
        funding = cast(dict[str, Any], runtime.contexts[-1])["position_funding_snapshots"][0]
        assert Decimal(funding["remaining_target_budget"]) == 100
        assert len(transactions) == 1
        for action, kind, price, expected in (
            (TransactionAction.BUY, PositionType.LONG_TERM, "100", "0"),
            (TransactionAction.SELL, PositionType.LONG_TERM, "150", "100"),
            (TransactionAction.BUY, PositionType.SWING, "50", "100"),
        ):
            transact(action, kind, price, "1")
            results["GOOG"] = fixed_quote("GOOG", "250")
            count = len(transactions)
            assert store.ask(thread, "结合当前持仓和当前市场重新分析 GOOG。").candidate is None
            context = cast(dict[str, Any], runtime.contexts[-1])
            assert Decimal(
                context["position_funding_snapshots"][0]["remaining_target_budget"]
            ) == Decimal(expected)
            assert len(transactions) == count
            assert "250" in json.dumps(observations[-1])
        store.seed(StrategyKind.POSITION_PLAN_V1, {"target_budget": "500"})
        store.ask(thread, "检查目标")
        context = cast(dict[str, Any], runtime.contexts[-1])
        assert Decimal(context["position_funding_snapshots"][0]["remaining_target_budget"]) == 300
        store.seed(StrategyKind.POSITION_PLAN_V1, None, operation=StrategyOperation.INVALIDATE)
        store.ask(thread, "既定目标是什么？")
        assert "position_funding_snapshots" not in runtime.contexts[-1]
        assert store.active() == []
        assert len(transactions) == 4
        assert all("remaining_target_budget" not in json.dumps(e) for e in store.events)
    assert all(schema == schemas[0] for schema in schemas)
    assert all(cast(int, call["model_request_count"]) <= 8 for call in runtime.calls)
