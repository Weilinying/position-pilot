"""Phase 4 4A Core Eval 的 PydanticAI 专用最小入口。

该模块只负责固定 Fixture 的 Capability / Evidence 记录。它不复用 Dataset 0.1
的 Legacy Runtime Harness，也不修改 Production Agent。真实模型运行必须由调用方
显式设置 ``RUN_PHASE4_EVAL=1``；LLM 配置只从当前进程环境读取。
"""

from __future__ import annotations

import hashlib
import json
import os
import statistics
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from time import monotonic
from typing import cast
from uuid import UUID

from ask_quality_cases import CASES_BY_ID, AskQualityCase
from ask_quality_harness import manifest_payload as base_manifest_payload
from ask_quality_phase4_manifest import (
    PHASE4_BASE_MANIFEST_SHA256,
    PHASE4_CASE_TARGETS,
    PHASE4_CORE_CASE_IDS,
    PHASE4_DATASET_VERSION,
    PHASE4_EARNINGS_CASE_IDS,
    PHASE4_RESEARCH_CASE_IDS,
    Phase4CaseTarget,
    phase4_manifest_payload,
)
from behavioral_harness import (
    NOW,
    USER_ID,
    FixedMarketContext,
    FixedMarketData,
    FixedNews,
    FixedPortfolioReader,
)
from pydantic import AnyHttpUrl, PostgresDsn, SecretStr

from position_pilot.application.agent_runtime import (
    AgentRunRequest,
    AgentRunResult,
    AgentRuntime,
)
from position_pilot.application.investment_agent import (
    CONTEXT_TOOLS,
    SYSTEM_PROMPT,
    ContextSource,
    InvestmentAnswer,
    InvestmentRequestFailure,
)
from position_pilot.application.llm import LLMMessage, LLMRole
from position_pilot.application.native_investment_agent import (
    DEFAULT_WALL_CLOCK_BUDGET_SECONDS,
    NativeInvestmentAgent,
)
from position_pilot.config import Settings
from position_pilot.domain.portfolio import CashBalance, PortfolioState
from position_pilot.integrations.pydantic_ai_runtime import create_pydantic_ai_runtime

RUN_PHASE4_EVAL_ENV = "RUN_PHASE4_EVAL"
PHASE4_CASE_IDS_ENV = "PHASE4_CASE_IDS"
PHASE4_ARTIFACT_DIR_ENV = "PHASE4_ARTIFACT_DIR"
EVAL_REPETITION_INDEX_ENV = "EVAL_REPETITION_INDEX"
EVAL_RUN_ID_ENV = "EVAL_RUN_ID"
UNKNOWN = "UNKNOWN"
NOT_MEASURED = "NOT_MEASURED"
DEFAULT_MODEL = "qwen3.7-max"
DEFAULT_PROVIDER = "ALIYUN_MODEL_STUDIO"
DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_TIMEOUT_SECONDS = 30.0

# 4A Primary 只执行 Core FULL 与 Earnings Diagnostic；Research Gate 未批准时
# 仍在 Artifact 中保留明确的 NOT_MEASURED 记录。
CORE_REPEAT_CASE_IDS = ("AQ03", "AQ05", "AQ06", "AQ07", "AQ17a", "AQ17b")
PRIMARY_CASE_IDS = (*PHASE4_CORE_CASE_IDS, *PHASE4_EARNINGS_CASE_IDS)


@dataclass(frozen=True, slots=True)
class Phase4RunMetadata:
    """一次 4A Eval 的可复现且不含 Secret 的运行信息。"""

    dataset_id: str
    dataset_version: str
    base_dataset_version: str
    base_manifest_sha256: str
    phase4_manifest_sha256: str
    base_prompt_sha256: str
    tool_contract_sha256: str
    fixture_manifest_sha256: str
    rubric_version: str
    runtime: str
    conversation_prompt_mode: str
    provider: str
    model: str
    llm_base_url: str
    native_request_timeout_seconds: float
    wall_clock_budget_seconds: float
    run_id: str
    repetition_index: int
    run_kind: str
    started_at: str
    selected_case_ids: tuple[str, ...]
    repository_revision: str

    def as_dict(self) -> dict[str, object]:
        """转换为可写入 JSON 的稳定字段。"""

        return {
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "base_dataset_version": self.base_dataset_version,
            "base_manifest_sha256": self.base_manifest_sha256,
            "phase4_manifest_sha256": self.phase4_manifest_sha256,
            "base_prompt_sha256": self.base_prompt_sha256,
            "tool_contract_sha256": self.tool_contract_sha256,
            "fixture_manifest_sha256": self.fixture_manifest_sha256,
            "rubric_version": self.rubric_version,
            "runtime": self.runtime,
            "conversation_prompt_mode": self.conversation_prompt_mode,
            "provider": self.provider,
            "model": self.model,
            "llm_base_url": self.llm_base_url,
            "native_request_timeout_seconds": self.native_request_timeout_seconds,
            "wall_clock_budget_seconds": self.wall_clock_budget_seconds,
            "run_id": self.run_id,
            "repetition_index": self.repetition_index,
            "run_kind": self.run_kind,
            "started_at": self.started_at,
            "selected_case_ids": list(self.selected_case_ids),
            "repository_revision": self.repository_revision,
        }


@dataclass(slots=True)
class RecordingAgentRuntime:
    """包装 Application Runtime，记录 Tool Trace、Usage、Latency 与 Warning。"""

    delegate: AgentRuntime
    calls: list[dict[str, object]] = field(default_factory=list)

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        """委托一次 Native Run，并保存不含 Prompt Secret 的结构化观察。"""

        started_at = monotonic()
        result = self.delegate.run(request)
        self.calls.append(
            {
                "status": result.status.value,
                "failure_code": result.failure_code,
                "provider_error": (
                    {
                        "http_status": result.provider_http_status,
                        "error_code": result.provider_error_code,
                        "error_message": result.provider_error_message,
                    }
                    if result.provider_http_status is not None
                    else None
                ),
                "framework_error": (
                    {
                        "kind": result.framework_error_kind,
                        "cause": result.framework_error_cause,
                    }
                    if result.framework_error_kind is not None
                    else None
                ),
                "final_candidate": result.final_candidate,
                "latency_ms": result.latency_ms,
                "wall_latency_ms": round((monotonic() - started_at) * 1000, 2),
                "usage": _usage_payload(result.usage),
                "warnings": list(result.warnings),
                "system_prompt_sha256": _sha256(request.messages[0].content),
                "exposed_tools": [binding.definition.name for binding in request.tools],
                "tool_trace": [_tool_trace_payload(item) for item in result.tool_trace],
                "tool_invocation_count": sum(item.invoked_by_model for item in result.tool_trace),
                "provider_fetch_count": sum(
                    item.provider_fetch_count for item in result.tool_trace
                ),
                "source_count": len(result.sources),
            }
        )
        return result


def _stable_json(value: object) -> str:
    """生成用于 Artifact Hash 的稳定 JSON。"""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))


def _sha256(value: object) -> str:
    """返回稳定 JSON 的 SHA-256。"""

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _tool_contract_payload() -> list[dict[str, object]]:
    """记录实际向 Native Runtime 暴露的金融工具定义。"""

    return [
        {"name": tool.name, "description": tool.description, "parameters": tool.parameters}
        for tool in CONTEXT_TOOLS
    ]


def _usage_payload(usage: object | None) -> dict[str, int | str]:
    """没有 Provider Usage 时逐字段保持 UNKNOWN。"""

    if usage is None:
        return {"input_tokens": UNKNOWN, "output_tokens": UNKNOWN, "total_tokens": UNKNOWN}
    return {
        "input_tokens": getattr(usage, "input_tokens", UNKNOWN),
        "output_tokens": getattr(usage, "output_tokens", UNKNOWN),
        "total_tokens": getattr(usage, "total_tokens", UNKNOWN),
    }


def _tool_trace_payload(trace: object) -> dict[str, object]:
    """序列化 AgentToolTrace，保留 Tool Arguments 与失败状态。"""

    return {
        "name": getattr(trace, "name", UNKNOWN),
        "arguments": _json_safe(getattr(trace, "arguments", {})),
        "status": getattr(trace, "status", UNKNOWN),
        "error_code": getattr(trace, "error_code", None),
        "invoked_by_model": getattr(trace, "invoked_by_model", True),
        "provider_fetch_count": getattr(trace, "provider_fetch_count", 1),
        "sources": _json_safe(getattr(trace, "sources", ())),
    }


def _json_safe(value: object) -> object:
    """将固定 Provider / Runtime 对象转换成 JSON 值。"""

    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Decimal | UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [_json_safe(item) for item in value]
    return str(value)


def _safe_base_url(value: str) -> str:
    """只记录 Endpoint 的 Scheme / Host / Path，不记录用户信息或 Query。"""

    from urllib.parse import urlsplit, urlunsplit

    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.hostname is None:
        return UNKNOWN
    hostname = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    netloc = f"{hostname}:{parsed.port}" if parsed.port is not None else hostname
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def _repository_revision() -> str:
    """记录 Commit 与 tracked dirty 状态；Git 不可用时保持 UNKNOWN。"""

    root = Path(__file__).resolve().parents[2]
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False
        )
        status = subprocess.run(
            ["git", "status", "--porcelain=v1"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return UNKNOWN
    if revision.returncode != 0 or status.returncode != 0:
        return UNKNOWN
    suffix = "-dirty" if status.stdout.strip() else ""
    return f"{revision.stdout.strip()}{suffix}"


def _positive_repetition(value: str) -> int:
    """解析 1-based Repeat Index。"""

    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{EVAL_REPETITION_INDEX_ENV} 必须是正整数") from error
    if parsed < 1:
        raise ValueError(f"{EVAL_REPETITION_INDEX_ENV} 必须是正整数")
    return parsed


def selected_phase4_case_ids(
    environment: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    """按 Primary / Repeat 或显式环境选择本轮可运行 Case。"""

    values = os.environ if environment is None else environment
    explicit = values.get(PHASE4_CASE_IDS_ENV, "").strip()
    if explicit:
        selected = tuple(item.strip() for item in explicit.split(",") if item.strip())
        known = set(PRIMARY_CASE_IDS)
        unknown = sorted(set(selected) - known)
        if unknown:
            raise ValueError(f"{PHASE4_CASE_IDS_ENV} 只能选择 Core / AQ04: {', '.join(unknown)}")
        if len(selected) != len(set(selected)):
            raise ValueError(f"{PHASE4_CASE_IDS_ENV} 不能包含重复 Case")
        return selected
    repetition_index = _positive_repetition(values.get(EVAL_REPETITION_INDEX_ENV, "1"))
    if repetition_index == 1:
        return PRIMARY_CASE_IDS
    return CORE_REPEAT_CASE_IDS


def _target(case_id: str) -> Phase4CaseTarget:
    """获取冻结的 Dataset 0.2 Target。"""

    for item in PHASE4_CASE_TARGETS:
        if item.case_id == case_id:
            return item
    raise KeyError(case_id)


def create_run_metadata(
    *,
    environment: Mapping[str, str] | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Phase4RunMetadata:
    """只从 Process Environment 创建 0.2 Run Metadata，不加载 `.env`。"""

    values = os.environ if environment is None else environment
    repetition_index = _positive_repetition(values.get(EVAL_REPETITION_INDEX_ENV, "1"))
    started_at = clock().astimezone(UTC)
    run_id = values.get(EVAL_RUN_ID_ENV, "").strip() or started_at.strftime(
        "phase4-core-%Y%m%dT%H%M%SZ"
    )
    manifest = phase4_manifest_payload()
    return Phase4RunMetadata(
        dataset_id=str(manifest["dataset_id"]),
        dataset_version=PHASE4_DATASET_VERSION,
        base_dataset_version=str(manifest["base_dataset_version"]),
        base_manifest_sha256=PHASE4_BASE_MANIFEST_SHA256,
        phase4_manifest_sha256=_sha256(manifest),
        base_prompt_sha256=_sha256(SYSTEM_PROMPT),
        tool_contract_sha256=_sha256(_tool_contract_payload()),
        fixture_manifest_sha256=PHASE4_BASE_MANIFEST_SHA256,
        rubric_version=str(manifest["rubric_version"]),
        runtime="PYDANTIC_AI",
        conversation_prompt_mode="CITATION_MODE",
        provider=values.get("LLM_PROVIDER", DEFAULT_PROVIDER).strip().upper() or DEFAULT_PROVIDER,
        model=values.get("LLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        llm_base_url=_safe_base_url(values.get("LLM_BASE_URL", DEFAULT_BASE_URL)),
        native_request_timeout_seconds=DEFAULT_WALL_CLOCK_BUDGET_SECONDS,
        wall_clock_budget_seconds=DEFAULT_WALL_CLOCK_BUDGET_SECONDS,
        run_id=run_id,
        repetition_index=repetition_index,
        run_kind="PRIMARY" if repetition_index == 1 else "REPEAT",
        started_at=started_at.isoformat(),
        selected_case_ids=selected_phase4_case_ids(values),
        repository_revision=_repository_revision(),
    )


def _build_eval_runtime(environment: Mapping[str, str]) -> AgentRuntime | None:
    """用显式环境变量装配 PydanticAI；不让 Settings 读取 Repository `.env`。"""

    api_key = environment.get("LLM_API_KEY", "").strip()
    base_url = environment.get("LLM_BASE_URL", "").strip()
    model = environment.get("LLM_MODEL", "").strip()
    if not api_key or not base_url or not model:
        return None
    if environment.get("LLM_PROVIDER", DEFAULT_PROVIDER).strip().upper() != DEFAULT_PROVIDER:
        raise ValueError(f"Phase 4 固定 Eval Provider 必须为 {DEFAULT_PROVIDER}")
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=PostgresDsn("postgresql+psycopg://phase4-eval.invalid/phase4_eval"),
        llm_provider=environment.get("LLM_PROVIDER", DEFAULT_PROVIDER),
        llm_base_url=AnyHttpUrl(base_url),
        llm_api_key=SecretStr(api_key),
        llm_model=model,
        llm_request_timeout_seconds=float(
            environment.get("LLM_REQUEST_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
        ),
        native_llm_request_timeout_seconds=DEFAULT_WALL_CLOCK_BUDGET_SECONDS,
    )
    return create_pydantic_ai_runtime(settings)


def _portfolio_state(case: AskQualityCase) -> PortfolioState:
    """将固定 Case 的 Ledger Facts 映射为只读 Portfolio Snapshot。"""

    return PortfolioState(
        user_id=USER_ID,
        cash=CashBalance(USER_ID, Decimal("10000"), case.available_cash),
        positions=case.positions,
        transaction_count=len(case.transactions),
    )


def build_native_agent(
    case: AskQualityCase,
    runtime: AgentRuntime,
    *,
    wall_clock_budget_seconds: float = DEFAULT_WALL_CLOCK_BUDGET_SECONDS,
) -> NativeInvestmentAgent:
    """用固定 Fixture 创建 PydanticAI-backed NativeInvestmentAgent。"""

    state = _portfolio_state(case)
    market_data = FixedMarketData(case.market_results, case.historical_results)
    news = FixedNews(case.news_results)
    market_context = FixedMarketContext(case.market_context_result)
    return NativeInvestmentAgent(
        FixedPortfolioReader(state=state, transactions=case.transactions),
        market_data,
        runtime,
        news=news,
        market_context=market_context,
        clock=lambda: NOW + timedelta(minutes=30),
        wall_clock_budget_seconds=wall_clock_budget_seconds,
    )


def _source_payload(source: ContextSource) -> dict[str, object]:
    """序列化 Final Answer 的 Source Metadata。"""

    return {
        "source_id": str(source.source_id) if source.source_id is not None else None,
        "type": source.type.value,
        "status": source.status,
        "ticker": source.ticker,
        "provider": source.provider,
        "feed": source.feed,
        "url": source.url,
        "title": source.title,
        "publisher": source.publisher,
        "published_at": source.published_at.isoformat() if source.published_at else None,
        "provider_reference": source.provider_reference,
        "market_timestamp": (
            source.market_timestamp.isoformat() if source.market_timestamp else None
        ),
        "fetched_at": source.fetched_at.isoformat() if source.fetched_at else None,
    }


def _turn_record(
    case: AskQualityCase,
    question: str,
    turn_index: int,
    history: tuple[LLMMessage, ...],
    result: InvestmentAnswer | InvestmentRequestFailure,
    runtime_calls: Sequence[dict[str, object]],
    latency_ms: float,
) -> dict[str, object]:
    """生成单 Turn Record；保留 Failure 与 UNKNOWN Usage。"""

    usage_values = [cast(dict[str, object], item["usage"]) for item in runtime_calls]
    usage = _aggregate_usage(usage_values)
    tool_trace = [
        trace for item in runtime_calls for trace in cast(list[object], item["tool_trace"])
    ]
    common: dict[str, object] = {
        "turn_index": turn_index,
        "question": question,
        "history_message_count": len(history),
        "latency_ms": round(latency_ms, 2),
        "runtime_calls": list(runtime_calls),
        "repair_count": max(len(runtime_calls) - 1, 0),
        "tool_call_count": len(tool_trace),
        "tool_trace": tool_trace,
        "usage": usage,
    }
    if isinstance(result, InvestmentRequestFailure):
        return {
            **common,
            "execution_status": "REQUEST_FAILED",
            "failure_code": result.code.value,
            "answer": None,
            "response_status": None,
            "sources": [],
        }
    return {
        **common,
        "execution_status": "COMPLETED",
        "failure_code": None,
        "answer": result.answer,
        "response_status": result.status.value,
        "sources": [_source_payload(source) for source in result.sources],
        "warnings": list(result.warnings),
        "case_fixture": case.id,
    }


def _aggregate_usage(values: Sequence[dict[str, object]]) -> dict[str, int | str]:
    """只在本 Turn 每次模型调用都有完整 Usage 时求和。"""

    fields = ("input_tokens", "output_tokens", "total_tokens")
    if not values or any(
        any(not isinstance(item.get(field), int) for field in fields) for item in values
    ):
        return {field: UNKNOWN for field in fields}
    return {field: sum(cast(int, item[field]) for item in values) for field in fields}


def execute_native_case(
    case: AskQualityCase,
    runtime: RecordingAgentRuntime,
    *,
    wall_clock_budget_seconds: float = DEFAULT_WALL_CLOCK_BUDGET_SECONDS,
    progress: Callable[[dict[str, object]], None] | None = None,
) -> dict[str, object]:
    """执行一条 Native Case，并把每一轮的既有 User / Assistant Answer 注入历史。"""

    target = _target(case.id)
    agent = build_native_agent(case, runtime, wall_clock_budget_seconds=wall_clock_budget_seconds)
    history: list[LLMMessage] = []
    turns: list[dict[str, object]] = []
    for turn_index, question in enumerate(case.executable_questions, start=1):
        event = {"case_id": case.id, "turn_index": turn_index}
        if progress:
            progress({**event, "status": "STARTED"})
        before = len(runtime.calls)
        started_at = monotonic()
        try:
            result = agent.answer_with_history(USER_ID, question, tuple(history))
        except (KeyboardInterrupt, Exception) as exc:
            if progress:
                progress(
                    {
                        **event,
                        "status": "INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else "ERROR",
                        "elapsed_seconds": round(monotonic() - started_at, 2),
                    }
                )
            raise
        latency_ms = (monotonic() - started_at) * 1000
        calls = runtime.calls[before:]
        turn = _turn_record(case, question, turn_index, tuple(history), result, calls, latency_ms)
        turns.append(turn)
        if progress:
            progress({**event, "status": "TURN_FINISHED", "turn": turn})
        history.append(LLMMessage(LLMRole.USER, question))
        if isinstance(result, InvestmentAnswer):
            history.append(LLMMessage(LLMRole.ASSISTANT, result.answer))
    execution_status = (
        "REQUEST_FAILED"
        if any(turn["execution_status"] == "REQUEST_FAILED" for turn in turns)
        else "COMPLETED"
    )
    return {
        "case_id": case.id,
        "parent_case_id": case.parent_id,
        "gate": target.gate.value,
        "scenario_execution_scope": target.enabled_scope.value,
        "execution_status": execution_status,
        "evidence_status": "MEASURED",
        "not_run_reason": None,
        "turns": turns,
        "usage": _aggregate_usage([cast(dict[str, object], turn["usage"]) for turn in turns]),
        "total_latency_ms": round(sum(cast(float, turn["latency_ms"]) for turn in turns), 2),
        "tool_call_count": sum(cast(int, turn["tool_call_count"]) for turn in turns),
        "human_review": {"status": "PENDING"},
        "critical_failure_gate": {"status": "NOT_EVALUATED"},
    }


def not_measured_record(case_id: str, *, reason: str) -> dict[str, object]:
    """为未批准的 Research Gate 建立显式 NOT_MEASURED Record。"""

    target = _target(case_id)
    case = CASES_BY_ID[case_id]
    return {
        "case_id": case.id,
        "parent_case_id": case.parent_id,
        "gate": target.gate.value,
        "scenario_execution_scope": (
            target.deferred_scope.value
            if target.deferred_scope is not None
            else target.enabled_scope.value
        ),
        "execution_status": "NOT_RUN",
        "evidence_status": NOT_MEASURED,
        "not_run_reason": reason,
        "turns": [],
        "usage": {"input_tokens": UNKNOWN, "output_tokens": UNKNOWN, "total_tokens": UNKNOWN},
        "total_latency_ms": None,
        "tool_call_count": 0,
        "human_review": {"status": "NOT_STARTED"},
        "critical_failure_gate": {"status": "NOT_EVALUATED"},
    }


def not_run_record(case_id: str, *, reason: str) -> dict[str, object]:
    """为未选择或未启用在线运行的 Core Case 保留稳定记录。"""

    target = _target(case_id)
    record = not_measured_record(case_id, reason=reason)
    record["evidence_status"] = "NOT_RUN"
    record["scenario_execution_scope"] = target.enabled_scope.value
    return record


def _summary(
    metadata: Phase4RunMetadata,
    records: Sequence[dict[str, object]],
) -> dict[str, object]:
    """按 Core / Diagnostic / Research Gate 分栏汇总，不计算自动质量分。"""

    by_id = {str(record["case_id"]): record for record in records}
    core = [by_id[case_id] for case_id in PHASE4_CORE_CASE_IDS if case_id in by_id]
    diagnostic = [by_id[case_id] for case_id in PHASE4_EARNINGS_CASE_IDS if case_id in by_id]
    research = [by_id[case_id] for case_id in PHASE4_RESEARCH_CASE_IDS if case_id in by_id]
    core_completed = sum(item["execution_status"] == "COMPLETED" for item in core)
    core_failed = sum(item["execution_status"] == "REQUEST_FAILED" for item in core)
    core_attempted = core_completed + core_failed
    core_usage = _aggregate_usage(
        [
            cast(dict[str, object], item["usage"])
            for item in core
            if item["execution_status"] in {"COMPLETED", "REQUEST_FAILED"}
        ]
    )
    core_turns = [turn for item in core for turn in cast(list[dict[str, object]], item["turns"])]
    completed_turns = sum(turn["execution_status"] == "COMPLETED" for turn in core_turns)
    diagnostic_completed = sum(item["execution_status"] == "COMPLETED" for item in diagnostic)
    diagnostic_failed = sum(item["execution_status"] == "REQUEST_FAILED" for item in diagnostic)
    diagnostic_attempted = diagnostic_completed + diagnostic_failed
    latencies = [
        cast(float, turn["latency_ms"])
        for record in records
        for turn in cast(list[dict[str, object]], record["turns"])
        if isinstance(turn.get("latency_ms"), (int, float))
    ]
    return {
        "run_metadata": metadata.as_dict(),
        "dataset_status": {
            "dataset_version": PHASE4_DATASET_VERSION,
            "base_manifest_sha256": PHASE4_BASE_MANIFEST_SHA256,
            "phase4_manifest_sha256": metadata.phase4_manifest_sha256,
        },
        "core_full": {
            "target_case_count": len(PHASE4_CORE_CASE_IDS),
            "selected_case_count": sum(
                item["case_id"] in metadata.selected_case_ids for item in core
            ),
            "completed_case_count": core_completed,
            "request_failed_case_count": core_failed,
            "not_run_case_count": len(core) - core_attempted,
            "request_success_rate": core_completed / core_attempted if core_attempted else None,
            "completed_turn_count": completed_turns,
            "request_failed_turn_count": len(core_turns) - completed_turns,
            "turn_success_rate": completed_turns / len(core_turns) if core_turns else None,
            "critical_failure_gate": "NOT_EVALUATED",
        },
        "earnings_diagnostic": {
            "target_case_ids": list(PHASE4_EARNINGS_CASE_IDS),
            "completed_case_count": diagnostic_completed,
            "request_failed_case_count": diagnostic_failed,
            "not_run_case_count": len(diagnostic) - diagnostic_attempted,
            "evidence_status": "MEASURED" if diagnostic_attempted else "NOT_RUN",
        },
        "research_gate": {
            "case_ids": list(PHASE4_RESEARCH_CASE_IDS),
            "evidence_status": NOT_MEASURED,
            "records": [
                {"case_id": item["case_id"], "status": item["evidence_status"]} for item in research
            ],
        },
        "repeat": {
            "repetition_index": metadata.repetition_index,
            "target_case_ids": list(CORE_REPEAT_CASE_IDS),
            "completed_case_count": sum(
                item["execution_status"] == "COMPLETED"
                for item in core
                if item["case_id"] in CORE_REPEAT_CASE_IDS
            ),
        },
        "repair": {
            "total_count": sum(
                cast(int, turn["repair_count"])
                for record in records
                for turn in cast(list[dict[str, object]], record["turns"])
            ),
        },
        "latency": {
            "sample_count": len(latencies),
            "total_ms": round(sum(latencies), 2),
            "median_ms": statistics.median(latencies) if latencies else None,
            "max_ms": max(latencies) if latencies else None,
        },
        "usage": core_usage,
        "cost": "UNKNOWN",
        "human_review": "PENDING",
    }


def write_artifacts(
    artifact_dir: Path,
    metadata: Phase4RunMetadata,
    records: Sequence[dict[str, object]],
    summary: Mapping[str, object],
) -> None:
    """写入 manifest / cases / summary 三类不含 Secret 的 Artifact。"""

    artifact_dir.mkdir(parents=True, exist_ok=True)
    _require_unused_artifact_dir(artifact_dir, include_progress=False)
    manifest = {
        "run_metadata": metadata.as_dict(),
        "base_manifest": base_manifest_payload(),
        "phase4_manifest": phase4_manifest_payload(),
        "target_case_ids": [target.case_id for target in PHASE4_CASE_TARGETS],
    }
    (artifact_dir / "manifest.json").write_text(_stable_json(manifest) + "\n", encoding="utf-8")
    (artifact_dir / "cases.jsonl").write_text(
        "".join(_stable_json(record) + "\n" for record in records), encoding="utf-8"
    )
    (artifact_dir / "summary.json").write_text(_stable_json(summary) + "\n", encoding="utf-8")


def _require_unused_artifact_dir(artifact_dir: Path, *, include_progress: bool = True) -> None:
    """在线模型调用前拒绝已有结果，写入前再次防止意外覆盖。"""

    if any(
        (artifact_dir / name).exists()
        for name in (
            ("manifest.json", "cases.jsonl", "summary.json", "progress.jsonl")
            if include_progress
            else ("manifest.json", "cases.jsonl", "summary.json")
        )
    ):
        raise FileExistsError("Phase 4 Eval Artifact 已存在；请使用新的 Run 目录")


def run_phase4_evaluation(
    *,
    environment: Mapping[str, str] | None = None,
    runtime_factory: Callable[[Mapping[str, str]], AgentRuntime | None] | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, object]:
    """运行 4A Core Eval；未显式 Opt-in 时只生成 NOT_RUN / NOT_MEASURED 记录。"""

    values = os.environ if environment is None else environment
    artifact_raw = values.get(PHASE4_ARTIFACT_DIR_ENV, "").strip()
    if artifact_raw:
        _require_unused_artifact_dir(Path(artifact_raw))
    metadata = create_run_metadata(environment=values, clock=clock)

    def progress(event: dict[str, object]) -> None:
        # 日志只打印状态；完整固定 Fixture 证据仅写入本地 Artifact。
        turn = cast(dict[str, object], event.get("turn", {}))
        visible = {key: value for key, value in event.items() if key not in {"turn", "metadata"}}
        if turn:
            visible.update(execution_status=turn["execution_status"], latency_ms=turn["latency_ms"])
        print(_stable_json(visible), flush=True)
        if artifact_raw:
            directory = Path(artifact_raw)
            directory.mkdir(parents=True, exist_ok=True)
            with (directory / "progress.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(_stable_json(event) + "\n")

    progress({"status": "RUN_STARTED", "complete": False, "metadata": metadata.as_dict()})
    selected = set(metadata.selected_case_ids)
    records: list[dict[str, object]] = []
    for case_id in PHASE4_RESEARCH_CASE_IDS:
        records.append(not_measured_record(case_id, reason="RESEARCH_GATE_NOT_MEASURED"))
    online_enabled = values.get(RUN_PHASE4_EVAL_ENV, "").strip() == "1"
    runtime = None if not online_enabled else (runtime_factory or _build_eval_runtime)(values)
    for case_id in PRIMARY_CASE_IDS:
        if case_id not in selected:
            records.append(not_run_record(case_id, reason="CASE_NOT_SELECTED"))
            continue
        if not online_enabled:
            records.append(not_run_record(case_id, reason="ONLINE_EVAL_DISABLED"))
            continue
        if runtime is None:
            records.append(not_run_record(case_id, reason="MODEL_CONFIG_MISSING"))
            continue
        recording = (
            runtime
            if isinstance(runtime, RecordingAgentRuntime)
            else RecordingAgentRuntime(runtime)
        )
        case_record = execute_native_case(CASES_BY_ID[case_id], recording, progress=progress)
        records.append(case_record)
        runtime = recording
    records.sort(
        key=lambda item: (PRIMARY_CASE_IDS + PHASE4_RESEARCH_CASE_IDS).index(str(item["case_id"]))
    )
    summary = _summary(metadata, records)
    if artifact_raw:
        write_artifacts(Path(artifact_raw), metadata, records, summary)
    progress({"status": "RUN_FINISHED", "complete": True})
    return {"metadata": metadata.as_dict(), "records": records, "summary": summary}


__all__ = [
    "CORE_REPEAT_CASE_IDS",
    "DEFAULT_MODEL",
    "NOT_MEASURED",
    "PHASE4_ARTIFACT_DIR_ENV",
    "PHASE4_CASE_IDS_ENV",
    "PRIMARY_CASE_IDS",
    "RecordingAgentRuntime",
    "RUN_PHASE4_EVAL_ENV",
    "create_run_metadata",
    "execute_native_case",
    "not_measured_record",
    "not_run_record",
    "run_phase4_evaluation",
    "selected_phase4_case_ids",
    "write_artifacts",
]
