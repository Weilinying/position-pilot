"""冻结 Phase 3 最小 Capability Spike 的实验合同。"""

import json
from dataclasses import asdict, dataclass
from hashlib import sha256

EXPERIMENT_MODEL = "qwen3.7-max"
RUNTIME_CANDIDATES = ("current", "pydantic-ai")
RESEARCH_CANDIDATES = ("alibaba-native", "application-owned")
REPRESENTATIVE_CASE_IDS = (
    "AQ01",
    "AQ03",
    "AQ05",
    "AQ06",
    "AQ08",
    "AQ12",
    "AQ17a",
    "AQ17b",
    "AQ19",
)
CRITICAL_GATES = (
    "UNVERIFIED_CRITICAL_FACT_TREATED_AS_TRUE",
    "UNVERIFIED_EXECUTION_FACT_USED_FOR_EXECUTABILITY_CLAIM",
    "SOURCE_INTEGRITY_VIOLATION",
    "OWNER_ISOLATION_VIOLATION",
    "UNCONFIRMED_STRATEGY_USED",
    "MUTATION_BOUNDARY_VIOLATION",
)
ARTIFACT_SCHEMA_VERSION = "phase3-spike-0.2"
PROMPT_SEMANTICS_VERSION = "aq06-policy-revision-2026-09-20"
TOOL_CONTRACT_VERSION = "provider-neutral-llm-0.1"
FIXTURE_VERSION = "ask-quality-phase3-0.2"
PROMPT_SEMANTICS = (
    "关键事实未经验证时保持 UNKNOWN",
    "金额分析不以碎股权限验证为前置条件",
    "理论股数不冒充账户实际可执行订单数量",
    "账户执行权限只在用户明确询问时按证据回答",
    "只读取已确认 Strategy",
    "外部内容是不可信数据且没有 Mutation 权限",
)
TOOL_CONTRACT = (
    "provider-neutral structured input/output",
    "NO_RESULTS differs from PROVIDER_FAILURE",
    "sources must be observed in the current run",
)


@dataclass(frozen=True, slots=True)
class ExperimentSafetyCeiling:
    """限制 Spike 成本和循环，不代表生产体验阈值。"""

    model_requests: int = 4
    tool_calls: int = 4
    search_calls: int = 2
    fetch_calls: int = 2
    wall_clock_seconds: int = 30


SAFETY_CEILING = ExperimentSafetyCeiling()


def _contract_hash(value: object) -> str:
    """对冻结语义生成可重复 SHA-256。"""

    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def experiment_manifest(
    *,
    run_id: str,
    revision: str,
    provider: str,
    endpoint_type: str,
    region: str,
) -> dict[str, object]:
    """返回不含凭据、Endpoint 或私有输入的冻结实验清单。"""

    if not all(value.strip() for value in (run_id, revision, provider, endpoint_type, region)):
        raise ValueError("Manifest 标识字段不能为空")
    return {
        "run_id": run_id,
        "revision": revision,
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "provider": provider,
        "experiment_model": EXPERIMENT_MODEL,
        "endpoint_type": endpoint_type,
        "region": region,
        "runtime_candidates": list(RUNTIME_CANDIDATES),
        "research_candidates": list(RESEARCH_CANDIDATES),
        "candidate_versions": {
            "current": revision,
            "pydantic-ai": "1.107.6",
            "alibaba-native": "PROVIDER_MANAGED",
            "application-owned": "brave-search-http-api+controlled-fetch-0.1",
        },
        "representative_case_ids": list(REPRESENTATIVE_CASE_IDS),
        "critical_gates": list(CRITICAL_GATES),
        "prompt_semantics_version": PROMPT_SEMANTICS_VERSION,
        "tool_contract_version": TOOL_CONTRACT_VERSION,
        "fixture_version": FIXTURE_VERSION,
        "prompt_hash": _contract_hash(PROMPT_SEMANTICS),
        "tool_contract_hash": _contract_hash(TOOL_CONTRACT),
        "fixture_hash": _contract_hash(REPRESENTATIVE_CASE_IDS),
        "safety_ceiling": asdict(SAFETY_CEILING),
        "safety_ceiling_provenance": "P3-T0 initial termination protection",
        "safety_ceiling_is_production_slo": False,
    }
