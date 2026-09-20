"""Phase 3 代表性证据与预算估算的可重复摘要。"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .contracts import ArtifactStatus
from .experiment_contract import EXPERIMENT_MODEL, REPRESENTATIVE_CASE_IDS, SAFETY_CEILING


@dataclass(frozen=True, slots=True)
class CaseEvidence:
    """代表性 Case 的能力证据，不冒充 Phase 4 Acceptance。"""

    case_id: str
    status: ArtifactStatus
    evidence: tuple[str, ...]
    limitation: str | None = None


CASE_EVIDENCE = (
    CaseEvidence(
        "AQ01",
        ArtifactStatus.NOT_MEASURED,
        ("research contract and source validation fixtures",),
        "no credentialed live research run",
    ),
    CaseEvidence(
        "AQ03",
        ArtifactStatus.PROTOTYPE_GAP,
        ("current quote tool loop", "unobserved source rejection"),
        "fixed-model live truth-correction response not measured",
    ),
    CaseEvidence(
        "AQ05",
        ArtifactStatus.PROTOTYPE_GAP,
        ("budget/cash controlled contrast", "execution quantity omitted"),
        "fixed-model final answer gate not measured",
    ),
    CaseEvidence(
        "AQ06",
        ArtifactStatus.PROTOTYPE_GAP,
        ("budget below one-share quote", "fractional/account permission UNKNOWN"),
        "fixed-model final answer gate not measured",
    ),
    CaseEvidence(
        "AQ08",
        ArtifactStatus.SUPPORTED,
        ("portfolio-only no-tool runtime regression",),
    ),
    CaseEvidence(
        "AQ12",
        ArtifactStatus.SUPPORTED,
        ("GOOG-MSFT-GOOG native history", "account-owned conversation injection"),
    ),
    CaseEvidence(
        "AQ17a",
        ArtifactStatus.SUPPORTED,
        ("NO_RESULTS distinct from provider failure",),
    ),
    CaseEvidence(
        "AQ17b",
        ArtifactStatus.SUPPORTED,
        ("PROVIDER_FAILURE remains explicit",),
    ),
    CaseEvidence(
        "AQ19",
        ArtifactStatus.PROTOTYPE_GAP,
        ("untrusted tool payload", "mutation allowlist", "controlled fetch security"),
        "fixed-model malicious-page run not measured",
    ),
)


def decision_evidence(*, revision: str) -> dict[str, object]:
    """形成不含 Secret、私有 Context 或网页正文的决策证据。"""

    if not revision.strip():
        raise ValueError("Revision 不能为空")
    return {
        "schema_version": "phase3-decision-evidence-0.1",
        "revision": revision,
        "experiment_model": EXPERIMENT_MODEL,
        "runtime": {
            "current": {
                "offline_status": ArtifactStatus.SUPPORTED.value,
                "live_status": ArtifactStatus.NOT_MEASURED.value,
                "deterministic_script_request_range": [1, 3],
                "notes": ["generic provider-neutral tool contract", "application-owned loop"],
            },
            "pydantic-ai": {
                "offline_status": ArtifactStatus.SUPPORTED.value,
                "live_status": ArtifactStatus.NOT_MEASURED.value,
                "deterministic_script_request_range": [1, 3],
                "notes": [
                    "native history and usage limits",
                    "AlibabaProvider constructible",
                    "three-tool bridge remains a prototype gap",
                ],
            },
        },
        "research": {
            "alibaba-native": {
                "offline_status": ArtifactStatus.SUPPORTED.value,
                "live_status": ArtifactStatus.NOT_MEASURED.value,
                "reason": "model credential and region endpoint unavailable",
            },
            "application-owned": {
                "offline_status": ArtifactStatus.SUPPORTED.value,
                "live_status": ArtifactStatus.NOT_MEASURED.value,
                "search_provider": "brave-search",
                "fetch": "controlled independent fetch prototype",
                "reason": "search provider credential unavailable",
            },
        },
        "persistence": {
            "application_boundary": ArtifactStatus.SUPPORTED.value,
            "postgres_live": ArtifactStatus.SUPPORTED.value,
            "evidence": "isolated PostgreSQL 17 temporary-schema integration",
        },
        "representative_cases": [
            {
                "case_id": item.case_id,
                "status": item.status.value,
                "evidence": list(item.evidence),
                "limitation": item.limitation,
            }
            for item in CASE_EVIDENCE
        ],
        "budget_estimate": {
            "initial_phase4_safety_ceiling": asdict(SAFETY_CEILING),
            "production_slo": ArtifactStatus.NOT_MEASURED.value,
            "cost": ArtifactStatus.NOT_MEASURED.value,
            "live_latency": ArtifactStatus.NOT_MEASURED.value,
        },
        "representative_combination_status": ArtifactStatus.NOT_MEASURED.value,
        "phase4_entry": "NO_GO_PENDING_LIVE_EVIDENCE",
    }


def write_decision_evidence(output_directory: Path, *, revision: str) -> Path:
    """只写入调用方显式提供的绝对 Artifact 目录。"""

    if not output_directory.is_absolute():
        raise ValueError("Artifact 目录必须是绝对路径")
    output_directory.mkdir(parents=True, exist_ok=True)
    path = output_directory / "decision-evidence.json"
    path.write_text(
        json.dumps(
            decision_evidence(revision=revision),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def validate_case_coverage() -> None:
    """代表性 Case 必须完整且不重复。"""

    observed = tuple(item.case_id for item in CASE_EVIDENCE)
    if observed != REPRESENTATIVE_CASE_IDS:
        raise ValueError("Representative Case Evidence 与冻结合同不一致")
