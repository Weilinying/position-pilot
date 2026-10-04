"""持续意图的输出接缝使用真实 FunctionModel，不调用在线 Provider。"""

import json
from typing import Literal

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from position_pilot.application.agent_runtime import AgentRunBudget, AgentRunRequest, AgentRunStatus
from position_pilot.application.llm import LLMMessage, LLMResponseFormat, LLMRole
from position_pilot.domain.strategy import PositionPlanPayload
from position_pilot.integrations.pydantic_ai_runtime import PydanticAIRuntime

DRAFT = {
    "operation": "UPSERT",
    "scope": {"ticker": "GOOG", "position_type": "LONG_TERM"},
    "kind": "POSITION_PLAN_V1",
    "payload": {"target_budget": "300", "currency": "USD"},
    "origin": "USER_STATED_INTENT",
    "evidence_quote": "长期配置 300 美元",
    "replaces_candidate_id": None,
    "replaces_candidate_revision": None,
}


@pytest.mark.parametrize("mechanism", ["NATIVE", "TOOL"])
@pytest.mark.parametrize(("enabled", "candidate"), [(False, None), (True, None), (True, DRAFT)])
def test_optional_candidate_keeps_existing_final_answer_contract(
    mechanism: Literal["NATIVE", "TOOL"], enabled: bool, candidate: dict[str, object] | None
) -> None:
    schemas: list[dict[str, object]] = []

    def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages
        output = info.model_request_parameters.output_object
        schemas.append(
            output.json_schema
            if output is not None
            else info.output_tools[0].parameters_json_schema
        )
        data: dict[str, object] = {"answer": "草案未确认，不会生效。", "source_refs": []}
        if enabled:
            data["candidate"] = candidate
        return ModelResponse(
            parts=[TextPart(json.dumps(data))]
            if mechanism == "NATIVE"
            else [ToolCallPart(info.output_tools[0].name, data)]
        )

    request = AgentRunRequest(
        messages=(
            LLMMessage(LLMRole.SYSTEM, "只返回可核对事实。"),
            LLMMessage(LLMRole.USER, "长期配置 300 美元"),
        ),
        tools=(),
        budget=AgentRunBudget(1, 0, 60),
        response_format=LLMResponseFormat.JSON_OBJECT,
        strategy_candidates_enabled=enabled,
    )
    runtime = PydanticAIRuntime(FunctionModel(model), output_mechanism=mechanism)
    result = runtime.run(request)
    assert result.status is AgentRunStatus.COMPLETED
    assert result.final_candidate is not None
    assert set(json.loads(result.final_candidate)) == {"answer", "source_refs"}
    properties = schemas[0]["properties"]
    assert isinstance(properties, dict)
    assert ("candidate" in properties) is enabled
    if candidate is not None:
        assert result.strategy_draft is not None
        assert isinstance(result.strategy_draft.payload, PositionPlanPayload)
        assert result.strategy_draft.payload.target_budget == 300
    else:
        assert result.strategy_draft is None
