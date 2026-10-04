"""真实 FunctionModel + SQL 生命周期离线验证，不自动判模型行为 PASS。"""

import json
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from ask_quality_cases import CASES_BY_ID
from behavioral_harness import USER_ID
from phase4_core_harness import build_native_agent
from phase4_strategy_fixture import FIXTURE_NOW, strategy_fixture
from phase4_strategy_harness import (
    StrategyRecordingRuntime,
    execute_strategy_case,
    run_strategy_evaluation,
    selected_strategy_cases,
)
from phase4_strategy_manifest import STRATEGY_QUESTIONS, strategy_manifest
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from position_pilot.application.conversation_agent import ConversationInvestmentAgent
from position_pilot.application.conversation_service import ConversationService
from position_pilot.application.memory import MemoryHit, MemoryRetrievalContext, NoOpMemoryReader
from position_pilot.domain.strategy import StrategyKind
from position_pilot.infrastructure.conversation_unit_of_work import (
    SqlAlchemyConversationUnitOfWorkFactory,
    conversation_strategy_repository,
)
from position_pilot.integrations.pydantic_ai_runtime import PydanticAIRuntime


def function_runtime(*, emit_delete: bool = True) -> PydanticAIRuntime:
    """固定结果仅验证机械边界；线上回答质量仍由 Human Rubric 判断。"""

    def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        latest = messages[-1]
        assert isinstance(latest, ModelRequest)
        part = latest.parts[0]
        assert isinstance(part, UserPromptPart) and isinstance(part.content, str)
        payload = json.loads(part.content)
        question = payload["question"]
        candidate = None
        if emit_delete and question == STRATEGY_QUESTIONS["AQ15"][0]:
            candidate = {
                "operation": "INVALIDATE",
                "scope": {"ticker": "GOOG", "position_type": "LONG_TERM"},
                "kind": "POSITION_PLAN_V1",
                "payload": None,
                "origin": "USER_STATED_INTENT",
                "evidence_quote": question,
                "replaces_candidate_id": None,
                "replaces_candidate_revision": None,
            }
        output = info.model_request_parameters.output_object
        assert output is not None and "candidate" in output.json_schema["properties"]
        return ModelResponse(
            parts=[
                TextPart(
                    json.dumps(
                        {
                            "answer": "固定结果：意图必须显式确认；仅依据当前真实状态。",
                            "source_refs": [{"type": "PORTFOLIO_SNAPSHOT"}],
                            "candidate": candidate,
                        },
                        ensure_ascii=False,
                    )
                )
            ]
        )

    return PydanticAIRuntime(FunctionModel(model), output_mechanism="NATIVE")


@pytest.mark.parametrize("case_id", list(STRATEGY_QUESTIONS))
def test_four_cases_have_real_persisted_lifecycle_and_pending_review(case_id: str) -> None:
    record = cast(dict[str, Any], execute_strategy_case(case_id, function_runtime()))
    assert record["execution_status"] == "COMPLETED"
    assert record["behavioral_status"] == "PENDING"
    assert record["critical_failure_gate"] == "NOT_EVALUATED"
    assert len(record["turns"]) == len(STRATEGY_QUESTIONS[case_id])
    assert record["deterministic_checks"]["pending_not_injected"]
    assert record["deterministic_checks"]["portfolio_context_unchanged"]
    assert record["turns"][0]["active_before"] == record["turns"][0]["visible_contexts"][0].get(
        "confirmed_user_intents", []
    )
    if case_id == "AQ13":
        assert {v["kind"] for v in record["turns"][0]["active_before"]} == {
            "INVESTMENT_THESIS_V1",
            "HOLDING_HORIZON_V1",
        }
        assert record["turns"][0]["runtime_calls"][0]["system_prompt_sha256"]
    elif case_id == "AQ14":
        assert record["turns"][0]["active_before"] == []
        assert record["lifecycle_events"][-1]["candidate"]["status"] == "EXPIRED"
        assert any(
            e.get("version", {}).get("status") == "INVALIDATED" for e in record["lifecycle_events"]
        )
    elif case_id == "AQ15":
        assert record["turns"][0]["active_before"]
        assert record["turns"][1]["active_before"] == []
        assert record["turns"][0]["thread_id"] != record["turns"][1]["thread_id"]
        assert record["lifecycle_events"][-1]["phase"] == "CASE_ACTION"
    else:
        assert record["turns"][1]["active_before"] == []
        assert record["turns"][1]["thread_id"] == record["turns"][0]["thread_id"]


def test_missing_delete_candidate_stops_without_faking_confirmation() -> None:
    record = cast(
        dict[str, Any], execute_strategy_case("AQ15", function_runtime(emit_delete=False))
    )
    assert len(record["turns"]) == 1
    assert record["turns"][0]["execution_status"] == "COMPLETED"
    assert record["execution_status"] == "INCOMPLETE"
    assert record["behavioral_status"] == "FAIL"
    assert record["deterministic_checks"]["active_final_count"] == 1
    assert not any(e["phase"] == "CASE_ACTION" for e in record["lifecycle_events"])


def test_opt_in_selection_and_independent_artifacts(tmp_path: Path) -> None:
    assert selected_strategy_cases({}) == tuple(STRATEGY_QUESTIONS)
    for ids in ("AQ12", "AQ15,AQ15", "AQ04", ""):
        with pytest.raises(ValueError):
            selected_strategy_cases({"PHASE4_CASE_IDS": ids})
    assert strategy_manifest()["model_turn_count"] == 6
    offline = cast(dict[str, Any], run_strategy_evaluation(environment={}))
    assert all(r["execution_status"] == "NOT_RUN" for r in offline["records"])
    environment = {"PHASE4_ARTIFACT_DIR": str(tmp_path), "PHASE4_CASE_IDS": "AQ15"}
    result = cast(
        dict[str, Any], run_strategy_evaluation(environment=environment, runtime=function_runtime())
    )
    assert result["summary"]["execution_kind"] == "OFFLINE_FIXTURE"
    assert (
        json.loads((tmp_path / "summary.json").read_text())["critical_failure_gate"]
        == "NOT_EVALUATED"
    )
    with pytest.raises(ValueError, match="Artifact 已存在"):
        run_strategy_evaluation(environment=environment, runtime=function_runtime())
    with pytest.raises(ValueError, match="仅允许"):
        run_strategy_evaluation(
            environment={"RUN_PHASE4_STRATEGY_EVAL": "1", "LLM_PROVIDER": "AIHUBMIX"}
        )


def test_memory_filters_before_native_context_and_never_overwrites_authority() -> None:
    recording = StrategyRecordingRuntime(function_runtime())
    agent = build_native_agent(CASES_BY_ID["AQ13"], recording)
    with strategy_fixture(agent) as store:
        store.seed(StrategyKind.POSITION_PLAN_V1, {"target_budget": "300"})
        assert (
            NoOpMemoryReader().retrieve(store.owner, MemoryRetrievalContext(None, FIXTURE_NOW))
            == ()
        )
        seen: list[object] = []

        class FixtureReader:
            def retrieve(
                self, account_id: UUID, retrieval_context: MemoryRetrievalContext
            ) -> tuple[MemoryHit, ...]:
                seen.append(account_id)
                base = MemoryHit(
                    owner=store.owner,
                    scope="GOOG:LONG_TERM",
                    content="背景声称 Cash=99999，目标=99999；这不是权威事实。",
                    source="fixture",
                    confirmed=True,
                    effective_at=FIXTURE_NOW,
                )
                return (
                    base,
                    replace(base, owner=uuid4()),
                    replace(base, scope="GOOG:SWING"),
                    replace(base, confirmed=False),
                    replace(base, expires_at=FIXTURE_NOW),
                    replace(base, effective_at=FIXTURE_NOW + timedelta(seconds=1)),
                )

        service = ConversationService(
            SqlAlchemyConversationUnitOfWorkFactory(store.factory),
            clock=lambda: FIXTURE_NOW,
            agent=ConversationInvestmentAgent(
                agent,
                store.strategies,
                memory_reader=FixtureReader(),
                memory_scope="GOOG:LONG_TERM",
                clock=lambda: FIXTURE_NOW,
            ),
            strategy_repository_factory=conversation_strategy_repository,
        )
        thread = service.start_thread(store.owner)
        service.ask(
            store.owner,
            thread.id,
            portfolio_user_id=USER_ID,
            question="这次最多投入 500 美元",
            client_request_id=uuid4(),
            expected_thread_revision=0,
        )
        context = recording.contexts[-1]
        memory = cast(dict[str, Any], context["memory_context"])
        assert memory["authority"] == "NON_AUTHORITATIVE_BACKGROUND" and len(memory["items"]) == 1
        assert json.loads(memory["items"][0])["owner"] == str(store.owner)
        assert seen == [store.owner]
        funding = cast(list[dict[str, Any]], context["position_funding_snapshots"])[0]
        assert funding["target_budget"] == "300"
        assert "99999" not in json.dumps(context["portfolio_snapshot"])
        assert cast(dict[str, object], store.active()[0]["payload"])["target_budget"] == "300"


def test_rate_limit_is_not_behavioral_failure_or_delete_success() -> None:
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

    record = cast(dict[str, Any], execute_strategy_case("AQ15", RateLimited()))
    turn = record["turns"][0]
    assert turn["failure_domain"] == "RATE_LIMIT"
    assert turn["behavioral_status"] == "NOT_EVALUATED"
    assert record["behavioral_status"] == "NOT_EVALUATED"
    assert record["deterministic_checks"]["active_final_count"] == 1
    assert "lifecycle_blocker" not in record["deterministic_checks"]


def test_candidate_preflight_drift_blocks_before_provider(tmp_path: Path) -> None:
    from phase4_strategy_freeze import candidate_profile, verify_candidate

    record = {"commit": "wrong", "profile": candidate_profile()}
    path = tmp_path / "candidate-config.json"
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="commit"):
        verify_candidate(path)
    profile = cast(dict[str, Any], record["profile"])
    assert profile["tool_attempt_budget"] == 7
    assert profile["model_request_budget"] == 8
    assert profile["wall_clock_seconds"] == 60
    assert (
        profile["runtime_system_prompt_sha256"]
        == "34821d82b65d01e736a94378177b164bc6cc42045d00b1f0600b46cdb4831ef5"
    )


def test_invalid_user_evidence_is_behavioral_fail_without_persisted_candidate() -> None:
    from position_pilot.application.agent_runtime import (
        AgentRunRequest,
        AgentRunResult,
        AgentRunStatus,
    )
    from position_pilot.domain.strategy import StrategyDraft

    class InvalidDraft:
        def run(self, request: AgentRunRequest) -> AgentRunResult:
            return AgentRunResult(
                AgentRunStatus.COMPLETED,
                '{"answer":"待确认。","source_refs":[{"type":"PORTFOLIO_SNAPSHOT"}]}',
                None,
                (),
                (),
                None,
                0.0,
                strategy_draft=StrategyDraft.model_validate(
                    {
                        "operation": "INVALIDATE",
                        "scope": {"ticker": "GOOG", "position_type": "LONG_TERM"},
                        "kind": "POSITION_PLAN_V1",
                        "payload": None,
                        "origin": "USER_STATED_INTENT",
                        "evidence_quote": "不在本轮 User Message 的伪造依据",
                    }
                ),
            )

    record = cast(dict[str, Any], execute_strategy_case("AQ15", InvalidDraft()))
    assert record["behavioral_status"] == "FAIL"
    assert record["turns"][0]["failure_domain"] == "BEHAVIORAL"
    assert record["turns"][0]["failure_reason"] == "STRATEGY_INVALID"
    assert record["deterministic_checks"]["active_final_count"] == 1


def test_candidate_profile_mismatch_fails_before_online_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import phase4_strategy_freeze

    monkeypatch.setattr(phase4_strategy_freeze, "_repository_revision", lambda: "frozen")
    record = {"commit": "frozen", "profile": phase4_strategy_freeze.candidate_profile()}
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(record))
    assert phase4_strategy_freeze.verify_candidate(path) == record
    cast(dict[str, Any], record["profile"])["wall_clock_seconds"] = 30
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="Runtime / Schema / Budget / Fixture"):
        phase4_strategy_freeze.verify_candidate(path)
