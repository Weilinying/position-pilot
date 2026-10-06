"""Gemini Production Final 的固定 Fixture Smoke 与显式在线入口。"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID

from ask_quality_cases import CASES_BY_ID
from behavioral_harness import (
    NOW,
    USER_ID,
    FixedMarketContext,
    FixedMarketData,
    FixedNews,
    FixedPortfolioReader,
)
from gemini_final_candidate import (
    CANDIDATE_PATH,
    SMOKE_BUDGET,
    candidate_payload,
    verify_candidate,
)
from pydantic import PostgresDsn, SecretStr

from position_pilot.application.agent_runtime import (
    AgentRunBudget,
    AgentRunRequest,
    AgentRunResult,
    AgentRunStatus,
    AgentRuntime,
)
from position_pilot.application.conversation_citations import (
    CitationValidationError,
    validate_citations,
)
from position_pilot.application.investment_agent import (
    CURRENT_QUOTE_TOOL_NAME,
    InvestmentAnswer,
    InvestmentRequestFailure,
)
from position_pilot.application.native_investment_agent import NativeInvestmentAgent
from position_pilot.application.source_registry import ContextSourceType
from position_pilot.config import Settings
from position_pilot.domain.portfolio import CashBalance, PortfolioState
from position_pilot.integrations.pydantic_ai_runtime import create_pydantic_ai_runtime

RUN_ENV = "RUN_GEMINI_PRODUCTION_SMOKE"
FIXED_QUESTION = (
    "请查询 GOOG 当前报价，并根据我明确陈述的长期依据提出待确认的长期 Thesis："
    "我看好 Google 搜索与 Cloud 长期竞争力。"
)
QUESTION_EVIDENCE = "我看好 Google 搜索与 Cloud 长期竞争力。"
SAFE_ARTIFACT_NAME = "smoke.json"


class BoundedSmokeRuntime(AgentRuntime):
    """固定 Smoke 请求预算，并拒绝任何 Application Final Repair。"""

    def __init__(self, delegate: AgentRuntime) -> None:
        self.delegate = delegate
        self.calls: list[dict[str, object]] = []
        self.tool_names: tuple[str, ...] = ()

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        if self.calls:
            self.calls.append({"status": "REJECTED", "failure_code": "FINAL_REPAIR_PROHIBITED"})
            return AgentRunResult(
                AgentRunStatus.FAILED,
                None,
                "FINAL_REPAIR_PROHIBITED",
                (),
                (),
                None,
                0.0,
            )
        self.tool_names = tuple(binding.definition.name for binding in request.tools)
        strategy_enabled = request.strategy_candidates_enabled
        bounded_request = replace(
            request,
            budget=AgentRunBudget(
                model_requests=cast(int, SMOKE_BUDGET["model_requests"]),
                tool_calls=cast(int, SMOKE_BUDGET["quote_tool_attempts"]),
                wall_clock_seconds=SMOKE_BUDGET["wall_clock_seconds"],
            ),
        )
        result = self.delegate.run(bounded_request)
        self.calls.append(
            {
                "status": result.status.value,
                "failure_code": result.failure_code,
                "provider_http_status": result.provider_http_status,
                "provider_error_code": result.provider_error_code,
                "framework_error_kind": result.framework_error_kind,
                "model_request_count": result.model_request_count,
                "tool_attempt_count": result.tool_attempt_count,
                "strategy_candidates_enabled": strategy_enabled,
                "tool_trace": [
                    {
                        "name": trace.name,
                        "status": trace.status,
                        "error_code": trace.error_code,
                        "arguments": dict(trace.arguments),
                        "sources": [dict(source) for source in trace.sources],
                    }
                    for trace in result.tool_trace
                ],
            }
        )
        return result


def make_settings(api_key: str) -> Settings:
    """只接受显式 Gemini Key，数据库地址固定为不连接的占位 DSN。"""

    if not api_key.strip():
        raise ValueError("GEMINI_API_KEY_REQUIRED")
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=PostgresDsn("postgresql+psycopg://unused:unused@localhost/unused"),
        llm_provider="GOOGLE_GEMINI",
        llm_model="gemini-3.8-flash",
        llm_api_key=None,
        gemini_api_key=SecretStr(api_key),
        native_llm_request_timeout_seconds=60.0,
    )


def _fixture_agent(runtime: AgentRuntime) -> NativeInvestmentAgent:
    case = CASES_BY_ID["AQ03"]
    state = PortfolioState(
        user_id=USER_ID,
        cash=CashBalance(USER_ID, Decimal("10000"), case.available_cash),
        positions=case.positions,
        transaction_count=len(case.transactions),
    )
    return NativeInvestmentAgent(
        FixedPortfolioReader(state=state, transactions=case.transactions),
        FixedMarketData(case.market_results, {}),
        runtime,
        news=FixedNews({}),
        market_context=FixedMarketContext(case.market_context_result),
        clock=lambda: NOW + timedelta(minutes=30),
        enabled_tool_names=frozenset({CURRENT_QUOTE_TOOL_NAME}),
        wall_clock_budget_seconds=60.0,
    )


def _success_checks(
    answer: InvestmentAnswer | InvestmentRequestFailure,
    runtime: BoundedSmokeRuntime,
) -> dict[str, object]:
    call = runtime.calls[0] if runtime.calls else {}
    traces = call.get("tool_trace", [])
    traces = traces if isinstance(traces, list) else []
    quote_traces = [
        item
        for item in traces
        if isinstance(item, dict) and item.get("name") == CURRENT_QUOTE_TOOL_NAME
    ]
    quote_source_ids = {
        source.get("source_id")
        for item in quote_traces
        if isinstance(item, dict)
        for source in item.get("sources", [])
        if isinstance(source, dict)
        and source.get("type") == ContextSourceType.CURRENT_QUOTE.value
        and source.get("status") == "OK"
        and source.get("ticker") == "GOOG"
    }
    citation_ids: tuple[UUID, ...] = ()
    if isinstance(answer, InvestmentAnswer):
        try:
            citation_ids = validate_citations(answer.answer, answer.sources)
        except CitationValidationError:
            citation_ids = ()
    answer_source_ids = (
        {
            str(source.source_id)
            for source in answer.sources
            if isinstance(answer, InvestmentAnswer)
            and source.type is ContextSourceType.CURRENT_QUOTE
            and source.status == "OK"
        }
        if isinstance(answer, InvestmentAnswer)
        else set()
    )
    candidate = answer.strategy_draft if isinstance(answer, InvestmentAnswer) else None
    candidate_valid = bool(
        candidate is not None
        and candidate.scope.ticker == "GOOG"
        and candidate.scope.position_type.value == "LONG_TERM"
        and candidate.kind.value == "INVESTMENT_THESIS_V1"
        and candidate.origin.value == "USER_STATED_INTENT"
        and candidate.evidence_quote in FIXED_QUESTION
    )
    return {
        "answer_completed": isinstance(answer, InvestmentAnswer),
        "quote_tool_attempts": len(quote_traces),
        "quote_tool_succeeded": any(
            isinstance(item, dict) and item.get("status") == "OK" for item in quote_traces
        ),
        "quote_source_present": bool(quote_source_ids & answer_source_ids),
        "valid_inline_quote_citation": bool(
            {str(item) for item in citation_ids} & answer_source_ids
        ),
        "typed_strategy_candidate_valid": candidate_valid,
        "candidate_schema_exposed": call.get("strategy_candidates_enabled") is True,
        "model_request_count": call.get("model_request_count", 0),
        "tool_attempt_count": call.get("tool_attempt_count", 0),
        "application_final_repair_count": sum(
            item.get("failure_code") == "FINAL_REPAIR_PROHIBITED" for item in runtime.calls
        ),
        "exposed_tools": runtime.tool_names,
        "failure_code": answer.code.value if isinstance(answer, InvestmentRequestFailure) else None,
    }


def run_smoke(settings: Settings) -> dict[str, object]:
    """用真实 Production Factory 和固定 Portfolio / Quote Fixture 执行一次 Smoke。"""

    runtime = create_pydantic_ai_runtime(settings)
    bounded = BoundedSmokeRuntime(runtime)
    report: dict[str, object] = {
        "provider": runtime.provider_name,
        "model": runtime.model_name,
        "output_mechanism": runtime._output_mechanism,
        "status": "FAIL",
        "behavioral_status": "NOT_EVALUATED",
        "evidence_scope": "FIXTURE_ONLY_NOT_LIVE_MARKET_ACCEPTANCE",
        "database_access": False,
        "search_exposed": False,
        "budget": SMOKE_BUDGET,
    }
    if (
        runtime.provider_name != "GOOGLE_GEMINI"
        or runtime.model_name != "gemini-3.8-flash"
        or runtime._output_mechanism != "NATIVE"
    ):
        report.update(failure_code="PRODUCTION_RUNTIME_MISMATCH")
        return report
    try:
        answer = _fixture_agent(bounded).answer_with_intent(
            USER_ID,
            FIXED_QUESTION,
            (),
            (),
        )
    except Exception as error:  # noqa: BLE001 - Provider 原文可能带敏感信息，只保存类型。
        report.update(failure_type=type(error).__name__, failure_code="SMOKE_EXECUTION_EXCEPTION")
        return report
    checks = _success_checks(answer, bounded)
    passed = (
        checks["answer_completed"] is True
        and checks["quote_tool_attempts"] == 1
        and checks["quote_tool_succeeded"] is True
        and checks["quote_source_present"] is True
        and checks["valid_inline_quote_citation"] is True
        and checks["typed_strategy_candidate_valid"] is True
        and checks["candidate_schema_exposed"] is True
        and checks["model_request_count"] == 2
        and checks["tool_attempt_count"] == 1
        and checks["application_final_repair_count"] == 0
        and checks["exposed_tools"] == (CURRENT_QUOTE_TOOL_NAME,)
    )
    report.update(
        status="PASS" if passed else "FAIL",
        failure_code=None if passed else "SMOKE_CONTRACT_INCOMPLETE",
        checks=checks,
        answer=answer.answer if isinstance(answer, InvestmentAnswer) else None,
        sources=[
            {
                "type": source.type.value,
                "status": source.status,
                "ticker": source.ticker,
                "source_id": str(source.source_id) if source.source_id else None,
            }
            for source in answer.sources
        ]
        if isinstance(answer, InvestmentAnswer)
        else [],
        candidate=answer.strategy_draft.model_dump(mode="json")
        if isinstance(answer, InvestmentAnswer) and answer.strategy_draft
        else None,
        runtime_calls=bounded.calls,
    )
    return report


def main(argv: list[str] | None = None) -> int:
    """提供离线 Candidate 冻结 / 校验与双开关在线 Smoke。"""

    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--freeze", action="store_true")
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--online", action="store_true")
    parser.add_argument("--candidate", type=Path, default=CANDIDATE_PATH)
    parser.add_argument("--artifact-dir", type=Path)
    args = parser.parse_args(argv)

    if args.freeze:
        try:
            if args.candidate.exists():
                raise ValueError("CANDIDATE_ALREADY_EXISTS")
            payload = candidate_payload()
            args.candidate.parent.mkdir(parents=True, exist_ok=True)
            args.candidate.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        except Exception as error:  # noqa: BLE001 - 仅输出稳定错误类型与安全码。
            print(json.dumps({"status": "FAIL", "failure_code": type(error).__name__}))
            return 1
        print(json.dumps({"status": "FROZEN_OFFLINE", "candidate": str(args.candidate)}))
        return 0

    if args.online:
        if os.environ.get(RUN_ENV) != "1":
            print(json.dumps({"status": "BLOCKED", "failure_code": "ONLINE_OPT_IN_REQUIRED"}))
            return 2
        if args.artifact_dir is None:
            print(json.dumps({"status": "BLOCKED", "failure_code": "ARTIFACT_DIR_REQUIRED"}))
            return 2
        try:
            verify_candidate(args.candidate)
        except Exception as error:  # noqa: BLE001 - 不序列化异常文本。
            print(json.dumps({"status": "BLOCKED", "failure_code": type(error).__name__}))
            return 2
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key.strip():
            print(json.dumps({"status": "BLOCKED", "failure_code": "GEMINI_API_KEY_REQUIRED"}))
            return 2
        try:
            args.artifact_dir.mkdir(parents=True, exist_ok=False)
        except Exception as error:  # noqa: BLE001 - 不覆盖或复用既有目录。
            print(json.dumps({"status": "BLOCKED", "failure_code": type(error).__name__}))
            return 2
        try:
            settings = make_settings(api_key)
        except Exception as error:  # noqa: BLE001 - ValidationError 可能含输入值，只保留类型。
            report: dict[str, object] = {
                "status": "FAIL",
                "failure_code": "SETTINGS_VALIDATION_FAILED",
                "failure_type": type(error).__name__,
                "provider": "GOOGLE_GEMINI",
                "model": "gemini-3.8-flash",
                "budget": SMOKE_BUDGET,
            }
            (args.artifact_dir / SAFE_ARTIFACT_NAME).write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n"
            )
            print(json.dumps({"status": report["status"], "artifact": SAFE_ARTIFACT_NAME}))
            return 1
        report = run_smoke(settings)
        (args.artifact_dir / SAFE_ARTIFACT_NAME).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )
        print(json.dumps({"status": report["status"], "artifact": SAFE_ARTIFACT_NAME}))
        return 0 if report["status"] == "PASS" else 1

    try:
        record = verify_candidate(args.candidate)
    except Exception as error:  # noqa: BLE001 - 离线检查不读取 Key / .env。
        print(json.dumps({"status": "FAIL", "failure_code": type(error).__name__}))
        return 1
    print(
        json.dumps(
            {
                "status": "PREFLIGHT_PASS_AWAITING_USER_EXECUTION",
                "candidate_id": record.get("candidate_id"),
                "online": False,
                "budget": SMOKE_BUDGET,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
