"""Phase 4 Ask Quality Dataset 0.2 Manifest Contract。"""

import json

from ask_quality_cases import CASES, DATASET_VERSION, RUBRIC_VERSION, ScenarioExecutionScope
from ask_quality_phase4_manifest import (
    PHASE4_BASE_DATASET_VERSION,
    PHASE4_BASE_MANIFEST_SHA256,
    PHASE4_CASE_TARGETS,
    PHASE4_CHECKPOINT_SEQUENCE,
    PHASE4_CONTINUOUS_ASK_SCRIPT,
    PHASE4_CORE_CASE_IDS,
    PHASE4_DATASET_VERSION,
    PHASE4_EARNINGS_CASE_IDS,
    PHASE4_RESEARCH_CASE_IDS,
    PHASE4_STRATEGY_CASE_IDS,
    PHASE4_TARGETS_BY_ID,
    Phase4EvidenceStatus,
    Phase4Gate,
    current_base_manifest_sha256,
    phase4_manifest_payload,
)


def test_phase4_manifest_preserves_dataset_01_as_history() -> None:
    """0.2 只能派生目标 Scope，不能改写 0.1 的版本或 Rubric。"""

    assert DATASET_VERSION == "0.1"
    assert PHASE4_BASE_DATASET_VERSION == "0.1"
    assert PHASE4_DATASET_VERSION == "0.2"
    assert RUBRIC_VERSION == "0.1"
    assert current_base_manifest_sha256() == PHASE4_BASE_MANIFEST_SHA256
    assert set(PHASE4_TARGETS_BY_ID) == {case.id for case in CASES}
    assert len(PHASE4_CASE_TARGETS) == len(CASES) == 21


def test_phase4_case_groups_are_frozen_before_execution() -> None:
    """4A Core、Research、Earnings 与 4B Strategy 必须分别归因。"""

    assert PHASE4_CORE_CASE_IDS == (
        "AQ03",
        "AQ05",
        "AQ06",
        "AQ07",
        "AQ08",
        "AQ09",
        "AQ10",
        "AQ11",
        "AQ12",
        "AQ17a",
        "AQ17b",
        "AQ18",
        "AQ20",
    )
    assert PHASE4_RESEARCH_CASE_IDS == ("AQ01", "AQ02", "AQ19")
    assert PHASE4_EARNINGS_CASE_IDS == ("AQ04",)
    assert PHASE4_STRATEGY_CASE_IDS == ("AQ13", "AQ14", "AQ15", "AQ16")


def test_research_gate_can_defer_without_changing_core_scope() -> None:
    """T4R 延后只保留 Research Case 为 DIAGNOSTIC，不阻塞 Core。"""

    for case_id in PHASE4_RESEARCH_CASE_IDS:
        target = PHASE4_TARGETS_BY_ID[case_id]
        assert target.gate is Phase4Gate.OPEN_RESEARCH_4A
        assert target.enabled_scope is ScenarioExecutionScope.FULL
        assert target.deferred_scope is ScenarioExecutionScope.DIAGNOSTIC
        assert target.deferred_evidence_status is Phase4EvidenceStatus.NOT_MEASURED
    for case_id in PHASE4_CORE_CASE_IDS:
        target = PHASE4_TARGETS_BY_ID[case_id]
        assert target.gate is Phase4Gate.CORE_4A
        assert target.enabled_scope is ScenarioExecutionScope.FULL
        assert target.deferred_scope is None
        assert target.deferred_evidence_status is None


def test_earnings_stays_diagnostic_and_strategy_waits_for_4b() -> None:
    """AQ04 不伪装 Earnings 能力，AQ13～AQ16 只属于 4B。"""

    earnings = PHASE4_TARGETS_BY_ID["AQ04"]
    assert earnings.gate is Phase4Gate.EARNINGS_REGRESSION
    assert earnings.enabled_scope is ScenarioExecutionScope.DIAGNOSTIC
    for case_id in PHASE4_STRATEGY_CASE_IDS:
        target = PHASE4_TARGETS_BY_ID[case_id]
        assert target.gate is Phase4Gate.STRATEGY_4B
        assert target.enabled_scope is ScenarioExecutionScope.FULL


def test_phase4_manifest_payload_is_reproducible_json() -> None:
    """Manifest 必须能作为 Artifact 独立保存，不依赖 Provider 或 Model。"""

    payload = phase4_manifest_payload()

    assert payload["dataset_version"] == "0.2"
    assert payload["base_dataset_version"] == "0.1"
    assert payload["base_manifest_sha256"] == PHASE4_BASE_MANIFEST_SHA256
    assert payload["rubric_version"] == "0.1"
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload


def test_phase4_sequential_script_and_independent_gate_are_frozen() -> None:
    """连续 Ask 顺序与独立 Research Gate 不得在执行后重写。"""

    assert PHASE4_CHECKPOINT_SEQUENCE == ("4A_CORE", "4A_HUMAN_REVIEW", "4B_STRATEGY")
    assert [step["order"] for step in PHASE4_CONTINUOUS_ASK_SCRIPT] == [1, 2, 3, 4, 5, 6]
    assert PHASE4_CONTINUOUS_ASK_SCRIPT[0]["checkpoint"] == "4A_RESEARCH_IF_ENABLED"
    assert PHASE4_CONTINUOUS_ASK_SCRIPT[3]["checkpoint"] == "4B_STRATEGY"
    payload = phase4_manifest_payload()
    assert payload["independent_gates"] == ["OPEN_RESEARCH_4A"]
