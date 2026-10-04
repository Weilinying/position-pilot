"""有限 4B 连续 Ask Eval，复用真实 Service 与 4A Runtime/金融 Fixture。"""

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import timedelta
from pathlib import Path
from time import monotonic

from ask_quality_cases import CASES_BY_ID
from phase4_core_harness import (
    RecordingAgentRuntime,
    _build_eval_runtime,
    _repository_revision,
    _sha256,
    _stable_json,
    build_native_agent,
    runtime_readiness_check,
)
from phase4_provider_support import classify_failure
from phase4_strategy_fixture import StrategyFixture, strategy_fixture
from phase4_strategy_freeze import verify_candidate
from phase4_strategy_manifest import STRATEGY_QUESTIONS, strategy_manifest

from position_pilot.application.agent_runtime import AgentRunRequest, AgentRunResult, AgentRuntime
from position_pilot.application.conversation_service import (
    ConversationCompletion,
    ConversationThread,
)
from position_pilot.application.strategy_service import StrategyError
from position_pilot.domain.strategy import StrategyKind, StrategyOperation

RUN_STRATEGY_ENV = "RUN_PHASE4_STRATEGY_EVAL"


@dataclass(slots=True)
class StrategyRecordingRuntime(RecordingAgentRuntime):
    """补充实际注入 Context；仅固定 Fixture，不读取用户密钥或生产数据。"""

    contexts: list[dict[str, object]] = field(default_factory=list)
    prompt_hashes: list[str] = field(default_factory=list)

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        context = json.loads(request.messages[-1].content or "{}")
        self.contexts.append(context)
        self.prompt_hashes.append(
            hashlib.sha256((request.messages[0].content or "").encode()).hexdigest()
        )
        return RecordingAgentRuntime.run(self, request)


def _prepare(store: StrategyFixture, case_id: str) -> None:
    """固定前置条件走真实确认 / 失效接口，不用 Prompt 声称已写入。"""
    if case_id in {"AQ13", "AQ14"}:
        store.seed(
            StrategyKind.INVESTMENT_THESIS_V1,
            {"thesis_text": "长期关注 GOOG 搜索与云业务竞争力；需持续核验。"},
        )
    if case_id == "AQ13":
        store.seed(
            StrategyKind.HOLDING_HORIZON_V1, {"horizon_category": "LONG_TERM", "until": None}
        )
    elif case_id == "AQ14":
        store.seed(StrategyKind.INVESTMENT_THESIS_V1, None, operation=StrategyOperation.INVALIDATE)
        candidate = store.seed(
            StrategyKind.INVESTMENT_THESIS_V1,
            {"thesis_text": "待复核，不自动生效。"},
            confirm=False,
        )
        store.now += timedelta(hours=25)
        store.events.append(
            {
                "phase": "FIXTURE_SETUP",
                "action": "EXPIRE_PENDING",
                "candidate": store.strategies.get(store.owner, candidate.id).model_dump(
                    mode="json"
                ),
            }
        )
    elif case_id == "AQ15":
        store.seed(StrategyKind.POSITION_PLAN_V1, {"target_budget": "300", "currency": "USD"})
    store.reconnect()


def _ask(
    store: StrategyFixture,
    runtime: StrategyRecordingRuntime,
    thread: ConversationThread,
    question: str,
    turn_index: int,
) -> tuple[dict[str, object], ConversationCompletion | None]:
    active_before = store.active()
    started = monotonic()
    offset = len(runtime.calls)
    context_offset = len(runtime.contexts)
    try:
        completion = store.ask(thread, question)
    except Exception as error:
        # 异常类型足以排障；不把 SDK 的 URL、Header 或 Secret 写进 Artifact。
        return {
            "turn_index": turn_index,
            "question": question,
            "execution_status": "REQUEST_FAILED",
            "failure_domain": "BEHAVIORAL" if isinstance(error, StrategyError) else "UNCLASSIFIED",
            "failure_reason": getattr(error, "code", type(error).__name__),
            "behavioral_status": "FAIL" if isinstance(error, StrategyError) else "NOT_EVALUATED",
            "runtime_calls": runtime.calls[offset:],
            "answer": None,
            "latency_ms": round((monotonic() - started) * 1000, 2),
            "active_before": active_before,
            "active_after": store.active(),
        }, None
    calls = runtime.calls[offset:]
    completed = completion.assistant_message is not None
    domain: str | None = None
    reason: str | None = None
    if not completed:
        last = calls[-1] if calls else {}
        provider_error = last.get("provider_error")
        provider_error = provider_error if isinstance(provider_error, dict) else {}
        domain, reason = classify_failure(
            status=provider_error.get("http_status"),
            message=str(provider_error.get("error_message", "")),
            code=str(last.get("failure_code") or completion.turn.failure_code or "UNKNOWN"),
        )
        if completion.turn.failure_code == "SOURCE_VALIDATION_FAILED":
            domain, reason = "BEHAVIORAL", "FINAL_BUSINESS_VALIDATION_FAILED"
    contexts = runtime.contexts[context_offset:]
    return {
        "turn_index": turn_index,
        "question": question,
        "execution_status": "COMPLETED" if completed else "REQUEST_FAILED",
        "failure_domain": domain,
        "failure_reason": reason,
        "failure_code": completion.turn.failure_code,
        "behavioral_status": "PENDING"
        if completed
        else ("FAIL" if domain == "BEHAVIORAL" else "NOT_EVALUATED"),
        "latency_ms": round((monotonic() - started) * 1000, 2),
        "answer": completion.assistant_message.content if completion.assistant_message else None,
        "sources": [asdict(source) for source in completion.sources],
        "candidate": completion.candidate.model_dump(mode="json") if completion.candidate else None,
        "thread_id": str(thread.id),
        "runtime_calls": calls,
        "runtime_system_prompt_sha256": runtime.prompt_hashes[context_offset:],
        "visible_contexts": contexts,
        "active_before": active_before,
        "active_after": store.active(),
    }, completion


def execute_strategy_case(case_id: str, delegate: AgentRuntime) -> dict[str, object]:
    """只执行当前四个 4B Case，不混入历史成功记录或自动 Repeat。"""
    recording = StrategyRecordingRuntime(delegate)
    agent = build_native_agent(CASES_BY_ID[case_id], recording)
    turns: list[dict[str, object]] = []
    checks: dict[str, object] = {}
    with strategy_fixture(agent) as store:
        _prepare(store, case_id)
        thread = store.conversations.start_thread(store.owner)
        for index, question in enumerate(STRATEGY_QUESTIONS[case_id], 1):
            turn, completion = _ask(store, recording, thread, question, index)
            turns.append(turn)
            if turn["execution_status"] != "COMPLETED":
                # 失败不构成 Assistant 历史，也不执行依赖其成功的确认步骤。
                break
            if case_id == "AQ15" and index == 1:
                candidate = (
                    completion.candidate if isinstance(completion, ConversationCompletion) else None
                )
                valid = (
                    candidate is not None
                    and candidate.operation is StrategyOperation.INVALIDATE
                    and candidate.kind is StrategyKind.POSITION_PLAN_V1
                    and candidate.scope.key == "GOOG:LONG_TERM"
                )
                checks["invalidation_candidate_matches_requested_scope"] = valid
                if not valid:
                    checks["lifecycle_blocker"] = (
                        "NO_VALID_INVALIDATION_CANDIDATE; 后续 Ask 不运行，不伪造失效"
                    )
                    break
                assert candidate is not None
                store.confirm(candidate, phase="CASE_ACTION")
                store.reconnect()
                thread = store.conversations.start_thread(store.owner)
        checks["active_final_count"] = len(store.active())
        events = list(store.events)
    contexts = recording.contexts
    checks["pending_not_injected"] = all("pending_intent_candidates" not in c for c in contexts)
    checks["portfolio_context_unchanged"] = (
        len({_stable_json(c["portfolio_snapshot"]) for c in contexts if "portfolio_snapshot" in c})
        <= 1
    )
    failed = any(t["execution_status"] != "COMPLETED" for t in turns)
    complete = len(turns) == len(STRATEGY_QUESTIONS[case_id]) and not failed
    return {
        "case_id": case_id,
        "scenario_execution_scope": "FULL",
        "execution_status": "COMPLETED"
        if complete
        else ("REQUEST_FAILED" if failed else "INCOMPLETE"),
        "completed_turn_count": sum(t["execution_status"] == "COMPLETED" for t in turns),
        "expected_turn_count": len(STRATEGY_QUESTIONS[case_id]),
        "not_run_turns": [
            {
                "turn_index": i,
                "question": q,
                "execution_status": "NOT_RUN",
                "reason": "DEPENDENT_LIFECYCLE_OR_PRIOR_REQUEST_NOT_COMPLETED",
            }
            for i, q in enumerate(STRATEGY_QUESTIONS[case_id], 1)
            if i > len(turns)
        ],
        "turns": turns,
        "lifecycle_events": events,
        "deterministic_checks": checks,
        "behavioral_status": "PENDING"
        if complete
        else (
            "FAIL"
            if "lifecycle_blocker" in checks
            or any(t.get("behavioral_status") == "FAIL" for t in turns)
            else "NOT_EVALUATED"
        ),
        "critical_failure_gate": "NOT_EVALUATED",
        "rubric": "PENDING_HUMAN_REVIEW",
    }


def selected_strategy_cases(environment: Mapping[str, str]) -> tuple[str, ...]:
    selected = tuple(
        s.strip()
        for s in environment.get("PHASE4_CASE_IDS", ",".join(STRATEGY_QUESTIONS)).split(",")
        if s.strip()
    )
    if (
        not selected
        or set(selected) - set(STRATEGY_QUESTIONS)
        or len(set(selected)) != len(selected)
    ):
        raise ValueError("4B 只允许不重复的 AQ13,AQ14,AQ15,AQ16")
    return selected


def run_strategy_evaluation(
    *,
    environment: Mapping[str, str] | None = None,
    runtime: AgentRuntime | None = None,
) -> dict[str, object]:
    """独立 Artifact；真实 Runtime 必须显式 opt-in，离线注入 Runtime 可验证装配。"""
    values = os.environ if environment is None else environment
    selected = selected_strategy_cases(values)
    enabled = values.get(RUN_STRATEGY_ENV) == "1"
    if enabled and (
        values.get("LLM_PROVIDER") != "GOOGLE_GEMINI"
        or values.get("LLM_MODEL") != "gemini-3.8-flash"
    ):
        raise ValueError("本轮 4B 仅允许 GOOGLE_GEMINI / gemini-3.8-flash")
    artifact = Path(values["PHASE4_ARTIFACT_DIR"]) if values.get("PHASE4_ARTIFACT_DIR") else None
    if enabled and (artifact is None or not values.get("EVAL_RUN_ID")):
        raise ValueError("在线 4B 必须指定独立 EVAL_RUN_ID / PHASE4_ARTIFACT_DIR")
    if artifact is not None:
        artifact.mkdir(parents=True, exist_ok=True)
        if any(
            (artifact / name).exists()
            for name in ("manifest.json", "cases.jsonl", "summary.json", "progress.jsonl")
        ):
            raise ValueError("Artifact 已存在，不覆盖或重跑")
    frozen_config: dict[str, object] | None = None
    if enabled and runtime is None:
        config_path = values.get("PHASE4_CANDIDATE_CONFIG")
        if not config_path:
            raise ValueError("在线 4B 必须指定 PHASE4_CANDIDATE_CONFIG")
        frozen_config = verify_candidate(Path(config_path))
    delegate = (
        runtime if runtime is not None else (_build_eval_runtime(values) if enabled else None)
    )
    if enabled and delegate is None:
        raise ValueError("缺少进程 GEMINI_API_KEY；不读取 .env")
    records: list[dict[str, object]] = []
    for case_id in selected:
        if delegate is None:
            records.append(
                {
                    "case_id": case_id,
                    "execution_status": "NOT_RUN",
                    "behavioral_status": "NOT_EVALUATED",
                    "critical_failure_gate": "NOT_EVALUATED",
                    "turns": [],
                }
            )
            continue
        print(json.dumps({"case_id": case_id, "status": "STARTED"}), flush=True)
        record = execute_strategy_case(case_id, delegate)
        records.append(record)
        serialized = _stable_json(record) + "\n"
        if artifact is not None:
            with (artifact / "cases.jsonl").open("a") as file:
                file.write(serialized)
        print(
            json.dumps(
                {
                    "case_id": case_id,
                    "execution_status": record["execution_status"],
                    "completed_turn_count": record["completed_turn_count"],
                }
            ),
            flush=True,
        )
    summary: dict[str, object] = {
        "candidate_config": frozen_config,
        "run_id": values.get("EVAL_RUN_ID", "OFFLINE"),
        "run_kind": "4B_PRIMARY",
        "repository_revision": _repository_revision(),
        "manifest_sha256": _sha256(strategy_manifest()),
        "provider": values.get("LLM_PROVIDER", "NOT_RUN"),
        "model": values.get("LLM_MODEL", "NOT_RUN"),
        "selected_cases": selected,
        "completed_case_count": sum(r["execution_status"] == "COMPLETED" for r in records),
        "behavioral": "PENDING_HUMAN_REVIEW" if delegate else "NOT_EVALUATED",
        "critical_failure_gate": "NOT_EVALUATED",
        "repeat": "NOT_RUN",
        "research": "DEFERRED",
        "runtime_readiness": runtime_readiness_check(),
        "online_requested": enabled,
        "execution_kind": "ONLINE" if enabled else "OFFLINE_FIXTURE",
    }
    if artifact is not None:
        (artifact / "manifest.json").write_text(_stable_json(strategy_manifest()) + "\n")
        (artifact / "summary.json").write_text(_stable_json(summary) + "\n")
    return {"summary": summary, "records": records}
