"""有限补考命令的离线边界，不消耗真实模型额度。"""

import json
from pathlib import Path
from typing import Any, cast

import pytest
from phase4b_repeat_gate import REPEAT_SCHEDULE, execute_repeat_case, run_repeat_gate
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from test_phase4_strategy_harness import function_runtime

from position_pilot.integrations.pydantic_ai_runtime import PydanticAIRuntime


def test_repeat_aq12_uses_current_intent_schema_real_history_and_scoped_fixture() -> None:
    history_counts: list[int] = []

    def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        history_counts.append(sum(isinstance(m, ModelResponse) for m in messages))
        output = info.model_request_parameters.output_object
        assert output is not None and "candidate" in output.json_schema["properties"]
        return ModelResponse(
            parts=[
                TextPart(
                    json.dumps(
                        {
                            "answer": "固定历史回答。",
                            "source_refs": [{"type": "PORTFOLIO_SNAPSHOT"}],
                            "candidate": None,
                        }
                    )
                )
            ]
        )

    runtime = PydanticAIRuntime(FunctionModel(model), output_mechanism="NATIVE")
    record = cast(dict[str, Any], execute_repeat_case("AQ12", runtime))
    assert record["execution_status"] == "COMPLETED"
    assert history_counts == [0, 1, 2]
    assert len({t["thread_id"] for t in record["turns"]}) == 1
    assert record["active_final"] == []
    assert all(t["candidate"] is None for t in record["turns"])
    assert all(
        t["runtime_system_prompt_sha256"]
        == ["34821d82b65d01e736a94378177b164bc6cc42045d00b1f0600b46cdb4831ef5"]
        for t in record["turns"]
    )
    assert record["behavioral_status"] == "PENDING"


def test_repeat_aq15_keeps_explicit_confirmation_and_new_thread() -> None:
    record = cast(dict[str, Any], execute_repeat_case("AQ15", function_runtime()))
    assert record["execution_status"] == "COMPLETED"
    assert record["turns"][0]["candidate"]["status"] == "PENDING"
    assert record["turns"][0]["active_after"]
    assert record["turns"][1]["active_before"] == []
    assert record["turns"][0]["thread_id"] != record["turns"][1]["thread_id"]
    assert REPEAT_SCHEDULE == (("AQ12", 1), ("AQ12", 2), ("AQ12", 3), ("AQ15", 2), ("AQ15", 3))
    with pytest.raises(ValueError):
        execute_repeat_case("AQ04", function_runtime())


def test_preflight_failure_never_constructs_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import phase4b_repeat_gate

    def reject(path: Path) -> dict[str, object]:
        raise ValueError("冻结漂移")

    def forbidden(environment: object) -> None:
        pytest.fail("预检失败后不得构造 Provider")

    monkeypatch.setattr(phase4b_repeat_gate, "verify_candidate", reject)
    monkeypatch.setattr(phase4b_repeat_gate, "_build_eval_runtime", forbidden)
    with pytest.raises(ValueError, match="冻结漂移"):
        run_repeat_gate(config=tmp_path, primary=tmp_path, artifact=tmp_path, environment={})


def test_failed_repeat_stops_remaining_runs_and_retains_not_evaluated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import phase4b_repeat_gate

    from position_pilot.application.agent_runtime import (
        AgentRunRequest,
        AgentRunResult,
        AgentRunStatus,
    )

    class RateLimited:
        def run(self, request: AgentRunRequest) -> AgentRunResult:
            return AgentRunResult(
                AgentRunStatus.FAILED,
                None,
                "HTTP_429",
                (),
                (),
                None,
                1.0,
                provider_http_status=429,
                provider_error_message="Quota exhausted",
            )

    monkeypatch.setattr(phase4b_repeat_gate, "verify_candidate", lambda path: {"commit": "frozen"})
    monkeypatch.setattr(phase4b_repeat_gate, "verify_primary_reference", lambda path, candidate: {})
    monkeypatch.setattr(
        phase4b_repeat_gate, "_build_eval_runtime", lambda environment: RateLimited()
    )
    artifact = tmp_path / "repeat"
    result = run_repeat_gate(
        config=tmp_path,
        primary=tmp_path,
        artifact=artifact,
        environment={"LLM_PROVIDER": "GOOGLE_GEMINI", "LLM_MODEL": "gemini-3.8-flash"},
    )
    assert result["status"] == "STOPPED_FOR_REVIEW"
    assert len(cast(list[object], result["results"])) == 1
    assert len(cast(list[object], result["not_run"])) == 4
    record = json.loads((artifact / "cases.jsonl").read_text())
    assert len(record["turns"]) == 1
    assert record["behavioral_status"] == "NOT_EVALUATED"
    assert record["turns"][0]["failure_domain"] == "RATE_LIMIT"
