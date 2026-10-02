"""四组独立 Intent 回归的显式在线入口；不重复 AQ10 或扩展 Core。"""

import json
import os
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from time import monotonic
from typing import cast

import phase4_core_harness
import pytest
from ask_quality_cases import CASES_BY_ID
from behavioral_harness import USER_ID
from phase4_core_harness import RecordingAgentRuntime, build_native_agent
from test_native_intent_policy import CASES

from position_pilot.application.agent_runtime import AgentRuntime
from position_pilot.application.investment_agent import InvestmentAnswer


def run_intent_cases(
    runtime_factory: Callable[[], AgentRuntime], artifact_dir: Path
) -> list[dict[str, object]]:
    """每例从空历史开始，逐例保存证据；请求失败即停止，不重复失败请求。"""

    artifact_dir.mkdir(parents=True, exist_ok=False)
    records: list[dict[str, object]] = []
    for index, case in enumerate(CASES, start=1):
        case_id = f"INTENT{index:02d}"
        fixture = replace(
            CASES_BY_ID["AQ03"],
            id=case_id,
            parent_id=case_id,
            target_messages=(case.question,),
            executable_questions=(case.question,),
        )
        runtime = RecordingAgentRuntime(runtime_factory())
        started_at = monotonic()
        result = build_native_agent(fixture, runtime).answer_with_history(
            USER_ID, case.question, ()
        )
        trace = [
            item
            for call in runtime.calls
            for item in cast(list[dict[str, object]], call["tool_trace"])
        ]
        names = sorted(str(item["name"]) for item in trace)
        completed = isinstance(result, InvestmentAnswer)
        quote_purposes = [
            cast(dict[str, object], item["arguments"]).get("request_purpose")
            for item in trace
            if item["name"] == "get_current_quote" and item["invoked_by_model"]
        ]
        routing_matches = (
            names == sorted(case.expected_tools)
            and all(item["status"] == "OK" for item in trace)
            and quote_purposes == ([] if case.request_purpose is None else [case.request_purpose])
        )
        record = phase4_core_harness._turn_record(
            fixture,
            case.question,
            1,
            (),
            result,
            runtime.calls,
            (monotonic() - started_at) * 1000,
        )
        record.update(
            {
                "case_id": case_id,
                "routing_status": ("PASS" if routing_matches else "FAIL")
                if completed
                else "NOT_EVALUATED",
                "human_checks": list(case.human_checks),
            }
        )
        records.append(record)
        with (artifact_dir / "cases.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(
            json.dumps(
                {
                    name: record[name]
                    for name in ("case_id", "execution_status", "routing_status", "answer")
                },
                ensure_ascii=False,
            )
        )
        if not completed:
            break
    return records


@pytest.mark.online
@pytest.mark.behavioral
@pytest.mark.skipif(
    os.getenv("RUN_PHASE4_INTENT_EVAL") != "1",
    reason="需要显式启用四组 Intent 在线回归",
)
def test_native_intent_policy_live_run() -> None:
    """只允许当前批准的 Gemini 模型；质量判定仍等待 Human Review。"""

    if os.getenv("LLM_PROVIDER") != "GOOGLE_GEMINI":
        pytest.fail("Intent 回归只装配 GOOGLE_GEMINI")
    if os.getenv("LLM_MODEL") != "gemini-3.8-flash":
        pytest.fail("Intent 回归只装配 gemini-3.8-flash")
    missing = [name for name in ("GEMINI_API_KEY", "PHASE4_ARTIFACT_DIR") if not os.getenv(name)]
    if missing:
        pytest.fail(f"缺少进程环境变量: {', '.join(missing)}")
    artifact_dir = Path(os.environ["PHASE4_ARTIFACT_DIR"])

    def runtime_factory() -> AgentRuntime:
        runtime = phase4_core_harness._build_eval_runtime(os.environ)
        assert runtime is not None
        return runtime

    records = run_intent_cases(runtime_factory, artifact_dir)
    (artifact_dir / "manifest.json").write_text(
        json.dumps(
            {
                "provider": "GOOGLE_GEMINI",
                "model": "gemini-3.8-flash",
                "scope": "FOUR_INDEPENDENT_INTENT_CASES",
                "market_data": "FIXTURE_ONLY",
                "quote": {"ticker": "GOOG", "last_price": "210.25"},
                "history_message_count_per_case": 0,
                "wall_clock_budget_seconds": 30.0,
                "human_review": "PENDING",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"artifact_dir": str(artifact_dir), "completed_records": len(records)}))
