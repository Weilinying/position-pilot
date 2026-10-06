"""固定 Gemini Production Regression 的离线门禁与 Artifact 测试。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import gemini_production_regression as regression
import gemini_regression_candidate as regression_candidate
import httpx
import pytest
from ask_quality_cases import CASES_BY_ID
from gemini_production_regression import (
    NATIVE_CASE_IDS,
    _safe_value,
    main,
    run_online,
)
from gemini_regression_candidate import CASE_IDS, EXPECTED_TURN_COUNT
from phase4_core_harness import RecordingAgentRuntime
from phase4_strategy_manifest import STRATEGY_QUESTIONS
from pydantic import PostgresDsn, SecretStr
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from position_pilot.application.investment_agent import (
    InvestmentAnswer,
    InvestmentFailureCode,
    InvestmentRequestFailure,
    InvestmentResponseStatus,
)
from position_pilot.application.native_investment_agent import NativeInvestmentAgent
from position_pilot.application.source_registry import ContextSource, ContextSourceType
from position_pilot.config import Settings
from position_pilot.integrations.pydantic_ai_runtime import PydanticAIRuntime


@pytest.fixture(autouse=True)
def deny_live_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """離線測試中未 Mock 的 HTTP Transport 必須立刻失敗。"""

    async def blocked(
        transport: httpx.AsyncHTTPTransport, request: httpx.Request
    ) -> httpx.Response:
        pytest.fail("Production Regression 离线测试禁止真实网络连接")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", blocked)


def _good_candidate() -> dict[str, object]:
    return {
        "candidate_id": "frozen-regression",
        "parent_smoke_candidate": {"candidate_id": "frozen-smoke"},
    }


def _valid_settings(key: str) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=PostgresDsn("postgresql+psycopg://unused:unused@localhost/unused"),
        llm_provider="GOOGLE_GEMINI",
        llm_model="gemini-3.8-flash",
        gemini_api_key=SecretStr(key),
    )


def _record(case_id: str) -> dict[str, object]:
    expected = (
        len(CASES_BY_ID[case_id].executable_questions)
        if case_id in NATIVE_CASE_IDS
        else len(STRATEGY_QUESTIONS[case_id])
    )
    if case_id in NATIVE_CASE_IDS:
        return {
            "case_id": case_id,
            "execution_status": "COMPLETED",
            "turns": [{"execution_status": "COMPLETED"} for _ in range(expected)],
        }
    return {
        "case_id": case_id,
        "execution_status": "COMPLETED",
        "completed_turn_count": expected,
        "expected_turn_count": expected,
        "turns": [],
    }


def test_fixed_selection_is_eight_cases_and_twelve_turns() -> None:
    assert CASE_IDS == ("AQ06", "AQ12", "AQ13", "AQ14", "AQ15", "AQ16", "AQ17a", "AQ17b")
    expected_turns = sum(
        len(CASES_BY_ID[case_id].executable_questions) for case_id in NATIVE_CASE_IDS
    )
    expected_turns += sum(len(STRATEGY_QUESTIONS[case_id]) for case_id in STRATEGY_QUESTIONS)
    assert expected_turns == EXPECTED_TURN_COUNT
    assert len(set(CASE_IDS)) == len(CASE_IDS)


def test_preflight_never_builds_settings_or_production_runtime(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(regression, "verify_candidate_file", lambda: _good_candidate())
    monkeypatch.setattr(
        regression,
        "make_settings",
        lambda key: pytest.fail("Preflight 不得构造 Settings"),
    )
    monkeypatch.setattr(
        regression,
        "create_pydantic_ai_runtime",
        lambda settings: pytest.fail("Preflight 不得创建 Runtime Client"),
    )
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    result = main(["--preflight"])

    assert result == 0
    report = json.loads(capsys.readouterr().out)
    assert report["online"] is False
    assert report["candidate_id"] == "frozen-regression"


def test_missing_key_does_not_create_artifact_or_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(regression, "verify_candidate_file", lambda: _good_candidate())
    monkeypatch.setattr(
        regression,
        "create_pydantic_ai_runtime",
        lambda settings: pytest.fail("缺少 Key 时不得创建 Runtime Client"),
    )
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    artifact = tmp_path / "not-created"

    result = run_online(artifact, {regression.RUN_ENV: "1"})

    assert result == 2
    assert not artifact.exists()
    report = json.loads(capsys.readouterr().out)
    assert report == {"status": "BLOCKED", "failure_code": "GEMINI_API_KEY_REQUIRED"}


def test_existing_artifact_is_never_overwritten(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    artifact = tmp_path / "existing"
    artifact.mkdir()
    prior = artifact / "marker.txt"
    prior.write_text("keep")
    monkeypatch.setattr(
        regression,
        "verify_candidate_file",
        lambda path: pytest.fail("既有路径必须先拒绝"),
    )

    result = run_online(artifact, {regression.RUN_ENV: "1"})

    assert result == 2
    assert prior.read_text() == "keep"
    assert json.loads(capsys.readouterr().out)["failure_code"] == "ARTIFACT_ALREADY_EXISTS"


def test_validation_error_keeps_manifest_and_only_writes_safe_type(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(regression, "verify_candidate_file", lambda: _good_candidate())
    monkeypatch.setattr(
        regression,
        "make_settings",
        lambda key: Settings(
            _env_file=None,  # type: ignore[call-arg]
            database_url=PostgresDsn("postgresql+psycopg://unused:unused@localhost/unused"),
            native_llm_request_timeout_seconds=0,
        ),
    )
    monkeypatch.setattr(
        regression,
        "create_pydantic_ai_runtime",
        lambda settings: pytest.fail("Settings ValidationError 后不得创建 Runtime"),
    )
    artifact = tmp_path / "validation-failed"
    secret_marker = "never-write-this-key"

    result = run_online(
        artifact,
        {regression.RUN_ENV: "1", "GEMINI_API_KEY": secret_marker},
    )

    assert result == 1
    manifest = json.loads((artifact / "manifest.json").read_text())
    summary = json.loads((artifact / "summary.json").read_text())
    assert manifest["case_ids"] == list(CASE_IDS)
    assert summary["failure_type"] == "ValidationError"
    assert "failure_message" not in summary
    assert secret_marker not in (artifact / "manifest.json").read_text()
    assert secret_marker not in (artifact / "summary.json").read_text()
    assert json.loads(capsys.readouterr().out)["status"] == "FAILED"


def test_online_dispatches_fixed_harnesses_through_production_factory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    factory_calls: list[Settings] = []
    native_calls: list[str] = []
    strategy_calls: list[str] = []
    model = FunctionModel(
        lambda messages, info: ModelResponse(parts=(TextPart("fixture"),)),
        model_name="offline-factory-test",
    )
    runtime = PydanticAIRuntime(
        model,
        provider_name="GOOGLE_GEMINI",
        model_name="gemini-3.8-flash",
        output_mechanism="NATIVE",
    )
    monkeypatch.setattr(regression, "verify_candidate_file", lambda: _good_candidate())
    monkeypatch.setattr(regression, "make_settings", _valid_settings)

    def create_runtime(settings: Settings) -> PydanticAIRuntime:
        factory_calls.append(settings)
        return runtime

    def native_case(
        case: Any, recorder: RecordingAgentRuntime, *, progress: Any = None
    ) -> dict[str, object]:
        native_calls.append(case.id)
        recorder.calls.append(
            {
                "model_request_count": 1,
                "tool_attempt_count": 0,
                "exposed_tools": ["get_current_quote"],
            }
        )
        if progress is not None:
            progress({"case_id": case.id, "turn_index": 1, "status": "STARTED"})
        return _record(case.id)

    def strategy_case(case_id: str, delegate: RecordingAgentRuntime) -> dict[str, object]:
        strategy_calls.append(case_id)
        delegate.calls.append(
            {
                "model_request_count": 1,
                "tool_attempt_count": 0,
                "exposed_tools": ["get_current_quote"],
            }
        )
        return _record(case_id)

    monkeypatch.setattr(regression, "create_pydantic_ai_runtime", create_runtime)
    monkeypatch.setattr(regression, "execute_native_case", native_case)
    monkeypatch.setattr(regression, "execute_strategy_case", strategy_case)
    artifact = tmp_path / "successful-execution"

    result = run_online(
        artifact,
        {regression.RUN_ENV: "1", "GEMINI_API_KEY": "offline-key"},
    )

    assert result == 0
    assert len(factory_calls) == 1
    assert native_calls == ["AQ06", "AQ12", "AQ17a", "AQ17b"]
    assert strategy_calls == ["AQ13", "AQ14", "AQ15", "AQ16"]
    summary = json.loads((artifact / "summary.json").read_text())
    assert summary["attempted_case_count"] == 8
    assert summary["completed_case_count"] == 8
    assert summary["completed_turn_count"] == 12
    assert summary["actual_model_request_count"] == 8
    assert summary["actual_tool_attempt_count"] == 0
    assert summary["search_free"] is True
    assert summary["behavioral_status"] == "PENDING_HUMAN_REVIEW"
    assert summary["research"] == "DEFERRED"
    assert summary["earnings_diagnostic"] == "NOT_TESTED"
    assert summary["repeat"] == "NOT_RUN"
    assert sorted(path.stem for path in (artifact / "cases").glob("*.json")) == sorted(CASE_IDS)
    assert json.loads(capsys.readouterr().out)["status"] == "COMPLETED"


def test_offline_function_model_executes_all_real_cases_and_sql_lifecycles(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """真實雙 Harness 只測機械執行，不把 FunctionModel 當成 Gemini 行為證據。"""

    def answer(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        current = messages[-1]
        assert isinstance(current, ModelRequest)
        user_part = next(
            part for part in reversed(current.parts) if isinstance(part, UserPromptPart)
        )
        assert isinstance(user_part.content, str)
        try:
            payload = json.loads(user_part.content)
        except json.JSONDecodeError:
            payload = {}
        question = payload.get("question", user_part.content)
        output_schema = info.model_request_parameters.output_object
        assert output_schema is not None
        structured: dict[str, object] = {
            "answer": "固定 FunctionModel 结果，仅验证运行路径。",
            "source_refs": [{"type": "PORTFOLIO_SNAPSHOT"}],
        }
        if "candidate" in output_schema.json_schema.get("properties", {}):
            candidate: dict[str, object] | None = None
            if question == STRATEGY_QUESTIONS["AQ15"][0]:
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
            structured["candidate"] = candidate
        return ModelResponse(parts=(TextPart(json.dumps(structured, ensure_ascii=False)),))

    runtime = PydanticAIRuntime(
        FunctionModel(answer, model_name="offline-function-model"),
        provider_name="GOOGLE_GEMINI",
        model_name="gemini-3.8-flash",
        output_mechanism="NATIVE",
    )
    factory_settings: list[Settings] = []

    def create_runtime(settings: Settings) -> PydanticAIRuntime:
        factory_settings.append(settings)
        return runtime

    monkeypatch.setattr(regression, "verify_candidate_file", lambda: _good_candidate())
    monkeypatch.setattr(regression, "make_settings", _valid_settings)
    monkeypatch.setattr(regression, "create_pydantic_ai_runtime", create_runtime)
    artifact = tmp_path / "real-harness-fixtures"

    result = run_online(
        artifact,
        {regression.RUN_ENV: "1", "GEMINI_API_KEY": "offline-only-key"},
    )

    assert result == 0
    assert len(factory_settings) == 1
    summary = json.loads((artifact / "summary.json").read_text())
    assert summary["completed_case_count"] == 8
    assert summary["completed_turn_count"] == 12
    assert summary["all_expected_turns_completed"] is True
    assert summary["search_free"] is True
    assert summary["actual_model_request_count"] == 12
    assert summary["actual_tool_attempt_count"] == 0
    assert summary["application_repair_count"] == 0
    assert summary["behavioral_status"] == "PENDING_HUMAN_REVIEW"
    assert summary["production_database_access"] is False
    assert summary["strategy_database"] == "ISOLATED_SQLITE_IN_MEMORY"
    records = {
        case_id: json.loads((artifact / "cases" / f"{case_id}.json").read_text())
        for case_id in CASE_IDS
    }
    assert records["AQ15"]["lifecycle_events"][-1]["phase"] == "CASE_ACTION"
    assert records["AQ15"]["execution_status"] == "COMPLETED"
    assert all(record["execution_status"] == "COMPLETED" for record in records.values())


def test_turn_safe_serializer_drops_provider_raw_fields() -> None:
    safe = _safe_value(
        {
            "failure_code": "MODEL_HTTP_FAILURE",
            "provider_error": {
                "http_status": 401,
                "error_code": "AUTH_FAILED",
                "error_message": "secret=never-write-this-key",
                "body": {"token": "never-write-this-key"},
                "headers": {"authorization": "never-write-this-key"},
            },
        }
    )

    serialized = json.dumps(safe)
    assert "MODEL_HTTP_FAILURE" in serialized
    assert "AUTH_FAILED" in serialized
    assert "error_message" not in serialized
    assert "never-write-this-key" not in serialized


def test_case_failure_does_not_stop_later_cases_and_dependencies_remain_not_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(regression, "verify_candidate_file", lambda: _good_candidate())
    monkeypatch.setattr(regression, "make_settings", _valid_settings)
    runtime = PydanticAIRuntime(
        FunctionModel(
            lambda messages, info: ModelResponse(parts=(TextPart("fixture"),)),
            model_name="offline-factory-test",
        ),
        provider_name="GOOGLE_GEMINI",
        model_name="gemini-3.8-flash",
        output_mechanism="NATIVE",
    )
    monkeypatch.setattr(regression, "create_pydantic_ai_runtime", lambda settings: runtime)

    def native_case(
        case: Any, recorder: RecordingAgentRuntime, *, progress: Any = None
    ) -> dict[str, object]:
        if case.id == "AQ06":
            raise RuntimeError("raw credential must not be serialized")
        return _record(case.id)

    def strategy_case(case_id: str, delegate: RecordingAgentRuntime) -> dict[str, object]:
        if case_id == "AQ15":
            return {
                "case_id": case_id,
                "execution_status": "REQUEST_FAILED",
                "completed_turn_count": 1,
                "expected_turn_count": 2,
                "not_run_turns": [{"turn_index": 2, "execution_status": "NOT_RUN"}],
                "turns": [{"execution_status": "REQUEST_FAILED"}],
            }
        return _record(case_id)

    monkeypatch.setattr(regression, "execute_native_case", native_case)
    monkeypatch.setattr(regression, "execute_strategy_case", strategy_case)
    artifact = tmp_path / "case-failure"

    result = run_online(artifact, {regression.RUN_ENV: "1", "GEMINI_API_KEY": "test-key"})

    assert result == 1
    failed = json.loads((artifact / "cases/AQ06.json").read_text())
    assert failed["failure_type"] == "RuntimeError"
    assert "raw credential" not in (artifact / "cases/AQ06.json").read_text()
    later = json.loads((artifact / "cases/AQ17b.json").read_text())
    assert later["execution_status"] == "COMPLETED"
    dependent = json.loads((artifact / "cases/AQ15.json").read_text())
    assert dependent["not_run_turns"][0]["execution_status"] == "NOT_RUN"
    summary = json.loads((artifact / "summary.json").read_text())
    assert summary["completed_turn_count"] == 10
    assert summary["all_expected_turns_completed"] is False


@pytest.mark.parametrize("failed_turn", [1, 2])
def test_aq12_failed_turn_stops_dependent_requests_and_persists_not_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failed_turn: int,
) -> None:
    artifact = tmp_path / "aq12-chain-break"
    (artifact / "cases").mkdir(parents=True)
    invoked_questions: list[str] = []

    def answer_with_history(
        agent: NativeInvestmentAgent,
        user_id: Any,
        question: str,
        history: Any,
    ) -> InvestmentAnswer | InvestmentRequestFailure:
        invoked_questions.append(question)
        if len(invoked_questions) == failed_turn:
            return InvestmentRequestFailure(
                InvestmentFailureCode.LLM_PROVIDER_UNAVAILABLE,
                "offline fixture failure",
            )
        return InvestmentAnswer(
            status=InvestmentResponseStatus.OK,
            answer="固定离线回答",
            sources=(ContextSource(ContextSourceType.PORTFOLIO_SNAPSHOT, "OK"),),
        )

    monkeypatch.setattr(NativeInvestmentAgent, "answer_with_history", answer_with_history)
    recording = RecordingAgentRuntime(delegate=object())  # type: ignore[arg-type]

    record = regression._run_case("AQ12", recording, artifact)

    questions = CASES_BY_ID["AQ12"].executable_questions
    assert invoked_questions == list(questions[:failed_turn])
    assert record["execution_status"] == "REQUEST_FAILED"
    assert record["behavioral_status"] == "NOT_EVALUATED"
    turns = record["turns"]
    assert isinstance(turns, list)
    assert len(turns) == failed_turn
    assert turns[-1]["execution_status"] == "REQUEST_FAILED"
    not_run = record["not_run_turns"]
    assert isinstance(not_run, list)
    assert [turn["turn_index"] for turn in not_run] == list(
        range(failed_turn + 1, len(questions) + 1)
    )
    assert all(turn["execution_status"] == "NOT_RUN" for turn in not_run)
    persisted = json.loads((artifact / "cases/AQ12.json").read_text())
    assert len(persisted["turns"]) == failed_turn
    assert len(persisted["not_run_turns"]) == len(questions) - failed_turn
    progress = [json.loads(line) for line in (artifact / "progress.jsonl").read_text().splitlines()]
    assert any(event["status"] == "TURN_FINISHED" for event in progress)
    assert any(event["status"] == "DEPENDENT_TURNS_NOT_RUN" for event in progress)


def test_regression_candidate_detects_source_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "fixture.py"
    source.write_text("version one")
    candidate_path = tmp_path / "candidate.json"
    smoke = {"candidate_id": "frozen-smoke", "source_commit": "parent-commit"}
    monkeypatch.setattr(regression_candidate, "ROOT", tmp_path)
    monkeypatch.setattr(regression_candidate, "SOURCE_PATHS", ("fixture.py",))
    monkeypatch.setattr(regression_candidate, "CANDIDATE_PATH", tmp_path / "smoke.json")
    monkeypatch.setattr(regression_candidate, "verify_candidate", lambda path: smoke)
    monkeypatch.setattr(
        regression_candidate,
        "_git",
        lambda args: "child-commit" if args == ["rev-parse", "HEAD"] else "fixture-blob",
    )
    monkeypatch.setattr(
        "gemini_regression_candidate.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0),
    )
    hashes = {"fixture.py": hashlib.sha256(b"version one").hexdigest()}
    blobs = {"fixture.py": "fixture-blob"}
    parent = {
        "candidate_id": smoke["candidate_id"],
        "source_commit": smoke["source_commit"],
        "candidate_sha256": regression_candidate.candidate_sha256(smoke),
    }
    record = {
        "candidate_id": "gemini-production-regression-2026-10-06-v1",
        "status": "PREPARED_OFFLINE_AWAITING_USER_EXECUTION",
        "source_commit": "child-commit",
        "source_files_sha256": hashes,
        "source_git_blobs": blobs,
        "parent_smoke_candidate": parent,
        "run_profile": regression_candidate.run_profile(),
    }
    candidate_path.write_text(json.dumps(record))

    assert (
        regression_candidate.verify_candidate_file(candidate_path)["candidate_id"]
        == record["candidate_id"]
    )
    source.write_text("version two")
    with pytest.raises(ValueError, match="SOURCE_FILE_DRIFT"):
        regression_candidate.verify_candidate_file(candidate_path)
