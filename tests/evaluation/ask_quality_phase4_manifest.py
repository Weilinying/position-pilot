"""Phase 4 Ask Quality Dataset 0.2 的目标能力 Manifest。"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from ask_quality_cases import (
    CASES,
    DATASET_ID,
    DATASET_VERSION,
    RUBRIC_VERSION,
    ScenarioExecutionScope,
)
from ask_quality_harness import manifest_payload as base_manifest_payload

PHASE4_DATASET_VERSION = "0.2"
PHASE4_BASE_DATASET_VERSION = DATASET_VERSION
PHASE4_BASE_MANIFEST_SHA256 = "f907a653bd0dfb2c731b6084151fa68b8edb8c28f1f947da89c0aed62d11e149"
PHASE4_CHECKPOINT_SEQUENCE = ("4A_CORE", "4A_HUMAN_REVIEW", "4B_STRATEGY")
PHASE4_INDEPENDENT_GATES = ("OPEN_RESEARCH_4A",)

PHASE4_CONTINUOUS_ASK_SCRIPT = (
    {
        "order": 1,
        "checkpoint": "4A_RESEARCH_IF_ENABLED",
        "message": "GOOG 今天为什么跌？",
    },
    {
        "order": 2,
        "checkpoint": "4A_CORE",
        "message": "那我该怎么办？",
    },
    {
        "order": 3,
        "checkpoint": "4A_CORE",
        "message": "我还有 500 美元，可以加仓吗？",
    },
    {
        "order": 4,
        "checkpoint": "4B_STRATEGY",
        "message": "我主要是长期仓，GOOG LONG_TERM 的目标投入是 300 美元。",
    },
    {
        "order": 5,
        "checkpoint": "4B_STRATEGY",
        "message": "如果跌到 320 美元呢？",
    },
    {
        "order": 6,
        "checkpoint": "4B_STRATEGY",
        "message": "请结合我现在的持仓、市场和最新信息重新分析。",
    },
)


class Phase4Gate(StrEnum):
    """Phase 4 Case 所属的独立验收 Gate。"""

    CORE_4A = "CORE_4A"
    OPEN_RESEARCH_4A = "OPEN_RESEARCH_4A"
    EARNINGS_REGRESSION = "EARNINGS_REGRESSION"
    STRATEGY_4B = "STRATEGY_4B"


class Phase4EvidenceStatus(StrEnum):
    """尚未启用独立 Gate 时的证据状态。"""

    NOT_MEASURED = "NOT_MEASURED"


@dataclass(frozen=True, slots=True)
class Phase4CaseTarget:
    """一个既有 Case 在 Phase 4 中的目标 Scope 与延后语义。"""

    case_id: str
    gate: Phase4Gate
    enabled_scope: ScenarioExecutionScope
    deferred_scope: ScenarioExecutionScope | None = None
    deferred_evidence_status: Phase4EvidenceStatus | None = None

    def as_dict(self) -> dict[str, str | None]:
        """输出可写入 Artifact 的稳定 Manifest 记录。"""

        return {
            "case_id": self.case_id,
            "gate": self.gate.value,
            "enabled_scope": self.enabled_scope.value,
            "deferred_scope": (
                self.deferred_scope.value if self.deferred_scope is not None else None
            ),
            "deferred_evidence_status": (
                self.deferred_evidence_status.value
                if self.deferred_evidence_status is not None
                else None
            ),
        }


def _targets(
    case_ids: tuple[str, ...],
    gate: Phase4Gate,
    enabled_scope: ScenarioExecutionScope,
    *,
    deferred_scope: ScenarioExecutionScope | None = None,
    deferred_evidence_status: Phase4EvidenceStatus | None = None,
) -> tuple[Phase4CaseTarget, ...]:
    return tuple(
        Phase4CaseTarget(
            case_id,
            gate,
            enabled_scope,
            deferred_scope,
            deferred_evidence_status,
        )
        for case_id in case_ids
    )


PHASE4_CORE_CASE_IDS = (
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
PHASE4_RESEARCH_CASE_IDS = ("AQ01", "AQ02", "AQ19")
PHASE4_EARNINGS_CASE_IDS = ("AQ04",)
PHASE4_STRATEGY_CASE_IDS = ("AQ13", "AQ14", "AQ15", "AQ16")

PHASE4_CASE_TARGETS = (
    *_targets(
        PHASE4_CORE_CASE_IDS,
        Phase4Gate.CORE_4A,
        ScenarioExecutionScope.FULL,
    ),
    *_targets(
        PHASE4_RESEARCH_CASE_IDS,
        Phase4Gate.OPEN_RESEARCH_4A,
        ScenarioExecutionScope.FULL,
        deferred_scope=ScenarioExecutionScope.DIAGNOSTIC,
        deferred_evidence_status=Phase4EvidenceStatus.NOT_MEASURED,
    ),
    *_targets(
        PHASE4_EARNINGS_CASE_IDS,
        Phase4Gate.EARNINGS_REGRESSION,
        ScenarioExecutionScope.DIAGNOSTIC,
    ),
    *_targets(
        PHASE4_STRATEGY_CASE_IDS,
        Phase4Gate.STRATEGY_4B,
        ScenarioExecutionScope.FULL,
    ),
)
PHASE4_TARGETS_BY_ID = {target.case_id: target for target in PHASE4_CASE_TARGETS}


def _json_default(value: object) -> str:
    """使用与 0.1 Harness 相同的稳定值序列化。"""

    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    return str(value)


def current_base_manifest_sha256() -> str:
    """计算当前 0.1 Manifest Digest，用于检测历史 Fixture 漂移。"""

    serialized = json.dumps(
        base_manifest_payload(),
        ensure_ascii=False,
        sort_keys=True,
        default=_json_default,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def phase4_manifest_payload() -> dict[str, object]:
    """生成不改写 Dataset 0.1 Case / Fixture / Rubric 的 0.2 Manifest。"""

    return {
        "dataset_id": DATASET_ID,
        "dataset_version": PHASE4_DATASET_VERSION,
        "base_dataset_version": PHASE4_BASE_DATASET_VERSION,
        "base_manifest_sha256": PHASE4_BASE_MANIFEST_SHA256,
        "rubric_version": RUBRIC_VERSION,
        "base_case_ids": [case.id for case in CASES],
        "checkpoint_sequence": list(PHASE4_CHECKPOINT_SEQUENCE),
        "independent_gates": list(PHASE4_INDEPENDENT_GATES),
        "sequential_scripts": [
            {
                "id": "phase4-complete-ask-v1",
                "steps": list(PHASE4_CONTINUOUS_ASK_SCRIPT),
            }
        ],
        "targets": [target.as_dict() for target in PHASE4_CASE_TARGETS],
    }
