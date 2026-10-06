"""固定 Gemini Production Regression；不改变既有 Smoke 或 Ask Harness。"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from ask_quality_cases import CASES_BY_ID
from gemini_production_smoke import make_settings
from gemini_regression_candidate import (
    CASE_IDS,
    EXPECTED_TURN_COUNT,
    REGRESSION_CANDIDATE_PATH,
    candidate_payload,
    candidate_sha256,
    verify_candidate_file,
)
from gemini_regression_candidate import (
    stable_json as _stable_json,
)
from phase4_core_harness import RecordingAgentRuntime, execute_native_case
from phase4_strategy_harness import execute_strategy_case
from phase4_strategy_manifest import STRATEGY_QUESTIONS
from pydantic import ValidationError

from position_pilot.application.investment_agent import CONTEXT_TOOLS
from position_pilot.integrations.pydantic_ai_runtime import create_pydantic_ai_runtime

RUN_ENV = "RUN_GEMINI_PRODUCTION_REGRESSION"
NATIVE_CASE_IDS = frozenset({"AQ06", "AQ12", "AQ17a", "AQ17b"})
FINANCIAL_TOOL_NAMES = frozenset(tool.name for tool in CONTEXT_TOOLS)
SENSITIVE_KEYS = frozenset(
    {
        "error_message",
        "raw_exception",
        "exception_body",
        "body",
        "headers",
        "header",
        "api_key",
        "gemini_api_key",
        "llm_api_key",
        "authorization",
    }
)


class _AQ12DependencyFailed(Exception):
    """AQ12 前序请求失败后，停止执行依赖后续轮次。"""


def manifest_payload(candidate: Mapping[str, object]) -> dict[str, object]:
    """生成在线 Artifact 首写 Manifest，不包含凭据或用户自由输入。"""

    return {
        "candidate_id": candidate.get("candidate_id"),
        "candidate_sha256": candidate_sha256(candidate),
        "parent_smoke_candidate": candidate.get("parent_smoke_candidate"),
        "source_commit": candidate.get("source_commit"),
        "source_files_sha256": candidate.get("source_files_sha256"),
        "source_git_blobs": candidate.get("source_git_blobs"),
        "provider": "GOOGLE_GEMINI",
        "model": "gemini-3.8-flash",
        "output_mechanism": "NATIVE",
        "case_ids": list(CASE_IDS),
        "expected_turn_count": EXPECTED_TURN_COUNT,
        "case_execution": "ONE_EACH_NO_REPEAT",
        "production_budget": {
            "initial_native_model_requests_per_turn": 8,
            "tool_attempts_per_turn": 7,
            "wall_clock_seconds_per_turn": 60.0,
            "existing_source_repair_max_additional_requests": 1,
            "existing_source_repair_tool_attempts": 0,
            "conservative_total_model_request_upper_bound": 108,
            "framework_retries": 0,
            "provider_http_attempts": 1,
        },
        "research": "DEFERRED",
        "earnings_diagnostic": "NOT_TESTED",
        "behavioral_status": "PENDING_HUMAN_REVIEW",
        "production_database_access": False,
        "strategy_database": "ISOLATED_SQLITE_IN_MEMORY",
        "evidence_scope": "FIXTURE_ONLY_NOT_LIVE_MARKET_ACCEPTANCE",
    }


def _safe_value(value: object) -> object:
    """刪除 Shared Harness 記錄中的原始 Provider 錯誤與敏感欄位。"""

    if isinstance(value, Mapping):
        return {
            str(key): _safe_value(item)
            for key, item in value.items()
            if str(key).casefold() not in SENSITIVE_KEYS
        }
    if isinstance(value, list | tuple):
        return [_safe_value(item) for item in value]
    return value


def _case_turn_count(record: Mapping[str, object]) -> int:
    if record.get("case_id") in NATIVE_CASE_IDS:
        turns = record.get("turns")
        return (
            sum(
                turn.get("execution_status") == "COMPLETED"
                for turn in turns
                if isinstance(turn, Mapping)
            )
            if isinstance(turns, list)
            else 0
        )
    value = record.get("completed_turn_count")
    return value if isinstance(value, int) else 0


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(_safe_value(value), ensure_ascii=False, indent=2, default=str) + "\n"
    )


def _write_progress(artifact: Path, event: Mapping[str, object]) -> None:
    with (artifact / "progress.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(_stable_json(_safe_value(event)) + "\n")


def _run_case(
    case_id: str,
    recording: RecordingAgentRuntime,
    artifact: Path,
) -> dict[str, object]:
    audit_start = len(recording.calls)
    case_path = artifact / "cases" / f"{case_id}.json"
    record: dict[str, object] = {
        "case_id": case_id,
        "execution_status": "RUNNING",
        "expected_turn_count": len(CASES_BY_ID[case_id].executable_questions)
        if case_id in NATIVE_CASE_IDS
        else len(STRATEGY_QUESTIONS[case_id]),
        "turns": [],
        "behavioral_status": "PENDING_HUMAN_REVIEW",
        "rubric": "PENDING_HUMAN_REVIEW",
    }
    _write_json(case_path, record)
    _write_progress(artifact, {"case_id": case_id, "status": "CASE_STARTED"})
    try:
        if case_id in NATIVE_CASE_IDS:
            partial_turns: list[dict[str, object]] = []

            def progress(event: dict[str, object]) -> None:
                turn = event.get("turn")
                if isinstance(turn, dict):
                    safe_turn = cast(dict[str, object], _safe_value(turn))
                    partial_turns.append(safe_turn)
                    record["turns"] = list(partial_turns)
                    _write_json(case_path, record)
                _write_progress(artifact, event)
                if (
                    case_id == "AQ12"
                    and isinstance(turn, dict)
                    and turn.get("execution_status") == "REQUEST_FAILED"
                ):
                    questions = CASES_BY_ID[case_id].executable_questions
                    failed_turn_index = cast(int, turn["turn_index"])
                    record["execution_status"] = "REQUEST_FAILED"
                    record["behavioral_status"] = (
                        "FAIL"
                        if any(item.get("behavioral_status") == "FAIL" for item in partial_turns)
                        else "NOT_EVALUATED"
                    )
                    record["not_run_turns"] = [
                        {
                            "turn_index": index,
                            "question": question,
                            "execution_status": "NOT_RUN",
                            "reason": "DEPENDENT_PRIOR_REQUEST_FAILED",
                        }
                        for index, question in enumerate(questions, start=1)
                        if index > failed_turn_index
                    ]
                    _write_json(case_path, record)
                    _write_progress(
                        artifact,
                        {
                            "case_id": case_id,
                            "status": "DEPENDENT_TURNS_NOT_RUN",
                            "after_turn_index": failed_turn_index,
                        },
                    )
                    raise _AQ12DependencyFailed

            result = execute_native_case(CASES_BY_ID[case_id], recording, progress=progress)
            record = cast(dict[str, object], _safe_value(result))
        else:
            result = execute_strategy_case(case_id, recording)
            record = cast(dict[str, object], _safe_value(result))
        record["runtime_audit"] = _safe_value(recording.calls[audit_start:])
        if record.get("behavioral_status") in {None, "PENDING"}:
            record["behavioral_status"] = "PENDING_HUMAN_REVIEW"
        record["rubric"] = "PENDING_HUMAN_REVIEW"
    except _AQ12DependencyFailed:
        record["runtime_audit"] = _safe_value(recording.calls[audit_start:])
    except Exception as error:  # noqa: BLE001 - 单 Case 异常不携带原文并继续后续 Case。
        record.update(
            execution_status="REQUEST_EXCEPTION",
            failure_type=type(error).__name__,
            failure_code="CASE_EXECUTION_EXCEPTION",
            runtime_audit=_safe_value(recording.calls[audit_start:]),
        )
    record["case_id"] = case_id
    record.setdefault("turns", [])
    _write_json(case_path, record)
    _write_progress(
        artifact,
        {
            "case_id": case_id,
            "status": "CASE_FINISHED",
            "execution_status": record.get("execution_status"),
            "completed_turn_count": _case_turn_count(record),
        },
    )
    return record


def run_online(artifact_dir: Path, environment: Mapping[str, str] | None = None) -> int:
    """运行固定 Online Regression；凭据只从传入 Process Environment 获取。"""

    values = os.environ if environment is None else environment
    if values.get(RUN_ENV) != "1":
        print(_stable_json({"status": "BLOCKED", "failure_code": "ONLINE_OPT_IN_REQUIRED"}))
        return 2
    if artifact_dir.exists():
        print(_stable_json({"status": "BLOCKED", "failure_code": "ARTIFACT_ALREADY_EXISTS"}))
        return 2
    try:
        candidate = verify_candidate_file()
    except Exception as error:  # noqa: BLE001 - 只输出安全异常类型。
        print(_stable_json({"status": "BLOCKED", "failure_type": type(error).__name__}))
        return 2
    api_key = values.get("GEMINI_API_KEY", "")
    if not api_key.strip():
        print(_stable_json({"status": "BLOCKED", "failure_code": "GEMINI_API_KEY_REQUIRED"}))
        return 2
    try:
        artifact_dir.mkdir(parents=True, exist_ok=False)
        (artifact_dir / "cases").mkdir()
        manifest = manifest_payload(candidate)
        _write_json(artifact_dir / "manifest.json", manifest)
        _write_progress(artifact_dir, {"status": "RUN_STARTED", "case_ids": CASE_IDS})
    except Exception as error:  # noqa: BLE001 - 不覆盖路径且仅记录安全类型。
        print(_stable_json({"status": "BLOCKED", "failure_type": type(error).__name__}))
        return 2
    try:
        settings = make_settings(api_key)
    except ValidationError as error:
        validation_summary = {
            "execution_status": "FAILED_BEFORE_CASES",
            "failure_type": type(error).__name__,
            "provider": "GOOGLE_GEMINI",
            "model": "gemini-3.8-flash",
            "behavioral_status": "PENDING_HUMAN_REVIEW",
            "research": "DEFERRED",
            "earnings_diagnostic": "NOT_TESTED",
            "repeat": "NOT_RUN",
        }
        _write_json(artifact_dir / "summary.json", validation_summary)
        print(_stable_json({"status": "FAILED", "failure_type": type(error).__name__}))
        return 1
    try:
        production_runtime = create_pydantic_ai_runtime(settings)
        if (
            production_runtime.provider_name != "GOOGLE_GEMINI"
            or production_runtime.model_name != "gemini-3.8-flash"
            or production_runtime._output_mechanism != "NATIVE"
        ):
            raise ValueError("PRODUCTION_RUNTIME_MISMATCH")
    except Exception as error:  # noqa: BLE001 - 不保存 Provider 异常正文。
        setup_summary = {
            "execution_status": "FAILED_BEFORE_CASES",
            "failure_type": type(error).__name__,
            "failure_code": "PRODUCTION_RUNTIME_SETUP_FAILED",
            "behavioral_status": "PENDING_HUMAN_REVIEW",
        }
        _write_json(artifact_dir / "summary.json", setup_summary)
        print(_stable_json({"status": "FAILED", "failure_type": type(error).__name__}))
        return 1
    recording = RecordingAgentRuntime(production_runtime)
    records: list[dict[str, object]] = []
    for case_id in CASE_IDS:
        records.append(_run_case(case_id, recording, artifact_dir))
    attempts = [
        attempt
        for record in records
        for attempt in cast(list[dict[str, object]], record.get("runtime_audit", []))
    ]
    all_search_free = bool(attempts) and all(
        isinstance(attempt.get("exposed_tools"), list)
        and all(name in FINANCIAL_TOOL_NAMES for name in cast(list[str], attempt["exposed_tools"]))
        for attempt in attempts
    )
    request_values = [item.get("model_request_count") for item in attempts]
    attempt_values = [item.get("tool_attempt_count") for item in attempts]
    model_requests: int | str = (
        sum(cast(int, value) for value in request_values)
        if request_values and all(isinstance(value, int) for value in request_values)
        else "UNKNOWN"
    )
    tool_attempts: int | str = (
        sum(cast(int, value) for value in attempt_values)
        if attempt_values and all(isinstance(value, int) for value in attempt_values)
        else "UNKNOWN"
    )
    completed_cases = sum(record.get("execution_status") == "COMPLETED" for record in records)
    completed_turns = sum(_case_turn_count(record) for record in records)
    repair_count = 0
    for record in records:
        turns = record.get("turns")
        if not isinstance(turns, list):
            continue
        for turn in turns:
            if not isinstance(turn, Mapping):
                continue
            recorded_repairs = turn.get("repair_count")
            if isinstance(recorded_repairs, int):
                repair_count += recorded_repairs
            else:
                calls = turn.get("runtime_calls")
                if isinstance(calls, list):
                    repair_count += max(0, len(calls) - 1)
    execution_complete = (
        completed_cases == len(CASE_IDS)
        and completed_turns == EXPECTED_TURN_COUNT
        and all_search_free
        and model_requests != "UNKNOWN"
        and tool_attempts != "UNKNOWN"
    )
    summary: dict[str, object] = {
        "execution_status": "COMPLETED" if execution_complete else "PARTIAL_OR_FAILED",
        "case_ids": list(CASE_IDS),
        "attempted_case_count": len(records),
        "expected_case_count": len(CASE_IDS),
        "completed_case_count": completed_cases,
        "completed_turn_count": completed_turns,
        "expected_turn_count": EXPECTED_TURN_COUNT,
        "all_expected_turns_completed": completed_turns == EXPECTED_TURN_COUNT,
        "search_free": all_search_free,
        "actual_model_request_count": model_requests,
        "actual_tool_attempt_count": tool_attempts,
        "application_repair_count": repair_count,
        "provider": "GOOGLE_GEMINI",
        "model": "gemini-3.8-flash",
        "behavioral_status": "PENDING_HUMAN_REVIEW",
        "research": "DEFERRED",
        "earnings_diagnostic": "NOT_TESTED",
        "repeat": "NOT_RUN",
        "production_database_access": False,
        "strategy_database": "ISOLATED_SQLITE_IN_MEMORY",
        "records": {record["case_id"]: record.get("execution_status") for record in records},
    }
    _write_json(artifact_dir / "summary.json", summary)
    _write_progress(
        artifact_dir,
        {"status": "RUN_FINISHED", "summary_status": summary["execution_status"]},
    )
    print(_stable_json({"status": summary["execution_status"], "artifact_dir": str(artifact_dir)}))
    return 0 if execution_complete else 1


def main(argv: list[str] | None = None) -> int:
    """提供离线 Preflight / Freeze 与明确授权的固定 Online Regression。"""

    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--online", action="store_true")
    parser.add_argument("--artifact-dir", type=Path)
    args = parser.parse_args(argv)
    if args.online:
        if args.artifact_dir is None:
            print(_stable_json({"status": "BLOCKED", "failure_code": "ARTIFACT_DIR_REQUIRED"}))
            return 2
        return run_online(args.artifact_dir)
    try:
        if args.freeze:
            if REGRESSION_CANDIDATE_PATH.exists():
                raise FileExistsError("CANDIDATE_ALREADY_EXISTS")
            payload = candidate_payload()
            REGRESSION_CANDIDATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            REGRESSION_CANDIDATE_PATH.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print(
                _stable_json(
                    {"status": "FROZEN_OFFLINE", "candidate": str(REGRESSION_CANDIDATE_PATH)}
                )
            )
            return 0
        candidate = verify_candidate_file()
    except Exception as error:  # noqa: BLE001 - 离线门禁不输出异常正文。
        print(_stable_json({"status": "FAIL", "failure_type": type(error).__name__}))
        return 1
    print(
        _stable_json(
            {
                "status": "PREFLIGHT_PASS_AWAITING_USER_EXECUTION",
                "online": False,
                "candidate_id": candidate.get("candidate_id"),
                "case_ids": CASE_IDS,
                "expected_turn_count": EXPECTED_TURN_COUNT,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
