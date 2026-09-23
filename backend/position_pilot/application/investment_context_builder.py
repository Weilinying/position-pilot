"""组合 Investment Agent 所需的 Provider-neutral Context。"""

import json
from dataclasses import dataclass

from position_pilot.application.investment_answer import structured_answer_schema
from position_pilot.application.investment_context import (
    M5_CONTEXT_CAPABILITIES,
    InvestmentPortfolioContext,
    PortfolioSnapshot,
    m3_decision_context,
    m3_response_contract,
)
from position_pilot.application.llm import LLMMessage, LLMRole
from position_pilot.application.position_funding import (
    PositionPlanIntent,
    build_position_funding_snapshots,
)


@dataclass(frozen=True, slots=True)
class InvestmentContextBuilder:
    """从 Application-owned Facts 构造稳定的初始消息。"""

    system_prompt: str

    def build(
        self,
        portfolio_context: InvestmentPortfolioContext,
        question: str,
        *,
        position_plan_intents: tuple[PositionPlanIntent, ...] = (),
        memory_context: tuple[str, ...] = (),
        conversation_history: tuple[LLMMessage, ...] = (),
    ) -> tuple[LLMMessage, ...]:
        """构造初始消息；Conversation 只接受用户可见的 User / Assistant 历史。"""

        if any(
            message.role not in {LLMRole.USER, LLMRole.ASSISTANT}
            or message.content is None
            or message.tool_calls
            or message.tool_call_id is not None
            for message in conversation_history
        ):
            raise ValueError("Conversation History 只能包含纯文本 User / Assistant Message")

        snapshot = PortfolioSnapshot.from_context(portfolio_context)
        payload: dict[str, object] = {
            "question": question,
            "context_capabilities": M5_CONTEXT_CAPABILITIES.as_dict(),
            "decision_context": m3_decision_context(),
            "portfolio_snapshot": snapshot.as_dict(),
            "available_source_reference": {"type": "PORTFOLIO_SNAPSHOT"},
            "response_contract": m3_response_contract(),
            "structured_answer_schema": structured_answer_schema(),
        }
        if position_plan_intents:
            payload["position_funding_snapshots"] = [
                item.as_dict()
                for item in build_position_funding_snapshots(
                    portfolio_context.portfolio,
                    position_plan_intents,
                )
            ]
        if memory_context:
            payload["memory_context"] = {
                "authority": "NON_AUTHORITATIVE_BACKGROUND",
                "items": list(memory_context),
            }
        return (
            LLMMessage(LLMRole.SYSTEM, self.system_prompt),
            *conversation_history,
            LLMMessage(
                LLMRole.USER,
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
            ),
        )
