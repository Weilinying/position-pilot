"""Phase 3 代表性证据和预算摘要测试。"""

import json
from pathlib import Path

from .contracts import ArtifactStatus
from .decision_evidence import (
    CASE_EVIDENCE,
    decision_evidence,
    validate_case_coverage,
    write_decision_evidence,
)


def test_representative_case_evidence_matches_frozen_contract() -> None:
    """T8 覆盖全部冻结代表性 Case，但不冒充 Phase 4 Acceptance。"""

    validate_case_coverage()

    statuses = {item.case_id: item.status for item in CASE_EVIDENCE}
    assert statuses["AQ01"] is ArtifactStatus.NOT_MEASURED
    assert statuses["AQ03"] is ArtifactStatus.PROTOTYPE_GAP
    assert statuses["AQ05"] is ArtifactStatus.SUPPORTED
    assert statuses["AQ06"] is ArtifactStatus.SUPPORTED
    assert statuses["AQ19"] is ArtifactStatus.SUPPORTED


def test_decision_evidence_separates_offline_live_and_production_budget() -> None:
    """缺少 Live Credential 时不得把离线能力或 Safety Ceiling 写成生产结论。"""

    evidence = decision_evidence(revision="fixture-revision")

    assert evidence["phase4_entry"] == "NO_GO_PENDING_LIVE_EVIDENCE"
    runtime = evidence["runtime"]
    assert isinstance(runtime, dict)
    assert runtime["current"]["live_status"] == "NOT_MEASURED"
    assert runtime["pydantic-ai"]["live_status"] == "NOT_MEASURED"
    budget = evidence["budget_estimate"]
    assert isinstance(budget, dict)
    assert budget["production_slo"] == "NOT_MEASURED"
    assert budget["cost"] == "NOT_MEASURED"


def test_decision_evidence_writer_is_reproducible(tmp_path: Path) -> None:
    """Artifact 不包含 Credential、私有 Context 或原始网页正文。"""

    path = write_decision_evidence(tmp_path.resolve(), revision="fixture-revision")
    payload = json.loads(path.read_text(encoding="utf-8"))
    serialized = json.dumps(payload, ensure_ascii=False).lower()

    assert payload == decision_evidence(revision="fixture-revision")
    assert "api_key" not in serialized
    assert "authorization" not in serialized
    assert "raw_content" not in serialized
    assert "private_context" not in serialized
