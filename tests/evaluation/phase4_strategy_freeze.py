"""4B Candidate 的最小离线预检；只核对已批准 Runtime 与固定脚本。"""

import hashlib
import json
from importlib.metadata import version
from pathlib import Path

from ask_quality_cases import CASES_BY_ID
from ask_quality_phase4_manifest import current_base_manifest_sha256
from behavioral_harness import USER_ID
from phase4_core_harness import _repository_revision, _sha256, build_native_agent
from phase4_strategy_manifest import strategy_manifest

from position_pilot.application.agent_runtime import AgentRunRequest, AgentRunResult, AgentRunStatus
from position_pilot.application.investment_agent import CONTEXT_TOOLS
from position_pilot.application.tool_catalog import current_financial_tool_descriptors
from position_pilot.integrations.pydantic_ai_runtime import _StrategyNativeCandidate


def candidate_profile() -> dict[str, object]:
    """从实际 Native Request 生成 hash 与预算；不装配在线 Provider。"""
    requests: list[AgentRunRequest] = []

    class Probe:
        def run(self, request: AgentRunRequest) -> AgentRunResult:
            requests.append(request)
            return AgentRunResult(
                AgentRunStatus.COMPLETED,
                '{"answer":"固定预检。","source_refs":[{"type":"PORTFOLIO_SNAPSHOT"}]}',
                None,
                (),
                (),
                None,
                0.0,
            )

    build_native_agent(CASES_BY_ID["AQ13"], Probe()).answer_with_intent(USER_ID, "检查意图", (), ())
    request = requests[0]
    policy = {
        tool.name: tool.max_calls_per_run
        for tool in current_financial_tool_descriptors(CONTEXT_TOOLS)
    }
    return {
        "pydantic_ai_version": version("pydantic-ai-slim"),
        "runtime_system_prompt_sha256": hashlib.sha256(
            (request.messages[0].content or "").encode()
        ).hexdigest(),
        "native_output_schema_sha256": _sha256(_StrategyNativeCandidate.model_json_schema()),
        "budget_policy": policy,
        "budget_policy_sha256": _sha256(policy),
        "tool_attempt_budget": request.budget.tool_calls,
        "model_request_budget": request.budget.model_requests,
        "wall_clock_seconds": request.budget.wall_clock_seconds,
        "strategy_manifest_sha256": _sha256(strategy_manifest()),
        "memory_profile": "NOOP",
        "base_fixture_manifest_sha256": current_base_manifest_sha256(),
    }


def verify_candidate(path: Path) -> dict[str, object]:
    """在线请求前拒绝脏树、错误 commit 或 Runtime/脚本漂移。"""
    record: dict[str, object] = json.loads(path.read_text())
    if record.get("commit") != _repository_revision():
        raise ValueError("4B Candidate commit 或 clean working tree 不匹配")
    actual = candidate_profile()
    if record.get("profile") != actual:
        raise ValueError("4B Candidate Runtime / Schema / Budget / Fixture script 不匹配")
    return record
