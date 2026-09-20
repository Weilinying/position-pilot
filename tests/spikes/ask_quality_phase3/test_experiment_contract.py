"""Phase 3 冻结实验合同测试。"""

from .contracts import ArtifactStatus
from .experiment_contract import (
    CRITICAL_GATES,
    EXPERIMENT_MODEL,
    REPRESENTATIVE_CASE_IDS,
    RESEARCH_CANDIDATES,
    RUNTIME_CANDIDATES,
    SAFETY_CEILING,
    experiment_manifest,
)


def test_phase3_contract_freezes_minimal_candidates_and_fixed_model() -> None:
    """Phase 3 不扩展 Runtime、Research 或模型横评范围。"""

    assert EXPERIMENT_MODEL == "qwen3.7-max"
    assert EXPERIMENT_MODEL != "deepseek-v4-pro-0813"
    assert RUNTIME_CANDIDATES == ("current", "pydantic-ai")
    assert RESEARCH_CANDIDATES == ("alibaba-native", "application-owned")
    assert set(REPRESENTATIVE_CASE_IDS) == {
        "AQ01",
        "AQ03",
        "AQ05",
        "AQ06",
        "AQ08",
        "AQ12",
        "AQ17a",
        "AQ17b",
        "AQ19",
    }


def test_manifest_distinguishes_safety_ceiling_from_production_slo() -> None:
    """实验预算只负责终止保护，不冒充生产 SLO。"""

    manifest = experiment_manifest(
        run_id="test-run",
        revision="test-revision",
        provider="FAKE",
        endpoint_type="FAKE",
        region="FAKE",
    )

    assert manifest["safety_ceiling_is_production_slo"] is False
    assert manifest["safety_ceiling"] == {
        "model_requests": 4,
        "tool_calls": 4,
        "search_calls": 2,
        "fetch_calls": 2,
        "wall_clock_seconds": 30,
    }
    assert SAFETY_CEILING.wall_clock_seconds == 30
    assert "UNVERIFIED_CRITICAL_FACT_TREATED_AS_TRUE" in CRITICAL_GATES
    for field in ("prompt_hash", "tool_contract_hash", "fixture_hash"):
        value = manifest[field]
        assert isinstance(value, str)
        assert len(value) == 64


def test_artifact_status_keeps_prototype_gap_distinct_from_architecture_limit() -> None:
    """Prototype Bug 不得自动升级为架构不支持。"""

    assert ArtifactStatus.PROTOTYPE_GAP.value == "PROTOTYPE_GAP"
    assert ArtifactStatus.ARCHITECTURE_LIMIT.value == "ARCHITECTURE_LIMIT"
    assert {status.value for status in ArtifactStatus} == {
        "SUPPORTED",
        "PROTOTYPE_GAP",
        "ARCHITECTURE_LIMIT",
        "NOT_MEASURED",
    }
