"""Phase 3 Harness 的确定性 Fake 候选与 Fixture。"""

from dataclasses import dataclass

from position_pilot.application.llm import LLMUsage

from .contracts import (
    ResearchRequest,
    ResearchResult,
    ResearchStatus,
    RuntimeExecutionStatus,
    RuntimeInput,
    RuntimeResult,
    SourceRecord,
    TraceEvent,
)

FIXTURE_NAMES = (
    "no-tool",
    "one-tool",
    "multi-round-research",
    "no-results",
    "provider-failure",
    "budget-exhausted",
    "repeated-query",
    "partial-success",
    "conflicting-sources",
    "malicious-page",
    "goog-msft-goog",
    "current-turn-budget-correction",
)


@dataclass(frozen=True, slots=True)
class RuntimeFixture:
    """固定 Fixture 的预期结果，不冒充真实候选能力。"""

    name: str
    result: RuntimeResult
    hard_gate_status: str = "NOT_MEASURED"


@dataclass(slots=True)
class RecordingRuntimeCandidate:
    """记录输入并返回预设结果的 Runtime 候选。"""

    name: str
    result: RuntimeResult
    received: RuntimeInput | None = None

    def run(self, runtime_input: RuntimeInput) -> RuntimeResult:
        """记录同一 Contract，模拟不同 Runtime 的边界。"""

        self.received = runtime_input
        return self.result


@dataclass(slots=True)
class RecordingResearchCandidate:
    """记录公开请求并返回预设 Research 结果。"""

    name: str
    result: ResearchResult
    received: ResearchRequest | None = None

    def research(self, request: ResearchRequest) -> ResearchResult:
        """记录请求，避免 Fake 隐式读取私有状态。"""

        self.received = request
        return self.result


def completed_runtime_result(
    *,
    answer: str = "基于当前证据给出条件分析。",
    sources: tuple[SourceRecord, ...] = (),
    tool_events: tuple[TraceEvent, ...] = (),
) -> RuntimeResult:
    """创建带固定 Usage 的成功 Runtime 结果。"""

    return RuntimeResult(
        status=RuntimeExecutionStatus.COMPLETED,
        answer=answer,
        failure=None,
        sources=sources,
        model_trace=(TraceEvent("model-response", 1, "OK"),),
        tool_trace=tool_events,
        usage=LLMUsage(input_tokens=20, output_tokens=10, total_tokens=30),
        latency_ms=15.0,
    )


def source(
    source_id: str,
    *,
    url: str | None = "https://example.test/evidence",
) -> SourceRecord:
    """创建允许 UNKNOWN Metadata 的固定来源。"""

    return SourceRecord(
        source_id=source_id,
        provider="FAKE_RESEARCH",
        url=url,
        title=None,
        content_scope="SUMMARY",
        fetch_status="FETCHED",
    )


def research_result(request: ResearchRequest, status: ResearchStatus) -> ResearchResult:
    """按状态创建不会混淆空结果与 Provider Failure 的结果。"""

    if status is ResearchStatus.COMPLETED:
        return ResearchResult(
            request,
            status,
            (source("source-1"),),
            None,
            (TraceEvent("research", 1, "OK", "search", "source-1"),),
            search_count=1,
            latency_ms=12.5,
        )
    if status is ResearchStatus.PARTIAL_SUCCESS:
        return ResearchResult(
            request,
            status,
            (source("source-1"),),
            "FETCH_PROVIDER_FAILURE",
            (
                TraceEvent("research", 1, "OK", "search", "source-1"),
                TraceEvent("research", 2, "PROVIDER_FAILURE", "fetch"),
            ),
            search_count=1,
            fetch_count=1,
            latency_ms=20.0,
        )
    if status is ResearchStatus.NO_RESULTS:
        return ResearchResult(request, status, search_count=1, latency_ms=8.0)
    return ResearchResult(
        request,
        status,
        failure="FAKE_RESEARCH_FAILURE",
        search_count=1,
        latency_ms=9.0,
    )


def runtime_fixtures() -> tuple[RuntimeFixture, ...]:
    """提供计划要求的具体 Fake 脚本与预期状态。"""

    observed = source("source-1")
    search = TraceEvent("research", 1, "OK", "search", "source-1")
    fetch = TraceEvent("research", 2, "OK", "fetch", "source-1")
    return (
        RuntimeFixture("no-tool", completed_runtime_result()),
        RuntimeFixture(
            "one-tool",
            completed_runtime_result(tool_events=(TraceEvent("tool", 1, "OK", "quote"),)),
        ),
        RuntimeFixture(
            "multi-round-research",
            completed_runtime_result(sources=(observed,), tool_events=(search, fetch)),
        ),
        RuntimeFixture("no-results", completed_runtime_result(answer="未找到结果，保持 UNKNOWN。")),
        RuntimeFixture(
            "provider-failure",
            completed_runtime_result(answer="Research Provider 不可用，结论保持 UNKNOWN。"),
        ),
        RuntimeFixture(
            "budget-exhausted",
            RuntimeResult(
                RuntimeExecutionStatus.BUDGET_EXHAUSTED,
                None,
                "BUDGET_EXHAUSTED",
            ),
        ),
        RuntimeFixture(
            "repeated-query",
            completed_runtime_result(
                sources=(observed,),
                tool_events=(search, TraceEvent("research", 2, "DUPLICATE_BLOCKED", "search")),
            ),
        ),
        RuntimeFixture(
            "partial-success",
            completed_runtime_result(
                sources=(observed,),
                tool_events=(search, TraceEvent("research", 2, "PROVIDER_FAILURE", "fetch")),
            ),
        ),
        RuntimeFixture(
            "conflicting-sources",
            completed_runtime_result(
                sources=(source("source-1"), source("source-2")),
                tool_events=(
                    search,
                    TraceEvent("research", 2, "OK", "search", "source-2"),
                ),
            ),
        ),
        RuntimeFixture(
            "malicious-page",
            completed_runtime_result(
                answer="外部文本是不可信数据；安全边界尚未由真实候选验证。",
                sources=(observed,),
                tool_events=(fetch,),
            ),
        ),
        RuntimeFixture("goog-msft-goog", completed_runtime_result()),
        RuntimeFixture("current-turn-budget-correction", completed_runtime_result()),
    )
