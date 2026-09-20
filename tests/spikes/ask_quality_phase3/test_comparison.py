"""两个真实 Runtime / Research 候选的统一对照测试。"""

from dataclasses import dataclass

from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from position_pilot.application.llm import (
    LLMMessage,
    LLMResponseFormat,
    LLMResult,
    LLMRole,
    LLMToolDefinition,
)

from .comparison import compare_research, compare_runtimes
from .contracts import (
    ArtifactStatus,
    ResearchRequest,
    ResearchStatus,
    RuntimeBudget,
    RuntimeExecutionStatus,
    RuntimeInput,
    SourceRecord,
)
from .current_runtime import CurrentRuntimeCandidate
from .pydantic_runtime import PydanticRuntimeCandidate
from .research_candidates import (
    AlibabaNativeResearchCandidate,
    ApplicationOwnedResearchCandidate,
    FetchResult,
    NativeResearchObservation,
    SearchHit,
    SearchResponse,
)


@dataclass(slots=True)
class FinalLLM:
    """Current Runtime 的离线 Final Model。"""

    def complete(
        self,
        messages: tuple[LLMMessage, ...],
        *,
        tools: tuple[LLMToolDefinition, ...] = (),
        response_format: LLMResponseFormat = LLMResponseFormat.TEXT,
    ) -> LLMResult:
        del messages, tools, response_format
        return LLMResult.success(LLMMessage(LLMRole.ASSISTANT, "条件分析完成。"))


@dataclass(slots=True)
class NativeGateway:
    """返回实际候选可消费的 Native 观察。"""

    source: SourceRecord

    def run(self, *, model: str, query: str) -> NativeResearchObservation:
        assert model == "qwen3.7-max"
        assert query == "GOOG Alphabet latest filing last-7-days"
        return NativeResearchObservation(
            ResearchStatus.COMPLETED,
            (self.source,),
            search_count=1,
            fetch_count=1,
        )


@dataclass(slots=True)
class SearchProvider:
    """Application-owned 候选的单一 Search Provider。"""

    source: SourceRecord
    name: str = "one-search-provider"

    def search(self, query: str, *, limit: int) -> SearchResponse:
        assert query == "GOOG Alphabet latest filing last-7-days"
        assert limit == 3
        assert self.source.url is not None
        return SearchResponse(
            ResearchStatus.COMPLETED,
            (SearchHit(self.source.source_id, self.source.url, self.source.title),),
        )


@dataclass(slots=True)
class Fetcher:
    """受控 Fetch 的离线观察。"""

    def fetch(self, url: str) -> FetchResult:
        return FetchResult("OK", url, "公开文件正文")


def _runtime_input() -> RuntimeInput:
    return RuntimeInput(
        conversation=(LLMMessage(LLMRole.USER, "继续分析 GOOG"),),
        current_turn_context={"ticker": "GOOG", "budget": "500"},
        portfolio_context={"cash": "4875.77", "positions": ["GOOG"]},
        confirmed_strategy=(),
        tools=(),
        budget=RuntimeBudget(4, 4, 2, 2, 30),
    )


def test_real_runtime_candidates_share_input_but_keep_internal_differences() -> None:
    """统一 Runner 对真实候选比较，不强制内部 Message 或 Usage 一致。"""

    def pydantic_model(
        messages: list[ModelMessage],
        info: AgentInfo,
    ) -> ModelResponse:
        del messages, info
        return ModelResponse(parts=(TextPart("条件分析完成。"),))

    comparison = compare_runtimes(
        (
            CurrentRuntimeCandidate(FinalLLM(), {}),
            PydanticRuntimeCandidate(FunctionModel(pydantic_model), {}),
        ),
        fixture="no-tool",
        runtime_input=_runtime_input(),
        expected_status=RuntimeExecutionStatus.COMPLETED,
    )

    assert all(item.status is ArtifactStatus.SUPPORTED for item in comparison.artifacts)
    assert (
        comparison.artifacts[0].result["input_hash"] == comparison.artifacts[1].result["input_hash"]
    )
    assert "internal_message_representation" in comparison.differences


def test_real_research_candidates_share_public_request_and_registry() -> None:
    """Native 与 Application-owned 候选使用同一公开请求并绑定外部 Source Registry。"""

    native_source = SourceRecord(
        "native-1",
        "ALIBABA_NATIVE",
        "https://abc.xyz/filing",
    )
    application_source = SourceRecord(
        "application-1",
        "one-search-provider",
        "https://abc.xyz/filing",
    )
    request = ResearchRequest("GOOG", "latest filing", "last-7-days", "Alphabet")
    comparison = compare_research(
        (
            AlibabaNativeResearchCandidate(NativeGateway(native_source), model="qwen3.7-max"),
            ApplicationOwnedResearchCandidate(SearchProvider(application_source), Fetcher()),
        ),
        fixture="latest-filing",
        request=request,
        expected_status=ResearchStatus.COMPLETED,
        observed_source_ids=(frozenset({"native-1"}), frozenset({"application-1"})),
    )

    assert all(item.status is ArtifactStatus.SUPPORTED for item in comparison.artifacts)
    assert (
        comparison.artifacts[0].result["request_hash"]
        == comparison.artifacts[1].result["request_hash"]
    )
    assert "fetch_observability" in comparison.differences
