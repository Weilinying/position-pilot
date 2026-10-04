"""AQ07 Eval-only 诊断边界的离线测试。"""

import json
from pathlib import Path

import phase4_aq07_timeout_diagnostic as diagnostic
import pytest
from phase4_aq07_timeout_diagnostic import (
    DiagnosticTrace,
    TimedToolRuntime,
    run_aq07_timeout_diagnostic,
)

from position_pilot.application.agent_runtime import (
    AgentRunBudget,
    AgentRunRequest,
    AgentRunResult,
    AgentRunStatus,
)
from position_pilot.application.llm import LLMMessage, LLMRole


class ScriptedRuntime:
    """不接触模型或工具的固定结果。"""

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        """返回供诊断包装层使用的合法候选。"""

        return AgentRunResult(
            AgentRunStatus.COMPLETED,
            '{"answer":"固定测试回答","source_refs":[]}',
            None,
            (),
            (),
            None,
            1.0,
        )


def test_diagnostic_accepts_only_30_or_60_seconds(tmp_path: Path) -> None:
    """无效预算在创建 Provider Client 和 Artifact 之前被拒绝。"""

    with pytest.raises(ValueError, match="只允许 30 或 60 秒"):
        run_aq07_timeout_diagnostic(
            api_key="fixture-only",
            base_url="https://example.invalid/v1",
            model_name="qwen3.7-max",
            timeout_seconds=45,
            artifact_dir=tmp_path / "not-created",
        )
    assert not (tmp_path / "not-created").exists()


def test_existing_artifact_is_rejected_before_model_call(tmp_path: Path) -> None:
    """避免付费调用后才发现目标目录已存在，保留历史 Artifact。"""

    artifact_dir = tmp_path / "existing"
    artifact_dir.mkdir()
    with pytest.raises(FileExistsError):
        run_aq07_timeout_diagnostic(
            api_key="fixture-only",
            base_url="https://example.invalid/v1",
            model_name="qwen3.7-max",
            timeout_seconds=30,
            artifact_dir=artifact_dir,
        )


def test_diagnostic_separates_initial_run_and_repair() -> None:
    """诊断包装层不会改变 Agent Request 或隐式触发 Repair。"""

    trace = DiagnosticTrace()
    runtime = TimedToolRuntime(ScriptedRuntime(), trace)
    request = AgentRunRequest(
        messages=(LLMMessage(LLMRole.USER, "固定问题"),),
        tools=(),
        budget=AgentRunBudget(3, 0, 30.0),
    )

    assert runtime.run(request).status is AgentRunStatus.COMPLETED
    assert trace.phase == "INITIAL"
    assert runtime.run(request).status is AgentRunStatus.COMPLETED
    assert trace.phase == "REPAIR"
    assert request.budget.wall_clock_seconds == 30.0


def test_diagnostic_wires_budget_and_writes_reduced_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """60 秒只传给 Eval Case，Artifact 不写 Key、Prompt 或 Tool 参数。"""

    observed_budget: list[float] = []

    def fake_execute(*args: object, wall_clock_budget_seconds: float) -> dict[str, object]:
        observed_budget.append(wall_clock_budget_seconds)
        return {
            "execution_status": "COMPLETED",
            "turns": [
                {
                    "answer": "固定回答",
                    "latency_ms": 100.0,
                    "repair_count": 0,
                    "response_status": "OK",
                    "tool_trace": [
                        {"name": "get_current_quote", "arguments": {"key": "secret-marker"}}
                    ],
                    "usage": {"total_tokens": "UNKNOWN"},
                }
            ],
        }

    monkeypatch.setattr(diagnostic, "execute_native_case", fake_execute)
    artifact_dir = tmp_path / "diag-60"
    artifact = run_aq07_timeout_diagnostic(
        api_key="fixture-only-key",
        base_url="https://example.invalid/v1",
        model_name="qwen3.7-max",
        timeout_seconds=60,
        artifact_dir=artifact_dir,
    )

    assert observed_budget == [60]
    assert artifact["timeout_seconds"] == 60
    saved = (artifact_dir / "diagnostic.json").read_text(encoding="utf-8")
    assert json.loads(saved)["case"]["tool_names"] == ["get_current_quote"]
    assert "fixture-only-key" not in saved
    assert "secret-marker" not in saved
    assert "固定问题" not in saved
