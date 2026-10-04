"""固定 AQ12 / AQ15 一致性 Gate 的外层脚本，不改变冻结 Candidate。"""

import argparse
import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from ask_quality_cases import CASES_BY_ID
from phase4_core_harness import _build_eval_runtime, build_native_agent
from phase4_strategy_fixture import strategy_fixture
from phase4_strategy_freeze import verify_candidate
from phase4_strategy_harness import StrategyRecordingRuntime, _ask, execute_strategy_case

from position_pilot.application.agent_runtime import AgentRuntime

REPEAT_SCHEDULE = (("AQ12", 1), ("AQ12", 2), ("AQ12", 3), ("AQ15", 2), ("AQ15", 3))


def execute_repeat_case(case_id: str, runtime: AgentRuntime) -> dict[str, object]:
    """AQ12 使用当前 Intent Schema 和真实 History；AQ15 复用 Primary 生命周期。"""
    if case_id == "AQ15":
        return execute_strategy_case(case_id, runtime)
    if case_id != "AQ12":
        raise ValueError("有限一致性 Gate 只允许 AQ12 / AQ15")
    recording = StrategyRecordingRuntime(runtime)
    case = CASES_BY_ID[case_id]
    agent = build_native_agent(case, recording)
    turns: list[dict[str, object]] = []
    with strategy_fixture(agent) as store:
        thread = store.conversations.start_thread(store.owner)
        for index, question in enumerate(case.executable_questions, 1):
            turn, _ = _ask(store, recording, thread, question, index)
            turns.append(turn)
            if turn["execution_status"] != "COMPLETED":
                break
        active = store.active()
    completed = len(turns) == 3 and all(t["execution_status"] == "COMPLETED" for t in turns)
    return {
        "case_id": case_id,
        "scenario_execution_scope": "FULL",
        "execution_status": "COMPLETED" if completed else "REQUEST_FAILED",
        "expected_turn_count": 3,
        "completed_turn_count": sum(t["execution_status"] == "COMPLETED" for t in turns),
        "turns": turns,
        "not_run_turns": [
            {"turn_index": i, "question": q, "reason": "PRIOR_REQUEST_NOT_COMPLETED"}
            for i, q in enumerate(case.executable_questions, 1)
            if i > len(turns)
        ],
        "active_final": active,
        "behavioral_status": "PENDING"
        if completed
        else (
            "FAIL" if any(t.get("behavioral_status") == "FAIL" for t in turns) else "NOT_EVALUATED"
        ),
        "critical_failure_gate": "NOT_EVALUATED",
    }


def verify_primary_reference(primary: Path, candidate: dict[str, object]) -> dict[str, object]:
    """仅引用同配置 AQ15 Primary r1；不复制回答充当新的执行。"""
    if json.loads((primary / "candidate-config.json").read_text()) != candidate:
        raise ValueError("AQ15 Primary r1 与当前冻结配置不同")
    records = [json.loads(line) for line in (primary / "cases.jsonl").read_text().splitlines()]
    record = next(r for r in records if r["case_id"] == "AQ15")
    if record["execution_status"] != "COMPLETED" or record["completed_turn_count"] != 2:
        raise ValueError("AQ15 Primary r1 未完成")
    return {
        "artifact": str(primary),
        "run_id": json.loads((primary / "summary.json").read_text())["run_id"],
        "cases_sha256": hashlib.sha256((primary / "cases.jsonl").read_bytes()).hexdigest(),
        "case_id": "AQ15",
        "repetition_index": 1,
        "behavioral": "参见 Primary Review；不从 COMPLETED 推导 PASS",
    }


def run_repeat_gate(
    *,
    config: Path,
    primary: Path,
    artifact: Path,
    environment: Mapping[str, str],
) -> dict[str, object]:
    """保留所有结果；一次运行失败就停止剩余补考，不增加 Case-level Retry。"""
    candidate = verify_candidate(config)
    reference = verify_primary_reference(primary, candidate)
    if (environment.get("LLM_PROVIDER"), environment.get("LLM_MODEL")) != (
        "GOOGLE_GEMINI",
        "gemini-3.8-flash",
    ):
        raise ValueError("只允许冻结的 GOOGLE_GEMINI / gemini-3.8-flash")
    runtime = _build_eval_runtime(environment)
    if runtime is None:
        raise ValueError("缺少进程 GEMINI_API_KEY；不读取 .env")
    artifact.mkdir(parents=True, exist_ok=False)
    (artifact / "candidate-config.json").write_text(json.dumps(candidate, indent=2) + "\n")
    summary: dict[str, Any] = {
        "run_id": artifact.name,
        "run_kind": "4B_REPEAT",
        "repository_revision": candidate["commit"],
        "schedule": REPEAT_SCHEDULE,
        "planned_ask_count": 13,
        "primary_r1_reference": reference,
        "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "status": "RUN_STARTED",
        "behavioral": "PENDING_HUMAN_REVIEW",
        "critical_failure_gate": "NOT_EVALUATED",
        "results": [],
        "not_run": [],
    }

    def save() -> None:
        (artifact / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
        )

    save()
    for offset, (case_id, repetition) in enumerate(REPEAT_SCHEDULE):
        print(
            json.dumps({"case_id": case_id, "repetition": repetition, "status": "STARTED"}),
            flush=True,
        )
        record = execute_repeat_case(case_id, runtime)
        record["repetition_index"] = repetition
        with (artifact / "cases.jsonl").open("a") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        result = {
            "case_id": case_id,
            "repetition": repetition,
            "execution_status": record["execution_status"],
            "completed_turn_count": record["completed_turn_count"],
        }
        cast(list[object], summary["results"]).append(result)
        print(json.dumps(result), flush=True)
        if record["execution_status"] != "COMPLETED":
            summary["status"] = "STOPPED_FOR_REVIEW"
            summary["not_run"] = REPEAT_SCHEDULE[offset + 1 :]
            save()
            return summary
        save()
    summary["status"] = "RUN_FINISHED"
    save()
    return summary


def main() -> None:
    """预检模式不加载 Provider；凭证仅由用户终端注入。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--primary", type=Path, required=True)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    try:
        if args.plan_only:
            candidate = verify_candidate(args.config)
            verify_primary_reference(args.primary, candidate)
            print("4B Repeat preflight PASS; AQ12 r1/r2/r3 + AQ15 r2/r3; 13 Ask.")
            return
        if args.artifact is None:
            raise ValueError("在线执行必须提供独立 Artifact")
        summary = run_repeat_gate(
            config=args.config,
            primary=args.primary,
            artifact=args.artifact,
            environment=os.environ,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        if summary["status"] != "RUN_FINISHED":
            raise SystemExit(1)
    except Exception as error:
        # 只输出类型，避免 SDK 异常中的 URL 或凭证进入终端。
        print(json.dumps({"status": "ERROR_STOPPED", "exception_type": type(error).__name__}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
