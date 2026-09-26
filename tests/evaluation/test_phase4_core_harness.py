"""Phase 4 4A Eval 入口的离线 Contract；不调用真实模型。"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import pytest
from ask_quality_cases import CASES_BY_ID
from ask_quality_phase4_manifest import PHASE4_CORE_CASE_IDS, PHASE4_RESEARCH_CASE_IDS
from behavioral_harness import USER_ID
from phase4_core_harness import (
    CORE_REPEAT_CASE_IDS,
    PRIMARY_CASE_IDS,
    RUN_PHASE4_EVAL_ENV,
    RecordingAgentRuntime,
    build_native_agent,
    run_phase4_evaluation,
    selected_phase4_case_ids,
)

from position_pilot.application.agent_runtime import AgentRunRequest, AgentRunResult, AgentRunStatus


@dataclass(slots=True)
class ScriptedRuntime:
    """只返回合法 Portfolio 回答的本地 Native Runtime。"""

    requests: list[AgentRunRequest] = field(default_factory=list)

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        self.requests.append(request)
        return AgentRunResult(
            AgentRunStatus.COMPLETED,
            json.dumps(
                {"answer": "固定测试回答。", "source_refs": [{"type": "PORTFOLIO_SNAPSHOT"}]}
            ),
            None,
            (),
            (),
            None,
            1.0,
        )


def test_phase4_case_selection_is_independent_of_legacy_scope() -> None:
    """4A Primary 与 Repeat 使用 0.2 Scope，Research 独立未测量。"""

    assert tuple(PRIMARY_CASE_IDS[:13]) == PHASE4_CORE_CASE_IDS
    assert PRIMARY_CASE_IDS[-1] == "AQ04"
    assert "AQ06" in CORE_REPEAT_CASE_IDS
    assert selected_phase4_case_ids({"EVAL_REPETITION_INDEX": "2"}) == CORE_REPEAT_CASE_IDS
    with pytest.raises(ValueError, match="只能选择 Core"):
        selected_phase4_case_ids({"PHASE4_CASE_IDS": PHASE4_RESEARCH_CASE_IDS[0]})


def test_offline_manifest_keeps_core_not_run_and_research_not_measured() -> None:
    """没有显式在线 Opt-in 时不伪造 Core 质量或 Research 能力。"""

    result = cast(dict[str, Any], run_phase4_evaluation(environment={}))
    records = {item["case_id"]: item for item in result["records"]}
    summary = result["summary"]

    assert summary["core_full"]["target_case_count"] == 13
    assert summary["core_full"]["completed_case_count"] == 0
    assert summary["core_full"]["request_success_rate"] is None
    assert records["AQ06"]["evidence_status"] == "NOT_RUN"
    assert all(
        records[case_id]["evidence_status"] == "NOT_MEASURED"
        for case_id in PHASE4_RESEARCH_CASE_IDS
    )
    assert summary["research_gate"]["evidence_status"] == "NOT_MEASURED"


def test_eval_only_agent_budget_can_compare_prior_30_second_ceiling() -> None:
    """普通 4A Fixture 使用获批 60 秒，诊断仍可单独观察旧 30 秒。"""

    default_runtime = ScriptedRuntime()
    diagnostic_runtime = ScriptedRuntime()
    case = CASES_BY_ID["AQ07"]
    build_native_agent(case, default_runtime).answer_with_history(
        USER_ID, case.executable_questions[0], ()
    )
    build_native_agent(
        case, diagnostic_runtime, wall_clock_budget_seconds=30.0
    ).answer_with_history(USER_ID, case.executable_questions[0], ())

    assert default_runtime.requests[0].budget.wall_clock_seconds == 60.0
    assert diagnostic_runtime.requests[0].budget.wall_clock_seconds == 30.0


def test_fixture_runner_uses_native_agent_and_preserves_unknown_usage(tmp_path: Path) -> None:
    """Fixture 回答只验证 Native 执行路径与 Artifact，不冒充真实评分。"""

    runtime = ScriptedRuntime()
    artifact_dir = tmp_path / "phase4-evidence"
    result = cast(
        dict[str, Any],
        run_phase4_evaluation(
            environment={
                RUN_PHASE4_EVAL_ENV: "1",
                "PHASE4_CASE_IDS": "AQ20",
                "PHASE4_ARTIFACT_DIR": str(artifact_dir),
                "EVAL_RUN_ID": "offline-test",
                "LLM_API_KEY": "fixture-only-never-transmitted",
            },
            runtime_factory=lambda _: runtime,
        ),
    )
    record = next(item for item in result["records"] if item["case_id"] == "AQ20")

    assert len(runtime.requests) == 1
    assert record["execution_status"] == "COMPLETED"
    assert record["usage"]["total_tokens"] == "UNKNOWN"
    assert result["summary"]["core_full"]["completed_case_count"] == 1
    assert result["metadata"]["native_request_timeout_seconds"] == 60.0
    assert result["metadata"]["wall_clock_budget_seconds"] == 60.0
    assert result["summary"]["latency"]["median_ms"] is not None
    assert (artifact_dir / "manifest.json").is_file()
    assert (artifact_dir / "cases.jsonl").is_file()
    assert (artifact_dir / "summary.json").is_file()
    progress = [
        json.loads(line) for line in (artifact_dir / "progress.jsonl").read_text().splitlines()
    ]
    assert progress[-1] == {"status": "RUN_FINISHED", "complete": True}
    assert progress[2]["status"] == "TURN_FINISHED"
    artifacts = "".join(path.read_text(encoding="utf-8") for path in artifact_dir.iterdir())
    assert "fixture-only-never-transmitted" not in artifacts
    assert "prompt_sha256" in artifacts
    assert "tool_contract_sha256" in artifacts
    assert "fixture_manifest_sha256" in artifacts


def test_multiturn_fixture_injects_prior_visible_answer() -> None:
    """连续 Case 第二轮收到前一轮 User / Assistant 历史。"""

    runtime = ScriptedRuntime()
    result = cast(
        dict[str, Any],
        run_phase4_evaluation(
            environment={RUN_PHASE4_EVAL_ENV: "1", "PHASE4_CASE_IDS": "AQ10"},
            runtime_factory=lambda _: RecordingAgentRuntime(runtime),
        ),
    )
    record = next(item for item in result["records"] if item["case_id"] == "AQ10")

    assert len(runtime.requests) >= 2
    assert record["turns"][0]["history_message_count"] == 0
    assert record["turns"][1]["history_message_count"] == 2
    assert record["turns"][0]["runtime_calls"][0]["final_candidate"] is not None


def test_interrupt_preserves_finished_turn_and_blocks_paid_restart(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """第二轮中断不丢失第一轮证据，已有部分结果也拒绝重跑。"""

    class InterruptedRuntime(ScriptedRuntime):
        def run(self, request: AgentRunRequest) -> AgentRunResult:
            if self.requests:
                raise KeyboardInterrupt
            return super().run(request)

    runtime = InterruptedRuntime()
    environment = {
        RUN_PHASE4_EVAL_ENV: "1",
        "PHASE4_CASE_IDS": "AQ10",
        "PHASE4_ARTIFACT_DIR": str(tmp_path),
    }
    with pytest.raises(KeyboardInterrupt):
        run_phase4_evaluation(environment=environment, runtime_factory=lambda _: runtime)
    events = [json.loads(line) for line in (tmp_path / "progress.jsonl").read_text().splitlines()]
    assert [event["status"] for event in events] == [
        "RUN_STARTED",
        "STARTED",
        "TURN_FINISHED",
        "STARTED",
        "INTERRUPTED",
    ]
    assert events[2]["turn"]["answer"] == "固定测试回答。"
    assert not (tmp_path / "summary.json").exists()
    output = capsys.readouterr().out
    assert "TURN_FINISHED" in output
    assert "固定测试回答" not in output
    with pytest.raises(FileExistsError):
        run_phase4_evaluation(environment=environment, runtime_factory=lambda _: pytest.fail())


def test_failed_turn_still_contributes_user_message_to_next_turn() -> None:
    """Eval 历史与生产 Conversation 一致：失败轮不生成 Assistant，但保留 User。"""

    @dataclass(slots=True)
    class FailFirstRuntime(ScriptedRuntime):
        def run(self, request: AgentRunRequest) -> AgentRunResult:
            if not self.requests:
                self.requests.append(request)
                return AgentRunResult(
                    AgentRunStatus.FAILED,
                    None,
                    "MODEL_HTTP_FAILURE",
                    (),
                    (),
                    None,
                    1.0,
                )
            return ScriptedRuntime.run(self, request)

    runtime = FailFirstRuntime()
    result = cast(
        dict[str, Any],
        run_phase4_evaluation(
            environment={RUN_PHASE4_EVAL_ENV: "1", "PHASE4_CASE_IDS": "AQ10"},
            runtime_factory=lambda _: runtime,
        ),
    )
    record = next(item for item in result["records"] if item["case_id"] == "AQ10")

    assert record["turns"][0]["execution_status"] == "REQUEST_FAILED"
    assert record["turns"][1]["history_message_count"] == 1


def test_existing_artifact_is_not_overwritten(tmp_path: Path) -> None:
    """同一 Run 目录须在模型调用前拒绝，避免重复付费且保留证据。"""

    runtime = ScriptedRuntime()
    environment = {
        "PHASE4_ARTIFACT_DIR": str(tmp_path / "run"),
        "EVAL_RUN_ID": "same-run",
        RUN_PHASE4_EVAL_ENV: "1",
        "PHASE4_CASE_IDS": "AQ20",
    }
    run_phase4_evaluation(environment=environment, runtime_factory=lambda _: runtime)
    original_artifact = (tmp_path / "run" / "summary.json").read_text(encoding="utf-8")
    assert len(runtime.requests) == 1
    with pytest.raises(FileExistsError, match="Artifact 已存在"):
        run_phase4_evaluation(environment=environment, runtime_factory=lambda _: runtime)
    assert len(runtime.requests) == 1
    assert (tmp_path / "run" / "summary.json").read_text(encoding="utf-8") == original_artifact
