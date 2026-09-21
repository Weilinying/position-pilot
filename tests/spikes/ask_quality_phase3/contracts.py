"""Phase 3 Harness 使用的最小 Provider-neutral Contract。"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from urllib.parse import parse_qsl, urlsplit

from position_pilot.application.llm import LLMMessage, LLMToolDefinition, LLMUsage


class ArtifactStatus(StrEnum):
    """区分能力、Prototype 缺口、架构限制与未测量。"""

    SUPPORTED = "SUPPORTED"
    PROTOTYPE_GAP = "PROTOTYPE_GAP"
    ARCHITECTURE_LIMIT = "ARCHITECTURE_LIMIT"
    NOT_MEASURED = "NOT_MEASURED"


class RuntimeExecutionStatus(StrEnum):
    """Runtime 候选的最小执行状态。"""

    COMPLETED = "COMPLETED"
    CANDIDATE_FAILURE = "CANDIDATE_FAILURE"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


class ResearchStatus(StrEnum):
    """Research 正常结果与失败必须可区分。"""

    COMPLETED = "COMPLETED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    NO_RESULTS = "NO_RESULTS"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    BLOCKED = "BLOCKED"
    TIMEOUT = "TIMEOUT"


@dataclass(frozen=True, slots=True)
class RuntimeBudget:
    """一次候选运行的显式 Safety Ceiling。"""

    model_requests: int
    tool_calls: int
    search_calls: int
    fetch_calls: int
    wall_clock_seconds: int

    def __post_init__(self) -> None:
        values = (
            self.model_requests,
            self.tool_calls,
            self.search_calls,
            self.fetch_calls,
            self.wall_clock_seconds,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in values
        ):
            raise ValueError("Runtime Budget 必须全部为正整数")


@dataclass(frozen=True, slots=True)
class RuntimeInput:
    """两个 Runtime 候选共同消费的受信输入。"""

    conversation: tuple[LLMMessage, ...]
    current_turn_context: Mapping[str, object]
    portfolio_context: Mapping[str, object]
    confirmed_strategy: tuple[Mapping[str, object], ...]
    tools: tuple[LLMToolDefinition, ...]
    budget: RuntimeBudget
    retrieved_memories: tuple[Mapping[str, object], ...] = ()


@dataclass(frozen=True, slots=True)
class SourceRecord:
    """实验性来源记录；未知 Metadata 保持 None。"""

    source_id: str
    provider: str
    url: str | None
    title: str | None = None
    provider_reference: str | None = None
    publisher: str | None = None
    published_at: str | None = None
    event_time: str | None = None
    content_scope: str | None = None
    fetch_status: str | None = None

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.provider.strip():
            raise ValueError("Source identity 与 Provider 不能为空")
        if self.url is not None:
            parsed = urlsplit(self.url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("Source URL 必须使用 HTTP(S) 且包含 Host")
            if parsed.username is not None or parsed.password is not None:
                raise ValueError("Source URL 不得包含 Credential")
            sensitive_query_keys = {"api_key", "token", "signature", "credential"}
            if any(key.lower() in sensitive_query_keys for key, _ in parse_qsl(parsed.query)):
                raise ValueError("Source URL 不得包含敏感 Query 参数")


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """保留候选实际动作，不强制框架内部表示一致。"""

    kind: str
    sequence: int
    status: str
    tool_name: str | None = None
    source_id: str | None = None

    def __post_init__(self) -> None:
        if not self.kind.strip() or not self.status.strip() or self.sequence <= 0:
            raise ValueError("Trace Event 必须包含 kind、status 与正整数 sequence")


@dataclass(frozen=True, slots=True)
class RuntimeResult:
    """候选运行结果；失败不能伪装成 Answer。"""

    status: RuntimeExecutionStatus
    answer: str | None
    failure: str | None
    sources: tuple[SourceRecord, ...] = ()
    model_trace: tuple[TraceEvent, ...] = ()
    tool_trace: tuple[TraceEvent, ...] = ()
    usage: LLMUsage | None = None
    latency_ms: float | None = None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, RuntimeExecutionStatus):
            raise ValueError("Runtime Result status 无效")
        if self.latency_ms is not None and (
            isinstance(self.latency_ms, bool)
            or not isinstance(self.latency_ms, (int, float))
            or not isfinite(self.latency_ms)
            or self.latency_ms < 0
        ):
            raise ValueError("Runtime Latency 必须是非负有限数或 None")
        if self.status is RuntimeExecutionStatus.COMPLETED:
            if (
                not isinstance(self.answer, str)
                or not self.answer.strip()
                or self.failure is not None
            ):
                raise ValueError("完成结果必须只包含非空 Answer")
        elif (
            self.answer is not None or not isinstance(self.failure, str) or not self.failure.strip()
        ):
            raise ValueError("失败结果必须只包含安全 Failure")


@dataclass(frozen=True, slots=True)
class ResearchRequest:
    """Research 只接收公开主体、事件与时间窗。"""

    ticker: str
    event: str
    time_window: str
    company: str | None = None

    def __post_init__(self) -> None:
        if not self.ticker.strip() or not self.event.strip() or not self.time_window.strip():
            raise ValueError("Research 公开主体、事件与时间窗不能为空")
        if self.company is not None and not self.company.strip():
            raise ValueError("Company 必须是非空字符串或 None")

    @property
    def query(self) -> str:
        """只从公开字段构造查询，不接收 Portfolio 或 Conversation。"""

        terms = (self.ticker, self.company, self.event, self.time_window)
        return " ".join(term for term in terms if term is not None)


@dataclass(frozen=True, slots=True)
class ResearchResult:
    """统一 Native 与 Application-owned Research 的观察结果。"""

    request: ResearchRequest
    status: ResearchStatus
    sources: tuple[SourceRecord, ...] = ()
    failure: str | None = None
    research_trace: tuple[TraceEvent, ...] = ()
    search_count: int = 0
    fetch_count: int = 0
    latency_ms: float | None = None
    usage: LLMUsage | None = None
    cost_amount: str | None = None
    cost_currency: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, ResearchStatus):
            raise ValueError("Research Result status 无效")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in (self.search_count, self.fetch_count)
        ):
            raise ValueError("Search / Fetch Count 必须是非负整数")
        if self.latency_ms is not None and (
            isinstance(self.latency_ms, bool)
            or not isinstance(self.latency_ms, (int, float))
            or not isfinite(self.latency_ms)
            or self.latency_ms < 0
        ):
            raise ValueError("Research Latency 必须是非负数或 None")
        if (self.cost_amount is None) is not (self.cost_currency is None):
            raise ValueError("Cost amount 与 currency 必须同时提供或同时 UNKNOWN")
        if self.status is ResearchStatus.COMPLETED:
            if not self.sources or self.failure is not None:
                raise ValueError("完成的 Research 必须包含来源且没有 Failure")
        elif self.status is ResearchStatus.PARTIAL_SUCCESS:
            if not self.sources or not isinstance(self.failure, str) or not self.failure.strip():
                raise ValueError("部分成功必须同时包含有效来源与 Failure")
        elif self.status is ResearchStatus.NO_RESULTS:
            if self.sources or self.failure is not None:
                raise ValueError("NO_RESULTS 不能包含来源或 Failure")
        elif not isinstance(self.failure, str) or not self.failure.strip():
            raise ValueError("Research Failure 必须包含安全错误消息")


@dataclass(frozen=True, slots=True)
class ComparisonArtifact:
    """一次候选观察的可重复 Artifact。"""

    category: str
    candidate: str
    fixture: str
    status: ArtifactStatus
    result: Mapping[str, object]
    differences: tuple[str, ...] = ()
