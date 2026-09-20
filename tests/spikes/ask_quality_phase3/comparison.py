"""两组 Phase 3 候选的最小统一 Comparison Runner。"""

from dataclasses import dataclass

from .contracts import (
    ComparisonArtifact,
    ResearchRequest,
    ResearchStatus,
    RuntimeExecutionStatus,
    RuntimeInput,
)
from .harness import (
    ResearchCandidate,
    RuntimeCandidate,
    run_research_fixture,
    run_runtime_fixture,
)


@dataclass(frozen=True, slots=True)
class CandidateComparison:
    """保留候选 Artifact 与允许存在的内部差异。"""

    artifacts: tuple[ComparisonArtifact, ComparisonArtifact]
    differences: tuple[str, ...]


def compare_runtimes(
    candidates: tuple[RuntimeCandidate, RuntimeCandidate],
    *,
    fixture: str,
    runtime_input: RuntimeInput,
    expected_status: RuntimeExecutionStatus,
    observed_source_ids: tuple[frozenset[str], frozenset[str]] = (
        frozenset(),
        frozenset(),
    ),
) -> CandidateComparison:
    """用同一 Application Input 运行两个真实 Runtime 候选。"""

    artifacts = tuple(
        run_runtime_fixture(
            candidate,
            fixture,
            runtime_input,
            expected_status,
            capability_evidence=True,
            observed_source_ids=source_ids,
        )
        for candidate, source_ids in zip(candidates, observed_source_ids, strict=True)
    )
    left_hash = artifacts[0].result.get("input_hash")
    right_hash = artifacts[1].result.get("input_hash")
    if left_hash != right_hash:
        raise ValueError("Runtime 候选没有消费等价 Application Input")
    differences = (
        "internal_message_representation",
        "model_trace_shape",
        "usage_accounting",
    )
    return CandidateComparison((artifacts[0], artifacts[1]), differences)


def compare_research(
    candidates: tuple[ResearchCandidate, ResearchCandidate],
    *,
    fixture: str,
    request: ResearchRequest,
    expected_status: ResearchStatus,
    observed_source_ids: tuple[frozenset[str], frozenset[str]],
) -> CandidateComparison:
    """用同一 Public-only Request 运行两个真实 Research 候选。"""

    artifacts = tuple(
        run_research_fixture(
            candidate,
            fixture,
            request,
            expected_status,
            capability_evidence=True,
            observed_source_ids=source_ids,
        )
        for candidate, source_ids in zip(candidates, observed_source_ids, strict=True)
    )
    left_hash = artifacts[0].result.get("request_hash")
    right_hash = artifacts[1].result.get("request_hash")
    if left_hash != right_hash:
        raise ValueError("Research 候选没有消费等价 Public Request")
    differences = (
        "provider_managed_search_vs_application_search",
        "source_metadata_shape",
        "fetch_observability",
    )
    return CandidateComparison((artifacts[0], artifacts[1]), differences)
