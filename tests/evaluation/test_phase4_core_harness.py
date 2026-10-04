"""Phase 4 4A Eval 入口的离线 Contract；不调用真实模型。"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import phase4_core_harness
import pytest
from ask_quality_cases import CASES_BY_ID
from ask_quality_phase4_manifest import PHASE4_CORE_CASE_IDS, PHASE4_RESEARCH_CASE_IDS
from behavioral_harness import USER_ID
from phase4_core_harness import (
    CORE_REPEAT_CASE_IDS,
    PRIMARY_CASE_IDS,
    RUN_PHASE4_EVAL_ENV,
    RecordingAgentRuntime,
    build_native_agent,
    run_phase4_evaluation,
    selected_phase4_case_ids,
)

from position_pilot.application.agent_runtime import (
    AgentRunRequest,
    AgentRunResult,
    AgentRunStatus,
    AgentToolTrace,
)


@dataclass(slots=True)
class ScriptedRuntime:
    """只返回合法 Portfolio 回答的本地 Native Runtime。"""

    requests: list[AgentRunRequest] = field(default_factory=list)

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        self.requests.append(request)
        return AgentRunResult(
            AgentRunStatus.COMPLETED,
            json.dumps(
                {"answer": "固定测试回答。", "source_refs": [{"type": "PORTFOLIO_SNAPSHOT"}]}
            ),
            None,
            (),
            (),
            None,
            1.0,
        )


def test_phase4_case_selection_is_independent_of_legacy_scope() -> None:
    """4A Primary 与 Repeat 使用 0.2 Scope，Research 独立未测量。"""

    assert tuple(PRIMARY_CASE_IDS[:13]) == PHASE4_CORE_CASE_IDS
    assert PRIMARY_CASE_IDS[-1] == "AQ04"
    assert "AQ06" in CORE_REPEAT_CASE_IDS
    assert selected_phase4_case_ids({"EVAL_REPETITION_INDEX": "2"}) == CORE_REPEAT_CASE_IDS
    with pytest.raises(ValueError, match="只能选择 Core"):
        selected_phase4_case_ids({"PHASE4_CASE_IDS": PHASE4_RESEARCH_CASE_IDS[0]})


def test_offline_manifest_keeps_core_not_run_and_research_not_measured() -> None:
    """没有显式在线 Opt-in 时不伪造 Core 质量或 Research 能力。"""

    result = cast(dict[str, Any], run_phase4_evaluation(environment={}))
    records = {item["case_id"]: item for item in result["records"]}
    summary = result["summary"]

    assert summary["core_full"]["target_case_count"] == 13
    assert summary["core_full"]["completed_case_count"] == 0
    assert summary["core_full"]["request_success_rate"] is None
    assert records["AQ06"]["evidence_status"] == "NOT_RUN"
    assert all(
        records[case_id]["evidence_status"] == "NOT_MEASURED"
        for case_id in PHASE4_RESEARCH_CASE_IDS
    )
    assert summary["research_gate"]["evidence_status"] == "NOT_MEASURED"


def test_eval_only_agent_budget_can_compare_prior_30_second_ceiling() -> None:
    """4A Eval 默认使用 60 秒，显式 30 秒仍可复现旧时限边界。"""

    default_runtime = ScriptedRuntime()
    diagnostic_runtime = ScriptedRuntime()
    case = CASES_BY_ID["AQ07"]
    build_native_agent(case, default_runtime).answer_with_history(
        USER_ID, case.executable_questions[0], ()
    )
    build_native_agent(
        case, diagnostic_runtime, wall_clock_budget_seconds=30.0
    ).answer_with_history(USER_ID, case.executable_questions[0], ())

    assert default_runtime.requests[0].budget.wall_clock_seconds == 60.0
    assert diagnostic_runtime.requests[0].budget.wall_clock_seconds == 30.0


def test_fixture_runner_uses_native_agent_and_preserves_unknown_usage(tmp_path: Path) -> None:
    """Fixture 回答只验证 Native 执行路径与 Artifact，不冒充真实评分。"""

    runtime = ScriptedRuntime()
    artifact_dir = tmp_path / "phase4-evidence"
    result = cast(
        dict[str, Any],
        run_phase4_evaluation(
            environment={
                RUN_PHASE4_EVAL_ENV: "1",
                "PHASE4_CASE_IDS": "AQ20",
                "PHASE4_ARTIFACT_DIR": str(artifact_dir),
                "EVAL_RUN_ID": "offline-test",
                "LLM_API_KEY": "fixture-only-never-transmitted",
            },
            runtime_factory=lambda _: runtime,
        ),
    )
    record = next(item for item in result["records"] if item["case_id"] == "AQ20")

    assert len(runtime.requests) == 1
    assert record["execution_status"] == "COMPLETED"
    assert record["usage"]["total_tokens"] == "UNKNOWN"
    assert record["turns"][0]["runtime_calls"][0]["provider_finish_reason"] is None
    assert result["summary"]["core_full"]["completed_case_count"] == 1
    assert result["metadata"]["native_request_timeout_seconds"] == 60.0
    assert result["metadata"]["wall_clock_budget_seconds"] == 60.0
    assert result["summary"]["latency"]["median_ms"] is not None
    assert (artifact_dir / "manifest.json").is_file()
    assert (artifact_dir / "cases.jsonl").is_file()
    assert (artifact_dir / "summary.json").is_file()
    progress = [
        json.loads(line) for line in (artifact_dir / "progress.jsonl").read_text().splitlines()
    ]
    assert progress[-1] == {"status": "RUN_FINISHED", "complete": True}
    assert progress[2]["status"] == "TURN_FINISHED"
    artifacts = "".join(path.read_text(encoding="utf-8") for path in artifact_dir.iterdir())
    assert "fixture-only-never-transmitted" not in artifacts
    assert "prompt_sha256" in artifacts
    assert "tool_contract_sha256" in artifacts
    assert "fixture_manifest_sha256" in artifacts


def test_eval_records_selected_model_without_changing_fixture_scope(tmp_path: Path) -> None:
    """可用模型由本轮显式指定，元数据保留模型身份与固定 Case 范围。"""

    selected_model = "qwen3.7-max-other-version"
    result = cast(
        dict[str, Any],
        run_phase4_evaluation(
            environment={
                RUN_PHASE4_EVAL_ENV: "1",
                "LLM_MODEL": selected_model,
                "PHASE4_CASE_IDS": "AQ20",
                "PHASE4_ARTIFACT_DIR": str(tmp_path),
                "EVAL_RUN_ID": "other-model-diagnostic",
            },
            runtime_factory=lambda _: ScriptedRuntime(),
        ),
    )

    assert result["metadata"]["model"] == selected_model
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_metadata"]["model"] == selected_model
    assert result["summary"]["core_full"]["selected_case_count"] == 1


def test_failed_earnings_diagnostic_is_reported_as_attempted() -> None:
    """AQ04 请求失败仍属于已执行证据，不能在汇总中误写为未运行。"""

    class FailedRuntime(ScriptedRuntime):
        def run(self, request: AgentRunRequest) -> AgentRunResult:
            self.requests.append(request)
            return AgentRunResult(
                AgentRunStatus.FAILED,
                None,
                "MODEL_HTTP_FAILURE",
                (),
                (),
                None,
                1.0,
                provider_http_status=400,
                provider_error_code="InvalidParameter",
                provider_error_message="tool_choice is unsupported in thinking mode",
            )

    runtime = FailedRuntime()
    result = cast(
        dict[str, Any],
        run_phase4_evaluation(
            environment={RUN_PHASE4_EVAL_ENV: "1", "PHASE4_CASE_IDS": "AQ04"},
            runtime_factory=lambda _: runtime,
        ),
    )
    diagnostic = result["summary"]["earnings_diagnostic"]
    record = next(item for item in result["records"] if item["case_id"] == "AQ04")

    assert len(runtime.requests) == 1
    assert record["execution_status"] == "REQUEST_FAILED"
    provider_error = record["turns"][0]["runtime_calls"][0]["provider_error"]
    assert provider_error == {
        "http_status": 400,
        "error_code": "InvalidParameter",
        "error_message": "tool_choice is unsupported in thinking mode",
    }
    assert diagnostic["completed_case_count"] == 0
    assert diagnostic["request_failed_case_count"] == 1
    assert diagnostic["not_run_case_count"] == 0
    assert diagnostic["evidence_status"] == "MEASURED"


def test_framework_failure_trace_keeps_only_safe_classification() -> None:
    """Eval 记录框架失败分类，不持久化可能包含请求内容的异常正文。"""

    class FailedRuntime(ScriptedRuntime):
        def run(self, request: AgentRunRequest) -> AgentRunResult:
            self.requests.append(request)
            return AgentRunResult(
                AgentRunStatus.FAILED,
                None,
                "INVALID_PROVIDER_RESPONSE",
                (),
                (),
                None,
                1.0,
                framework_error_kind="OUTPUT_RETRY_EXHAUSTED",
                framework_error_cause="ValidationError",
            )

    runtime = RecordingAgentRuntime(FailedRuntime())
    case = CASES_BY_ID["AQ20"]
    build_native_agent(case, runtime).answer_with_history(USER_ID, case.executable_questions[0], ())

    assert runtime.calls[0]["framework_error"] == {
        "kind": "OUTPUT_RETRY_EXHAUSTED",
        "cause": "ValidationError",
    }
    assert runtime.calls[0]["provider_error"] is None


def test_recording_keeps_model_invocations_separate_from_provider_fetches() -> None:
    """Quote 自动补取 Market 时，Eval 分别记录模型调用与真实获取。"""

    class AutomaticMarketRuntime(ScriptedRuntime):
        def run(self, request: AgentRunRequest) -> AgentRunResult:
            self.requests.append(request)
            return AgentRunResult(
                AgentRunStatus.COMPLETED,
                json.dumps(
                    {"answer": "固定测试回答。", "source_refs": [{"type": "PORTFOLIO_SNAPSHOT"}]}
                ),
                None,
                (
                    AgentToolTrace("get_current_quote", {"ticker": "GOOG"}, "OK"),
                    AgentToolTrace(
                        "get_market_context",
                        {},
                        "OK",
                        invoked_by_model=False,
                        provider_fetch_count=1,
                    ),
                ),
                (),
                None,
                1.0,
            )

    runtime = RecordingAgentRuntime(AutomaticMarketRuntime())
    case = CASES_BY_ID["AQ20"]
    build_native_agent(case, runtime).answer_with_history(USER_ID, case.executable_questions[0], ())

    call = runtime.calls[0]
    assert call["tool_invocation_count"] == 1
    assert call["provider_fetch_count"] == 2
    traces = call["tool_trace"]
    assert isinstance(traces, list)
    assert [trace["invoked_by_model"] for trace in traces] == [True, False]
    assert [trace["provider_fetch_count"] for trace in traces] == [1, 1]


def test_multiturn_fixture_injects_prior_visible_answer() -> None:
    """连续 Case 第二轮收到前一轮 User / Assistant 历史。"""

    runtime = ScriptedRuntime()
    result = cast(
        dict[str, Any],
        run_phase4_evaluation(
            environment={RUN_PHASE4_EVAL_ENV: "1", "PHASE4_CASE_IDS": "AQ10"},
            runtime_factory=lambda _: RecordingAgentRuntime(runtime),
        ),
    )
    record = next(item for item in result["records"] if item["case_id"] == "AQ10")

    assert len(runtime.requests) >= 2
    assert record["turns"][0]["history_message_count"] == 0
    assert record["turns"][1]["history_message_count"] == 2
    assert record["turns"][0]["runtime_calls"][0]["final_candidate"] is not None


def test_interrupt_preserves_finished_turn_and_blocks_paid_restart(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """第二轮中断不丢失第一轮证据，已有部分结果也拒绝重跑。"""

    class InterruptedRuntime(ScriptedRuntime):
        def run(self, request: AgentRunRequest) -> AgentRunResult:
            if self.requests:
                raise KeyboardInterrupt
            return super().run(request)

    runtime = InterruptedRuntime()
    environment = {
        RUN_PHASE4_EVAL_ENV: "1",
        "PHASE4_CASE_IDS": "AQ10",
        "PHASE4_ARTIFACT_DIR": str(tmp_path),
    }
    with pytest.raises(KeyboardInterrupt):
        run_phase4_evaluation(environment=environment, runtime_factory=lambda _: runtime)
    events = [json.loads(line) for line in (tmp_path / "progress.jsonl").read_text().splitlines()]
    assert [event["status"] for event in events] == [
        "RUN_STARTED",
        "STARTED",
        "TURN_FINISHED",
        "STARTED",
        "INTERRUPTED",
    ]
    assert events[2]["turn"]["answer"] == "固定测试回答。"
    assert not (tmp_path / "summary.json").exists()
    output = capsys.readouterr().out
    assert "TURN_FINISHED" in output
    assert "固定测试回答" not in output
    with pytest.raises(FileExistsError):
        run_phase4_evaluation(environment=environment, runtime_factory=lambda _: pytest.fail())


def test_failed_turn_still_contributes_user_message_to_next_turn() -> None:
    """Eval 历史与生产 Conversation 一致：失败轮不生成 Assistant，但保留 User。"""

    @dataclass(slots=True)
    class FailFirstRuntime(ScriptedRuntime):
        def run(self, request: AgentRunRequest) -> AgentRunResult:
            if not self.requests:
                self.requests.append(request)
                return AgentRunResult(
                    AgentRunStatus.FAILED,
                    None,
                    "MODEL_HTTP_FAILURE",
                    (),
                    (),
                    None,
                    1.0,
                )
            return ScriptedRuntime.run(self, request)

    runtime = FailFirstRuntime()
    result = cast(
        dict[str, Any],
        run_phase4_evaluation(
            environment={RUN_PHASE4_EVAL_ENV: "1", "PHASE4_CASE_IDS": "AQ10"},
            runtime_factory=lambda _: runtime,
        ),
    )
    record = next(item for item in result["records"] if item["case_id"] == "AQ10")

    assert record["turns"][0]["execution_status"] == "REQUEST_FAILED"
    assert record["turns"][1]["history_message_count"] == 1


def test_existing_artifact_is_not_overwritten(tmp_path: Path) -> None:
    """同一 Run 目录须在模型调用前拒绝，避免重复付费且保留证据。"""

    runtime = ScriptedRuntime()
    environment = {
        "PHASE4_ARTIFACT_DIR": str(tmp_path / "run"),
        "EVAL_RUN_ID": "same-run",
        RUN_PHASE4_EVAL_ENV: "1",
        "PHASE4_CASE_IDS": "AQ20",
    }
    run_phase4_evaluation(environment=environment, runtime_factory=lambda _: runtime)
    original_artifact = (tmp_path / "run" / "summary.json").read_text(encoding="utf-8")
    assert len(runtime.requests) == 1
    with pytest.raises(FileExistsError, match="Artifact 已存在"):
        run_phase4_evaluation(environment=environment, runtime_factory=lambda _: runtime)
    assert len(runtime.requests) == 1
    assert (tmp_path / "run" / "summary.json").read_text(encoding="utf-8") == original_artifact


def test_readiness_executes_fixture_tools_and_does_not_infer_web_search() -> None:
    """实际 Fixture Executor 可调用不代表模型已有联网能力。"""
    report = cast(dict[str, Any], phase4_core_harness.runtime_readiness_check())
    assert report["ready"] is True
    assert report["tools"]["get_current_quote"] == {"callable": True, "status": "OK"}
    assert report["tools"]["get_recent_news"] == {"callable": True, "status": "OK"}
    assert report["tools"]["web_search"]["callable"] is False
    assert report["live_information_access"] == "NOT_EVALUATED"
    assert phase4_core_harness.runtime_readiness_check(require_search=True)["ready"] is False


@pytest.mark.parametrize(
    "http_status,domain,message",
    [
        (400, "PROVIDER_CAPABILITY", "tool_choice is unsupported"),
        (400, "UNCLASSIFIED", "bad request"),
        (401, "ACCESS_OR_AUTH", "unauthorized"),
        (429, "RATE_LIMIT", "quota"),
    ],
)
def test_provider_failure_does_not_score_behavior(
    http_status: int,
    domain: str,
    message: str,
) -> None:
    """请求失败留在可靠性分母，质量评分保持未评估。"""

    class FailedRuntime:
        def run(self, request: AgentRunRequest) -> AgentRunResult:
            return AgentRunResult(
                AgentRunStatus.FAILED,
                None,
                "MODEL_HTTP_FAILURE",
                (),
                (),
                None,
                1.0,
                provider_http_status=http_status,
                provider_error_message=message,
            )

    result = cast(
        dict[str, Any],
        run_phase4_evaluation(
            environment={RUN_PHASE4_EVAL_ENV: "1", "PHASE4_CASE_IDS": "AQ20"},
            runtime_factory=lambda _: FailedRuntime(),
        ),
    )
    turn = next(r for r in result["records"] if r["case_id"] == "AQ20")["turns"][0]
    assert turn["failure_domain"] == domain
    assert turn["behavioral_status"] == "NOT_EVALUATED"
    assert result["summary"]["core_full"]["request_failed_case_count"] == 1
    assert result["summary"]["core_full"]["request_success_rate"] == 0


def test_business_validation_failure_is_separate_from_provider_failure() -> None:
    """模型成功返回但两次伪造引用被拒绝时保留业务失败。"""

    class FabricatedRuntime:
        def run(self, request: AgentRunRequest) -> AgentRunResult:
            return AgentRunResult(
                AgentRunStatus.COMPLETED,
                '{"answer":"假来源 [source:00000000-0000-0000-0000-000000000000]",'
                '"source_refs":[]}',
                None,
                (),
                (),
                None,
                1.0,
            )

    result = cast(
        dict[str, Any],
        run_phase4_evaluation(
            environment={RUN_PHASE4_EVAL_ENV: "1", "PHASE4_CASE_IDS": "AQ20"},
            runtime_factory=lambda _: FabricatedRuntime(),
        ),
    )
    turn = next(r for r in result["records"] if r["case_id"] == "AQ20")["turns"][0]
    assert turn["failure_domain"] == "BEHAVIORAL"
    assert turn["behavioral_status"] == "FAIL"


def test_aihubmix_assembly_and_native_schema_match_smoke() -> None:
    """离线比较测试客户端及 Core 的既有 Native Schema，不创建真实请求。"""
    import asyncio

    from phase4_output_mechanism_spike import (
        _NativeStructuredFinalCandidate,
    )
    from pydantic_ai.providers.openai import OpenAIProvider

    from position_pilot.integrations.pydantic_ai_runtime import (
        PydanticAIRuntime,
    )
    from position_pilot.integrations.pydantic_ai_runtime import (
        _NativeStructuredFinalCandidate as CoreSchema,
    )

    runtime = phase4_core_harness._build_eval_runtime(
        {
            "LLM_PROVIDER": "AIHUBMIX",
            "LLM_API_KEY": "test",
            "LLM_MODEL": "arbitrary-model",
            "LLM_BASE_URL": "https://example.com/v1",
        }
    )
    assert isinstance(runtime, PydanticAIRuntime)
    assert runtime.timeout_seconds == 30.0
    assert runtime.max_retries == 0
    assert runtime._output_mechanism == "NATIVE"
    assert _NativeStructuredFinalCandidate is CoreSchema

    async def inspect() -> None:
        assert runtime._model_context_factory is not None
        async with runtime._model_context_factory() as model:
            assert type(model._provider) is OpenAIProvider
            assert model.profile.supports_json_schema_output is True

    asyncio.run(inspect())


def test_gemini_core_assembly_uses_official_native_model_without_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Core 测试入口只读 Gemini Key，并复用 A/B 已验证的官方 Native 模型。"""
    import asyncio

    from google.genai import Client
    from phase4_provider_support import _GeminiRequestTraceModel
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.providers.google import GoogleProvider

    from position_pilot.integrations.pydantic_ai_runtime import PydanticAIRuntime

    captured_options: list[Any] = []

    def capture_client(**kwargs: Any) -> Client:
        captured_options.append(kwargs["http_options"])
        return Client(**kwargs)

    monkeypatch.setattr("google.genai.Client", capture_client)
    values = {
        "LLM_PROVIDER": "GOOGLE_GEMINI",
        "LLM_MODEL": "gemini-3.8-flash",
        "GEMINI_API_KEY": "offline-fixture-key",
        "LLM_BASE_URL": "https://old-aliyun.example/v1",
    }
    runtime = phase4_core_harness._build_eval_runtime(values)
    assert isinstance(runtime, PydanticAIRuntime)
    assert runtime.provider_name == "GOOGLE_GEMINI"
    assert runtime.model_name == "gemini-3.8-flash"
    assert runtime.timeout_seconds == 60.0
    assert runtime.max_retries == 0
    assert runtime._output_mechanism == "NATIVE"
    assert phase4_core_harness.create_run_metadata(environment=values).llm_base_url == (
        "https://generativelanguage.googleapis.com"
    )

    async def inspect() -> None:
        assert runtime._model_context_factory is not None
        async with runtime._model_context_factory() as model:
            assert isinstance(model, _GeminiRequestTraceModel)
            assert isinstance(model.wrapped, GoogleModel)
            assert type(model.wrapped._provider) is GoogleProvider
            assert model.retry_transport_errors is True
            assert captured_options[0].timeout == 60_000
            assert captured_options[0].httpx_async_client.timeout.read == 60.0

    asyncio.run(inspect())


def test_gemini_trace_distinguishes_sequential_tool_rounds_without_content() -> None:
    """三个分步工具请求会耗尽三次模型请求，逐次记录不保存正文或参数。"""
    import asyncio

    from phase4_provider_support import _GeminiRequestTraceModel
    from pydantic_ai import Agent, UsageLimits
    from pydantic_ai.exceptions import UsageLimitExceeded
    from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
    from pydantic_ai.models.function import AgentInfo, FunctionModel

    tool_calls = (
        ToolCallPart("get_recent_news", {"ticker": "GOOG"}),
        ToolCallPart("get_current_quote", {"ticker": "GOOG"}),
        ToolCallPart("get_market_context", {}),
    )
    model_calls: list[int] = []

    def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        model_calls.append(len(messages))
        index = len(model_calls) - 1
        return ModelResponse(parts=[tool_calls[index] if index < 3 else TextPart("完成")])

    def get_recent_news(ticker: str) -> str:
        return "新闻已取得"

    def get_current_quote(ticker: str) -> str:
        return "报价已取得"

    def get_market_context() -> str:
        return "市场已取得"

    trace: list[dict[str, object]] = []
    agent = Agent(
        _GeminiRequestTraceModel(FunctionModel(reply), trace),
        tools=[get_recent_news, get_current_quote, get_market_context],
        retries=0,
    )
    with pytest.raises(UsageLimitExceeded, match="request_limit of 3"):
        asyncio.run(
            agent.run("固定测试问题", usage_limits=UsageLimits(request_limit=3, tool_calls_limit=4))
        )
    assert len(model_calls) == 3
    assert [item["tool_call_names"] for item in trace] == [
        ["get_recent_news"],
        ["get_current_quote"],
        ["get_market_context"],
    ]
    assert trace[1]["tool_results_in_latest_request"] == ["get_recent_news"]
    assert trace[2]["tool_results_in_latest_request"] == ["get_current_quote"]
    assert all("GOOG" not in item.values() and "完成" not in str(item) for item in trace)


def test_core_artifact_records_only_current_runtime_model_requests() -> None:
    """逐次模型 Trace 随当前 Runtime Call 写入 Artifact，不混入先前轮次。"""

    class TracedRuntime:
        phase4_request_trace: list[dict[str, object]] = [
            {"request_index": 1, "tool_call_names": ["previous_call"]}
        ]

        def run(self, request: AgentRunRequest) -> AgentRunResult:
            self.phase4_request_trace.append(
                {"request_index": 2, "tool_call_names": ["get_current_quote"]}
            )
            return AgentRunResult(
                AgentRunStatus.COMPLETED,
                '{"answer":"固定测试回答。","source_refs":[{"type":"PORTFOLIO_SNAPSHOT"}]}',
                None,
                (),
                (),
                None,
                1.0,
            )

    recording = RecordingAgentRuntime(TracedRuntime())
    case = CASES_BY_ID["AQ20"]
    build_native_agent(case, recording).answer_with_history(
        USER_ID, case.executable_questions[0], ()
    )
    assert recording.calls[0]["model_requests"] == [
        {"request_index": 2, "tool_call_names": ["get_current_quote"]}
    ]


def test_model_request_budget_is_not_classified_as_provider_failure() -> None:
    """本轮已观察的预算耗尽独立归因，不能误报 Provider Capability。"""
    from phase4_provider_support import classify_failure

    assert classify_failure(code="MODEL_REQUEST_BUDGET_EXCEEDED") == (
        "RUNTIME_BUDGET",
        "MODEL_REQUEST_BUDGET_EXCEEDED",
    )


def test_gemini_core_rejects_missing_key_and_other_model() -> None:
    """没有独立 Gemini Key 时不借用旧 LLM Key，也不切换候选模型。"""
    values = {
        "LLM_PROVIDER": "GOOGLE_GEMINI",
        "LLM_MODEL": "gemini-3.8-flash",
        "LLM_API_KEY": "old-aliyun-key",
    }
    assert phase4_core_harness._build_eval_runtime(values) is None
    with pytest.raises(ValueError, match="只允许 gemini-3.8-flash"):
        phase4_core_harness._build_eval_runtime(
            {**values, "GEMINI_API_KEY": "offline-fixture-key", "LLM_MODEL": "other-model"}
        )


def test_gemini_online_entry_requires_no_aliyun_base_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """在线入口的配置校验只要求 Gemini Key；这里不调用模型。"""
    import test_phase4_core_online

    monkeypatch.setenv(RUN_PHASE4_EVAL_ENV, "1")
    monkeypatch.setenv("LLM_PROVIDER", "GOOGLE_GEMINI")
    monkeypatch.setenv("LLM_MODEL", "gemini-3.8-flash")
    monkeypatch.setenv("GEMINI_API_KEY", "offline-fixture-key")
    monkeypatch.setenv("EVAL_RUN_ID", "offline-gemini-entry")
    monkeypatch.setenv("PHASE4_ARTIFACT_DIR", str(tmp_path))
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    calls: list[bool] = []

    def fake_run() -> dict[str, object]:
        calls.append(True)
        return {"summary": {"online_called": False}}

    monkeypatch.setattr(test_phase4_core_online, "run_phase4_evaluation", fake_run)
    test_phase4_core_online.test_phase4_core_live_fixture_run()
    assert calls == [True]


def test_readiness_failure_blocks_model_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Readiness 失败不能仍运行模型或标记行为失败。"""
    monkeypatch.setattr(
        phase4_core_harness,
        "runtime_readiness_check",
        lambda **kwargs: {"ready": False, "scope": "FIXTURE_EXECUTORS_ONLY"},
    )
    runtime = ScriptedRuntime()
    result = cast(
        dict[str, Any],
        run_phase4_evaluation(
            environment={RUN_PHASE4_EVAL_ENV: "1", "PHASE4_CASE_IDS": "AQ20"},
            runtime_factory=lambda _: runtime,
        ),
    )
    assert runtime.requests == []
    record = next(r for r in result["records"] if r["case_id"] == "AQ20")
    assert record["not_run_reason"] == "RUNTIME_NOT_READY"
    assert record["critical_failure_gate"]["status"] == "NOT_EVALUATED"
