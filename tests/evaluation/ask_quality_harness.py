"""Ask Quality Discovery 的运行记录、执行器与本地 Artifact Reporter。"""

import hashlib
import json
import os
import statistics
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from time import monotonic
from typing import Any, Protocol, cast
from urllib.parse import urlsplit, urlunsplit

from ask_quality_cases import (
    ALL_RUBRIC_DIMENSIONS,
    CASES,
    CASES_BY_ID,
    DATASET_ID,
    DATASET_VERSION,
    RUBRIC_VERSION,
    AskQualityCase,
    ScenarioExecutionScope,
)
from behavioral_harness import (
    NOW,
    USER_ID,
    CountingLLM,
    FixedMarketContext,
    FixedMarketData,
    FixedNews,
    FixedPortfolioReader,
    behavioral_completion_metrics,
    collect_failure_execution_trace,
    structured_response_diagnostics,
)

from position_pilot.application.investment_agent import (
    CONTEXT_TOOLS,
    SYSTEM_PROMPT,
    InvestmentAgent,
    InvestmentAnswer,
    InvestmentRequestFailure,
)
from position_pilot.application.llm import LLMProvider, LLMResponseFormat
from position_pilot.domain.portfolio import CashBalance, PortfolioState

EVALUATION_PROVIDER = "ALIYUN_MODEL_STUDIO"
EVALUATION_PROVIDER_ENV = "LLM_PROVIDER"
DEFAULT_EVALUATION_MODEL = "deepseek-v4-pro-0813"
DEFAULT_LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_LLM_TIMEOUT_SECONDS = "30"
PRODUCTION_BEHAVIOR_REVISION = "ace40d5bf5bd75a3da3dba5e615021dfde8bfcd0"
REAL_EVAL_ENV = "RUN_REAL_ASK_QUALITY_EVAL"
SELECTED_CASES_ENV = "ASK_QUALITY_CASE_IDS"
ARTIFACT_DIR_ENV = "ASK_QUALITY_ARTIFACT_DIR"
UNKNOWN = "UNKNOWN"


class _FixtureResult(Protocol):
    """统一固定 Market / News Result 的只读序列化接口。"""

    @property
    def status(self) -> StrEnum: ...

    @property
    def message(self) -> str | None: ...

    @property
    def data(self) -> object | None: ...


class ExecutionStatus(StrEnum):
    """一次执行变体或 Turn 的实际请求状态。"""

    COMPLETED = "COMPLETED"
    REQUEST_FAILED = "REQUEST_FAILED"
    NOT_RUN = "NOT_RUN"


class CriticalFailureGate(StrEnum):
    """关键事实与权限错误的人工 Gate 状态。"""

    PASS = "PASS"
    FAIL = "FAIL"
    NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True, slots=True)
class AskQualityRunMetadata:
    """一次 Discovery pytest Session 的可重复性元数据。"""

    dataset_id: str
    dataset_version: str
    rubric_version: str
    provider: str
    model: str
    production_revision: str
    harness_revision: str
    llm_base_url: str
    request_timeout_seconds: str
    run_id: str
    repetition_index: int
    routing_response_format: str
    started_at: str
    prompt_sha256: str
    tool_contract_sha256: str
    fixture_manifest_sha256: str

    def as_dict(self) -> dict[str, object]:
        """返回可安全写入本地 Artifact 的稳定字段。"""

        return {
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "rubric_version": self.rubric_version,
            "provider": self.provider,
            "model": self.model,
            "production_revision": self.production_revision,
            "harness_revision": self.harness_revision,
            "llm_base_url": self.llm_base_url,
            "request_timeout_seconds": self.request_timeout_seconds,
            "run_id": self.run_id,
            "repetition_index": self.repetition_index,
            "routing_response_format": self.routing_response_format,
            "started_at": self.started_at,
            "prompt_sha256": self.prompt_sha256,
            "tool_contract_sha256": self.tool_contract_sha256,
            "fixture_manifest_sha256": self.fixture_manifest_sha256,
        }


def _sha256(value: str) -> str:
    """返回 UTF-8 文本的稳定 SHA-256。"""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_default(value: object) -> str:
    """只为可复现的 Evaluation 类型提供稳定文本序列化。"""

    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    return str(value)


def _json_dumps(value: object, *, indent: int | None = None) -> str:
    """生成排序稳定且支持 Evaluation 值类型的 JSON。"""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        indent=indent,
        default=_json_default,
    )


def _read_git_revision(repository_root: Path) -> str:
    """同时记录 Commit 与完整工作区 dirty 状态。"""

    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain=v1"],
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return UNKNOWN
    if revision.returncode != 0 or status.returncode != 0:
        return UNKNOWN
    suffix = "-dirty" if status.stdout.strip() else ""
    return f"{revision.stdout.strip()}{suffix}"


def _safe_base_url(value: str) -> str:
    """记录去除用户信息、Query 与 Fragment 的 Provider Endpoint。"""

    parsed = urlsplit(value)
    if not parsed.scheme or parsed.hostname is None:
        return UNKNOWN
    hostname = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    netloc = f"{hostname}:{parsed.port}" if parsed.port is not None else hostname
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def _tool_contract_payload() -> list[dict[str, object]]:
    """返回用于版本摘要的 Provider-neutral Tool Contract。"""

    return [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }
        for tool in CONTEXT_TOOLS
    ]


def _fixture_data(value: object) -> object:
    """把固定 Provider 数据展开，确保内容变化会改变 Fixture 摘要。"""

    if value is None:
        return None
    if not is_dataclass(value):
        raise TypeError("Evaluation Fixture data 必须是 dataclass")
    return asdict(cast(Any, value))


def _provider_result_payload(result: _FixtureResult) -> dict[str, object]:
    """序列化 Market / News Result 的状态、消息与完整固定数据。"""

    return {
        "status": result.status.value,
        "message": result.message,
        "data": _fixture_data(result.data),
    }


def case_manifest(case: AskQualityCase) -> dict[str, object]:
    """把不可变 Case 定义转换成不含 Secret 的 Manifest。"""

    return {
        "case_id": case.id,
        "parent_case_id": case.parent_id,
        "category": case.category,
        "origin": case.origin.value,
        "related_failure": case.related_failure,
        "target_messages": case.target_messages,
        "executable_questions": case.executable_questions,
        "unavailable_target_steps": [
            {
                "message": message,
                "reason": "NOT_EXECUTABLE_BY_CURRENT_ASK_CONTRACT",
            }
            for message in case.target_messages
            if message not in case.executable_questions
        ],
        "scenario_execution_scope": case.scope.value,
        "required_capabilities": [item.value for item in case.required_capabilities],
        "capability_gaps": [
            {"capability": item.value, "status": "NOT_SUPPORTED"} for item in case.capability_gaps
        ],
        "state_fixtures": [
            {
                "state_type": fixture.state_type,
                "value": fixture.value,
                "runtime_availability": fixture.runtime_availability,
            }
            for fixture in case.state_fixtures
        ],
        "domain_fixture": {
            "available_cash": str(case.available_cash),
            "positions": [
                {
                    "ticker": position.ticker,
                    "position_type": position.position_type.value,
                    "shares": str(position.shares),
                    "average_cost": str(position.average_cost),
                }
                for position in case.positions
            ],
            "transactions": [_fixture_data(transaction) for transaction in case.transactions],
        },
        "provider_fixtures": {
            "quote": {
                ticker: _provider_result_payload(result)
                for ticker, result in case.market_results.items()
            },
            "price_history": {
                ticker: _provider_result_payload(result)
                for ticker, result in case.historical_results.items()
            },
            "news": {
                ticker: _provider_result_payload(result)
                for ticker, result in case.news_results.items()
            },
            "market_context": _provider_result_payload(case.market_context_result),
            "clock": (NOW + timedelta(minutes=30)).isoformat(),
        },
        "expected_behavior": case.expected_behavior,
        "forbidden_behavior": case.forbidden_behavior,
        "rubric_dimensions": [item.value for item in case.rubric_dimensions],
        "controlled_contrast": case.controlled_contrast,
        "repeat_candidate": case.repeat_candidate,
        "holdout": case.holdout,
    }


def manifest_payload() -> dict[str, object]:
    """返回整个 Discovery Dataset 的冻结 Manifest。"""

    parent_ids = {case.parent_id for case in CASES}
    return {
        "dataset_id": DATASET_ID,
        "dataset_version": DATASET_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "parent_case_count": len(parent_ids),
        "execution_variant_count": len(CASES),
        "fixture_label": "FIXTURE",
        "cases": [case_manifest(case) for case in CASES],
    }


def selected_cases(environment: Mapping[str, str] | None = None) -> tuple[AskQualityCase, ...]:
    """读取显式 Case 子集；默认执行全部变体。"""

    values = os.environ if environment is None else environment
    raw_value = values.get(SELECTED_CASES_ENV, "").strip()
    if not raw_value:
        return CASES
    selected_ids = tuple(part.strip() for part in raw_value.split(",") if part.strip())
    unknown_ids = sorted(set(selected_ids) - CASES_BY_ID.keys())
    if unknown_ids:
        raise ValueError(f"{SELECTED_CASES_ENV} 包含未知 Case: {', '.join(unknown_ids)}")
    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError(f"{SELECTED_CASES_ENV} 不能包含重复 Case")
    return tuple(CASES_BY_ID[case_id] for case_id in selected_ids)


def create_run_metadata(
    *,
    environment: Mapping[str, str] | None = None,
    repository_root: Path | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> AskQualityRunMetadata:
    """从显式进程环境创建运行元数据，不读取 Repository `.env`。"""

    values = os.environ if environment is None else environment
    started_at = clock().astimezone(UTC)
    raw_repetition = values.get("EVAL_REPETITION_INDEX", "1")
    try:
        repetition_index = int(raw_repetition)
    except ValueError as error:
        raise ValueError("EVAL_REPETITION_INDEX 必须是正整数") from error
    if repetition_index < 1:
        raise ValueError("EVAL_REPETITION_INDEX 必须是正整数")
    run_id = values.get("EVAL_RUN_ID", "").strip() or started_at.strftime(
        "ask-quality-%Y%m%dT%H%M%SZ"
    )
    routing_format = values.get("EVAL_ROUTING_RESPONSE_FORMAT", "TEXT").strip().upper()
    try:
        routing_response_format = LLMResponseFormat(routing_format)
    except ValueError as error:
        raise ValueError("EVAL_ROUTING_RESPONSE_FORMAT 只支持 TEXT 或 JSON_OBJECT") from error
    root = repository_root or Path(__file__).resolve().parents[2]
    manifest = manifest_payload()
    return AskQualityRunMetadata(
        dataset_id=DATASET_ID,
        dataset_version=DATASET_VERSION,
        rubric_version=RUBRIC_VERSION,
        provider=values.get(EVALUATION_PROVIDER_ENV, EVALUATION_PROVIDER).strip().upper()
        or UNKNOWN,
        model=values.get("LLM_MODEL", DEFAULT_EVALUATION_MODEL).strip() or UNKNOWN,
        production_revision=PRODUCTION_BEHAVIOR_REVISION,
        harness_revision=_read_git_revision(root),
        llm_base_url=_safe_base_url(values.get("LLM_BASE_URL", DEFAULT_LLM_BASE_URL)),
        request_timeout_seconds=values.get(
            "LLM_REQUEST_TIMEOUT_SECONDS",
            DEFAULT_LLM_TIMEOUT_SECONDS,
        ),
        run_id=run_id,
        repetition_index=repetition_index,
        routing_response_format=routing_response_format.value,
        started_at=started_at.isoformat(),
        prompt_sha256=_sha256(SYSTEM_PROMPT),
        tool_contract_sha256=_sha256(_json_dumps(_tool_contract_payload())),
        fixture_manifest_sha256=_sha256(_json_dumps(manifest)),
    )


def _raw_completions(llm: CountingLLM) -> list[dict[str, object]]:
    """仅保留 Provider-neutral Completion，不保存 HTTP Payload。"""

    completions: list[dict[str, object]] = []
    for index, (result, response_format) in enumerate(
        zip(llm.results, llm.response_formats, strict=True), start=1
    ):
        entry: dict[str, object] = {
            "completion_index": index,
            "status": result.status.value,
            "response_format": response_format.value,
            "error_message": result.error_message,
        }
        if result.metadata is not None:
            entry["metadata"] = {
                "provider": result.metadata.provider,
                "model": result.metadata.model,
                "latency_ms": result.metadata.latency_ms,
                "response_id": result.metadata.response_id,
                "usage": (
                    {
                        "input_tokens": result.metadata.usage.input_tokens,
                        "output_tokens": result.metadata.usage.output_tokens,
                        "total_tokens": result.metadata.usage.total_tokens,
                    }
                    if result.metadata.usage is not None
                    else None
                ),
            }
        if result.completion is not None:
            message = result.completion.message
            entry["content"] = message.content
            entry["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "name": tool_call.name,
                    "arguments": dict(tool_call.arguments),
                }
                for tool_call in message.tool_calls
            ]
        completions.append(entry)
    return completions


def _usage_payload(llm: CountingLLM) -> dict[str, int | str]:
    """仅在每次真实 Completion 都提供 Usage 时汇总，避免部分数据冒充完整成本。"""

    usages = [
        result.metadata.usage
        for result in llm.results
        if result.metadata is not None and result.metadata.usage is not None
    ]
    if len(usages) != len(llm.results):
        return {
            "input_tokens": UNKNOWN,
            "output_tokens": UNKNOWN,
            "total_tokens": UNKNOWN,
        }
    return {
        "input_tokens": sum(usage.input_tokens for usage in usages),
        "output_tokens": sum(usage.output_tokens for usage in usages),
        "total_tokens": sum(usage.total_tokens for usage in usages),
    }


def _aggregate_turn_usage(turns: list[dict[str, object]]) -> dict[str, int | str]:
    """汇总 Case 内全部 Turn；任一 Turn 缺失 Usage 时保持 UNKNOWN。"""

    values: list[dict[str, object]] = []
    for turn in turns:
        usage = turn.get("usage")
        if not isinstance(usage, dict) or any(
            not isinstance(usage.get(field), int)
            for field in ("input_tokens", "output_tokens", "total_tokens")
        ):
            return {
                "input_tokens": UNKNOWN,
                "output_tokens": UNKNOWN,
                "total_tokens": UNKNOWN,
            }
        values.append(usage)
    return {
        "input_tokens": sum(cast(int, usage["input_tokens"]) for usage in values),
        "output_tokens": sum(cast(int, usage["output_tokens"]) for usage in values),
        "total_tokens": sum(cast(int, usage["total_tokens"]) for usage in values),
    }


def _source_records(result: InvestmentAnswer) -> list[dict[str, object]]:
    """序列化成功来源与失败 Tool Attempt。"""

    return [
        {
            "type": source.type.value,
            "status": source.status,
            "ticker": source.ticker,
            "provider": source.provider,
            "feed": source.feed,
            "market_timestamp": source.market_timestamp,
            "fetched_at": source.fetched_at,
        }
        for source in result.sources
    ]


def _execute_turn(
    case: AskQualityCase,
    question: str,
    turn_index: int,
    llm_provider: LLMProvider,
    routing_response_format: LLMResponseFormat,
) -> dict[str, object]:
    """通过当前单问题路径执行一轮，绝不拼接前文。"""

    state = PortfolioState(
        user_id=USER_ID,
        cash=CashBalance(USER_ID, Decimal("10000"), case.available_cash),
        positions=case.positions,
        transaction_count=len(case.transactions),
    )
    market_data = FixedMarketData(case.market_results, case.historical_results)
    news = FixedNews(case.news_results)
    market_context = FixedMarketContext(case.market_context_result)
    llm = CountingLLM(
        llm_provider,
        routing_response_format_override=routing_response_format,
    )
    agent = InvestmentAgent(
        FixedPortfolioReader(state=state, transactions=case.transactions),
        market_data,
        llm,
        news=news,
        market_context=market_context,
        clock=lambda: NOW + timedelta(minutes=30),
    )
    started_at = monotonic()
    result = agent.answer(USER_ID, question)
    latency_ms = round((monotonic() - started_at) * 1000, 2)
    diagnostics = structured_response_diagnostics(llm, market_data, news, market_context)
    metrics = behavioral_completion_metrics(llm, market_data, news, market_context)
    tool_trace = collect_failure_execution_trace(llm, market_data, news, market_context)
    tool_attempts = tool_trace["tool_attempts"]
    assert isinstance(tool_attempts, list)
    common: dict[str, object] = {
        "turn_index": turn_index,
        "question": question,
        "latency_ms": latency_ms,
        "completion_count": llm.completion_count,
        "tool_call_count": len(tool_attempts),
        "raw_completions": _raw_completions(llm),
        "structured_response_diagnostics": diagnostics,
        "completion_metrics": metrics,
        "usage": _usage_payload(llm),
    }
    if isinstance(result, InvestmentRequestFailure):
        return {
            **common,
            "execution_status": ExecutionStatus.REQUEST_FAILED.value,
            "request_failure": {"code": result.code.value, "message": result.message},
            "answer": None,
            "response_status": None,
            "sources": [],
            "tool_trace": tool_trace,
        }
    return {
        **common,
        "execution_status": ExecutionStatus.COMPLETED.value,
        "request_failure": None,
        "answer": result.answer,
        "response_status": result.status.value,
        "sources": _source_records(result),
        "tool_trace": tool_trace,
    }


def execute_case(
    case: AskQualityCase,
    llm_provider: LLMProvider,
    routing_response_format: LLMResponseFormat,
) -> dict[str, object]:
    """逐轮独立提交 Case，并组合成一个 Session Record。"""

    turns = [
        _execute_turn(case, question, index, llm_provider, routing_response_format)
        for index, question in enumerate(case.executable_questions, start=1)
    ]
    status = (
        ExecutionStatus.REQUEST_FAILED
        if any(turn["execution_status"] == ExecutionStatus.REQUEST_FAILED.value for turn in turns)
        else ExecutionStatus.COMPLETED
    )
    total_latency_ms = sum(cast(float, turn["latency_ms"]) for turn in turns)
    tool_call_count = sum(cast(int, turn["tool_call_count"]) for turn in turns)
    return {
        "case_id": case.id,
        "parent_case_id": case.parent_id,
        "related_failure": case.related_failure,
        "scenario_execution_scope": case.scope.value,
        "execution_status": status.value,
        "total_latency_ms": round(total_latency_ms, 2),
        "tool_call_count": tool_call_count,
        "not_run_reason": None,
        "capability_gaps": [
            {"capability": item.value, "status": "NOT_SUPPORTED"} for item in case.capability_gaps
        ],
        "turns": turns,
        "critical_failure_gate": {
            "status": CriticalFailureGate.NOT_EVALUATED.value,
            "categories": [],
            "evidence": [],
            "reviewer": None,
        },
        "human_review": {
            "status": "PENDING",
            "scores": {},
            "dimension_reviews": {
                dimension.value: {
                    "status": "PENDING",
                    "value": None,
                    "evidence": [],
                    "reviewer": None,
                }
                for dimension in case.rubric_dimensions
            },
            "reviewer": None,
            "reviewed_at": None,
        },
        "usage": _aggregate_turn_usage(turns),
        "cost": {
            "amount": UNKNOWN,
            "currency": UNKNOWN,
            "price_source": UNKNOWN,
            "as_of": UNKNOWN,
            "includes_search": False,
        },
    }


def not_run_record(case: AskQualityCase, reason: str) -> dict[str, object]:
    """保留未发出请求的 Case，不把它换算为 Gate PASS。"""

    return {
        "case_id": case.id,
        "parent_case_id": case.parent_id,
        "related_failure": case.related_failure,
        "scenario_execution_scope": case.scope.value,
        "execution_status": ExecutionStatus.NOT_RUN.value,
        "total_latency_ms": None,
        "tool_call_count": 0,
        "not_run_reason": reason,
        "capability_gaps": [
            {"capability": item.value, "status": "NOT_SUPPORTED"} for item in case.capability_gaps
        ],
        "turns": [],
        "critical_failure_gate": {
            "status": CriticalFailureGate.NOT_EVALUATED.value,
            "categories": [],
            "evidence": [],
            "reviewer": None,
        },
        "human_review": {
            "status": "NOT_STARTED",
            "scores": {},
            "dimension_reviews": {
                dimension.value: {
                    "status": "NOT_STARTED",
                    "value": None,
                    "evidence": [],
                    "reviewer": None,
                }
                for dimension in case.rubric_dimensions
            },
            "reviewer": None,
            "reviewed_at": None,
        },
        "usage": {"input_tokens": UNKNOWN, "output_tokens": UNKNOWN, "total_tokens": UNKNOWN},
        "cost": {
            "amount": UNKNOWN,
            "currency": UNKNOWN,
            "price_source": UNKNOWN,
            "as_of": UNKNOWN,
            "includes_search": False,
        },
    }


def _capability_coverage() -> dict[str, object]:
    """按父场景计算固定能力覆盖，不受运行结果影响。"""

    variants_by_parent: dict[str, list[AskQualityCase]] = {}
    for case in CASES:
        variants_by_parent.setdefault(case.parent_id, []).append(case)
    full_parent_ids = sorted(
        parent_id
        for parent_id, variants in variants_by_parent.items()
        if all(variant.scope is ScenarioExecutionScope.FULL for variant in variants)
    )
    return {
        "full_parent_case_count": len(full_parent_ids),
        "target_parent_case_count": len(variants_by_parent),
        "rate": len(full_parent_ids) / len(variants_by_parent),
        "full_parent_case_ids": full_parent_ids,
    }


def _record_mapping(value: object) -> dict[str, object]:
    """把动态 Run Record 字段收窄为字符串键 Mapping。"""

    if not isinstance(value, dict):
        return {}
    return cast(dict[str, object], value)


def _record_turns(record: dict[str, object]) -> list[dict[str, object]]:
    """返回结构有效的 Turn 列表，供汇总逻辑读取。"""

    value = record.get("turns")
    if not isinstance(value, list):
        return []
    return [cast(dict[str, object], turn) for turn in value if isinstance(turn, dict)]


def _latency_values(records: list[dict[str, object]]) -> list[float]:
    """提取已实际执行 Turn 的毫秒延迟。"""

    latencies: list[float] = []
    for record in records:
        for turn in _record_turns(record):
            value = turn.get("latency_ms")
            if isinstance(value, int | float):
                latencies.append(float(value))
    return latencies


def _tool_call_total(records: list[dict[str, object]]) -> int:
    """统计本轮已实际执行的 Tool Attempt 数。"""

    total = 0
    for record in records:
        for turn in _record_turns(record):
            value = turn.get("tool_call_count")
            if isinstance(value, int):
                total += value
    return total


def _critical_failure_category_counts(
    gate_failures: list[dict[str, object]],
) -> dict[str, int]:
    """按人工 Gate 中记录的类别汇总 Critical Failure。"""

    counts: dict[str, int] = {}
    for record in gate_failures:
        gate = _record_mapping(record.get("critical_failure_gate"))
        categories = gate.get("categories")
        if not isinstance(categories, list):
            continue
        for category in categories:
            if isinstance(category, str):
                counts[category] = counts.get(category, 0) + 1
    return dict(sorted(counts.items()))


def _review_status(records: list[dict[str, object]]) -> str:
    """区分没有可评记录、待评分与已完成评分。"""

    if not records:
        return "NOT_STARTED"
    statuses = {_record_mapping(record.get("human_review")).get("status") for record in records}
    return "COMPLETED" if statuses == {"COMPLETED"} else "PENDING"


def _dimension_distributions(
    records: list[dict[str, object]],
) -> dict[str, dict[str, int]]:
    """只统计人工明确给出的 0 / 1 / 2 分，不把缺失状态换算为零分。"""

    distributions = {
        dimension.value: {"0": 0, "1": 0, "2": 0} for dimension in ALL_RUBRIC_DIMENSIONS
    }
    for record in records:
        human_review = _record_mapping(record.get("human_review"))
        dimension_reviews = _record_mapping(human_review.get("dimension_reviews"))
        for dimension in ALL_RUBRIC_DIMENSIONS:
            review = _record_mapping(dimension_reviews.get(dimension.value))
            value = review.get("value")
            if isinstance(value, int) and value in (0, 1, 2):
                distributions[dimension.value][str(value)] += 1
    return distributions


def build_summary(
    metadata: AskQualityRunMetadata,
    records: list[dict[str, object]],
) -> dict[str, object]:
    """生成不混合 Coverage、Quality、Reliability 与 Gate 的首页指标。"""

    completed_count = sum(
        record["execution_status"] == ExecutionStatus.COMPLETED.value for record in records
    )
    failed_count = sum(
        record["execution_status"] == ExecutionStatus.REQUEST_FAILED.value for record in records
    )
    not_run_count = sum(
        record["execution_status"] == ExecutionStatus.NOT_RUN.value for record in records
    )
    attempted_count = completed_count + failed_count
    gate_failures = [
        record
        for record in records
        if _record_mapping(record.get("critical_failure_gate")).get("status")
        == CriticalFailureGate.FAIL.value
    ]
    gate_not_evaluated = sum(
        _record_mapping(record.get("critical_failure_gate")).get("status")
        == CriticalFailureGate.NOT_EVALUATED.value
        for record in records
    )
    full_completed = [
        record
        for record in records
        if record["scenario_execution_scope"] == ScenarioExecutionScope.FULL.value
        and record["execution_status"] == ExecutionStatus.COMPLETED.value
    ]
    diagnostic_records = [
        record
        for record in records
        if record["scenario_execution_scope"] == ScenarioExecutionScope.DIAGNOSTIC.value
    ]
    diagnostic_completed = [
        record
        for record in diagnostic_records
        if record["execution_status"] == ExecutionStatus.COMPLETED.value
    ]
    latencies = _latency_values(records)
    return {
        "run_metadata": metadata.as_dict(),
        "capability_coverage": _capability_coverage(),
        "full_answer_quality": {
            "completed_variant_count": len(full_completed),
            "rubric_version": RUBRIC_VERSION,
            "review_status": _review_status(full_completed),
            "dimension_distributions": _dimension_distributions(full_completed),
        },
        "diagnostic_observations": {
            "target_variant_count": len(diagnostic_records),
            "completed_variant_count": len(diagnostic_completed),
            "review_status": _review_status(diagnostic_completed),
            "dimension_distributions": _dimension_distributions(diagnostic_completed),
        },
        "request_reliability": {
            "completed": completed_count,
            "request_failed": failed_count,
            "not_run": not_run_count,
            "success_rate": completed_count / attempted_count if attempted_count else None,
        },
        "critical_failures": {
            "fail_count": len(gate_failures),
            "affected_case_ids": [record["case_id"] for record in gate_failures],
            "category_counts": _critical_failure_category_counts(gate_failures),
            "not_evaluated_count": gate_not_evaluated,
        },
        "latency": {
            "sample_count": len(latencies),
            "total_ms": round(sum(latencies), 2),
            "median_ms": statistics.median(latencies) if latencies else None,
            "max_ms": max(latencies) if latencies else None,
        },
        "tool_calls": {"total": _tool_call_total(records)},
        "usage": UNKNOWN,
        "cost": UNKNOWN,
    }


@dataclass(slots=True)
class AskQualityReporter:
    """聚合 Case 记录，并可选写入被 Git 忽略的本地 Artifact。"""

    metadata: AskQualityRunMetadata
    target_cases: tuple[AskQualityCase, ...]
    artifact_dir: Path | None = None
    records_by_id: dict[str, dict[str, object]] = field(default_factory=dict)

    def _attach_run_metadata(self, record: dict[str, object]) -> dict[str, object]:
        """让每条可独立读取的 Case Record 携带 Run 与重复序号。"""

        return {**record, "run_metadata": self.metadata.as_dict()}

    def record(self, record: dict[str, object]) -> None:
        """记录一个 Case；重复 Case ID 表示 Harness 错误。"""

        case_id = record.get("case_id")
        if not isinstance(case_id, str) or case_id not in {case.id for case in self.target_cases}:
            raise ValueError("Case Record 不属于本轮目标集")
        if case_id in self.records_by_id:
            raise ValueError(f"Case {case_id} 已记录")
        stored_record = self._attach_run_metadata(record)
        self.records_by_id[case_id] = stored_record
        print(_json_dumps({"ask_quality_case": stored_record}, indent=2))

    def record_not_run(self, case: AskQualityCase, reason: str) -> None:
        """显式记录预检阶段未发出请求的 Case。"""

        self.record(not_run_record(case, reason))

    def finalize(
        self, *, incomplete_reason: str = "HARNESS_DID_NOT_EXECUTE_CASE"
    ) -> dict[str, object]:
        """补齐意外未运行项，输出 Summary，并写入可选 Artifact。"""

        for case in self.target_cases:
            if case.id not in self.records_by_id:
                self.records_by_id[case.id] = self._attach_run_metadata(
                    not_run_record(case, incomplete_reason)
                )
        records = [self.records_by_id[case.id] for case in self.target_cases]
        summary = build_summary(self.metadata, records)
        payload = {"ask_quality_evaluation_summary": summary}
        print(_json_dumps(payload, indent=2))
        if self.artifact_dir is not None:
            self._write_artifacts(records, summary)
        return summary

    def _write_artifacts(
        self,
        records: list[dict[str, object]],
        summary: dict[str, object],
    ) -> None:
        """只在调用方明确目录下保存不含 HTTP Secret 的本地记录。"""

        assert self.artifact_dir is not None
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_manifest = {
            "run_metadata": self.metadata.as_dict(),
            "target_case_ids": [case.id for case in self.target_cases],
            "dataset_manifest": manifest_payload(),
        }
        (self.artifact_dir / "manifest.json").write_text(
            _json_dumps(artifact_manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        (self.artifact_dir / "cases.jsonl").write_text(
            "".join(_json_dumps(record) + "\n" for record in records),
            encoding="utf-8",
        )
        (self.artifact_dir / "summary.json").write_text(
            _json_dumps(summary, indent=2) + "\n",
            encoding="utf-8",
        )


def artifact_dir_from_environment(
    environment: Mapping[str, str] | None = None,
) -> Path | None:
    """读取可选本地 Artifact 目录，不创建默认持久化位置。"""

    values = os.environ if environment is None else environment
    raw_value = values.get(ARTIFACT_DIR_ENV, "").strip()
    return Path(raw_value) if raw_value else None


__all__ = [
    "ARTIFACT_DIR_ENV",
    "DEFAULT_EVALUATION_MODEL",
    "DEFAULT_LLM_BASE_URL",
    "DEFAULT_LLM_TIMEOUT_SECONDS",
    "PRODUCTION_BEHAVIOR_REVISION",
    "REAL_EVAL_ENV",
    "SELECTED_CASES_ENV",
    "AskQualityReporter",
    "AskQualityRunMetadata",
    "CriticalFailureGate",
    "ExecutionStatus",
    "artifact_dir_from_environment",
    "build_summary",
    "case_manifest",
    "create_run_metadata",
    "execute_case",
    "manifest_payload",
    "not_run_record",
    "selected_cases",
]
