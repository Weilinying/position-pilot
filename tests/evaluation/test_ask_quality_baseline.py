"""Ask Quality Discovery 阶段一的 Manifest、Reporter 与真实模型入口。"""

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from ask_quality_cases import (
    CASES,
    CASES_BY_ID,
    CONTROLLED_CONTRASTS,
    HOLDOUT_CASE_IDS,
    REPEAT_CASE_IDS,
    AskQualityCase,
    ScenarioExecutionScope,
)
from ask_quality_harness import (
    DEFAULT_EVALUATION_MODEL,
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_TIMEOUT_SECONDS,
    PRODUCTION_BEHAVIOR_REVISION,
    REAL_EVAL_ENV,
    AskQualityReporter,
    ExecutionStatus,
    artifact_dir_from_environment,
    build_summary,
    case_manifest,
    create_run_metadata,
    execute_case,
    manifest_payload,
    not_run_record,
    selected_cases,
)

from position_pilot.application.llm import (
    LLMMessage,
    LLMResponseFormat,
    LLMResponseMetadata,
    LLMResult,
    LLMRole,
    LLMStatus,
    LLMToolCall,
    LLMToolDefinition,
    LLMUsage,
)
from position_pilot.integrations.aliyun_llm import (
    ALIYUN_MODEL_STUDIO,
    AliyunLLMProvider,
    OpenAICompatibleLLMProvider,
)


@dataclass(slots=True)
class RecordingLLM:
    """记录每次独立请求收到的消息，并返回固定合法 Answer。"""

    calls: list[tuple[LLMMessage, ...]] = field(default_factory=list)
    usage: LLMUsage | None = None

    def complete(
        self,
        messages: tuple[LLMMessage, ...],
        *,
        tools: tuple[LLMToolDefinition, ...] = (),
        response_format: LLMResponseFormat = LLMResponseFormat.TEXT,
    ) -> LLMResult:
        """返回只声明 Portfolio Snapshot 的固定 Structured Answer。"""

        self.calls.append(messages)
        message = LLMMessage(
            LLMRole.ASSISTANT,
            json.dumps(
                {
                    "answer": "固定回答。",
                    "source_refs": [{"type": "PORTFOLIO_SNAPSHOT"}],
                },
                ensure_ascii=False,
            ),
        )
        metadata = (
            LLMResponseMetadata("FIXED", "fixed-model", 1.0, self.usage)
            if self.usage is not None
            else None
        )
        return LLMResult.success(
            message,
            metadata,
        )


@dataclass(slots=True)
class FailingLLM:
    """返回固定 Provider Failure。"""

    def complete(
        self,
        messages: tuple[LLMMessage, ...],
        *,
        tools: tuple[LLMToolDefinition, ...] = (),
        response_format: LLMResponseFormat = LLMResponseFormat.TEXT,
    ) -> LLMResult:
        """返回不含 Provider Payload 的安全失败。"""

        return LLMResult.failure(LLMStatus.PROVIDER_UNAVAILABLE, "固定 Provider Failure")


@dataclass(slots=True)
class QuoteCallingLLM:
    """先请求固定 Quote，再返回声明该来源的合法 Answer。"""

    completion_count: int = 0

    def complete(
        self,
        messages: tuple[LLMMessage, ...],
        *,
        tools: tuple[LLMToolDefinition, ...] = (),
        response_format: LLMResponseFormat = LLMResponseFormat.TEXT,
    ) -> LLMResult:
        """按生产 Agent 的两次 Completion Contract 返回结果。"""

        self.completion_count += 1
        if self.completion_count == 1:
            return LLMResult.success(
                LLMMessage(
                    LLMRole.ASSISTANT,
                    None,
                    tool_calls=(
                        LLMToolCall(
                            "quote-1",
                            "get_current_quote",
                            {
                                "ticker": "GOOG",
                                "request_purpose": "INFORMATION_RETRIEVAL",
                            },
                        ),
                    ),
                )
            )
        return LLMResult.success(
            LLMMessage(
                LLMRole.ASSISTANT,
                json.dumps(
                    {
                        "answer": "固定报价是 210.25 美元。",
                        "source_refs": [
                            {"type": "PORTFOLIO_SNAPSHOT"},
                            {"type": "CURRENT_QUOTE", "ticker": "GOOG"},
                        ],
                    },
                    ensure_ascii=False,
                ),
            )
        )


def test_manifest_freezes_twenty_parents_and_twenty_one_variants() -> None:
    """AQ17 的两个必要变体不能被错误计成两个父场景。"""

    manifest = manifest_payload()

    assert manifest["parent_case_count"] == 20
    assert manifest["execution_variant_count"] == 21
    assert len(CASES_BY_ID) == 21
    assert case_manifest(CASES_BY_ID["AQ01"])["related_failure"] == (
        "USER_REPORTED_GOOG_DROP_CAUSALITY"
    )
    assert case_manifest(CASES_BY_ID["AQ05"])["related_failure"] == (
        "USER_REPORTED_CURRENT_TURN_BUDGET_IGNORED"
    )


def test_scope_and_capability_gap_are_independent() -> None:
    """FULL 不得伪造能力缺口，DIAGNOSTIC 必须说明缺失能力。"""

    for case in CASES:
        if case.scope is ScenarioExecutionScope.FULL:
            assert case.capability_gaps == ()
        else:
            assert case.capability_gaps


def test_repeat_and_holdout_sets_are_frozen() -> None:
    """关键重复与 Holdout 分组必须在真实结果出现前固定。"""

    assert REPEAT_CASE_IDS == ("AQ03", "AQ05", "AQ07", "AQ17a", "AQ17b")
    assert HOLDOUT_CASE_IDS == ("AQ04", "AQ12", "AQ18", "AQ19")
    assert all(
        CASES_BY_ID[case_id].scope is ScenarioExecutionScope.FULL for case_id in REPEAT_CASE_IDS
    )


def test_controlled_contrasts_only_change_declared_input() -> None:
    """两组对照的 Domain 与无关 Provider Fixture 必须保持一致。"""

    assert tuple(contrast.id for contrast in CONTROLLED_CONTRASTS) == (
        "budget-only",
        "news-empty-vs-failure",
    )
    budget_500 = case_manifest(CASES_BY_ID["AQ05"])
    budget_200 = case_manifest(CASES_BY_ID["AQ06"])
    assert budget_500["domain_fixture"] == budget_200["domain_fixture"]
    assert budget_500["provider_fixtures"] == budget_200["provider_fixtures"]
    budget_500_questions = cast(tuple[str, ...], budget_500["executable_questions"])
    budget_200_questions = cast(tuple[str, ...], budget_200["executable_questions"])
    assert budget_500_questions[0].replace("500", "200") == budget_200_questions[0]

    news_empty = case_manifest(CASES_BY_ID["AQ17a"])
    news_failure = case_manifest(CASES_BY_ID["AQ17b"])
    assert news_empty["domain_fixture"] == news_failure["domain_fixture"]
    assert news_empty["executable_questions"] == news_failure["executable_questions"]
    news_empty_providers = cast(dict[str, object], news_empty["provider_fixtures"])
    news_failure_providers = cast(dict[str, object], news_failure["provider_fixtures"])
    assert news_empty_providers["market_context"] == news_failure_providers["market_context"]
    news_empty_results = cast(dict[str, dict[str, object]], news_empty_providers["news"])
    news_failure_results = cast(dict[str, dict[str, object]], news_failure_providers["news"])
    assert news_empty_results["GOOG"]["status"] == "NO_NEWS_FOUND"
    assert news_failure_results["GOOG"]["status"] == "PROVIDER_UNAVAILABLE"


def test_strategy_mutation_steps_are_not_injected_into_ask_runtime() -> None:
    """AQ15 只提交后续问题，不把缺失 Mutation 接口伪装成 Ask 能力。"""

    case = CASES_BY_ID["AQ15"]

    assert len(case.target_messages) == 3
    assert case.executable_questions == ("现在分析 GOOG 时还会用旧计划吗？",)
    assert case.scope is ScenarioExecutionScope.DIAGNOSTIC
    manifest = case_manifest(case)
    unavailable_steps = cast(list[dict[str, str]], manifest["unavailable_target_steps"])
    assert [step["message"] for step in unavailable_steps] == [
        "删除我之前的 GOOG 分批计划。",
        "确认删除。",
    ]


def test_manifest_hash_input_contains_complete_provider_fixture_data() -> None:
    """Fixture 摘要输入必须覆盖报价、新闻正文和失败消息，而不只是状态。"""

    quote_manifest = case_manifest(CASES_BY_ID["AQ03"])
    quote_providers = cast(dict[str, object], quote_manifest["provider_fixtures"])
    quote_results = cast(dict[str, dict[str, object]], quote_providers["quote"])
    quote_data = cast(dict[str, object], quote_results["GOOG"]["data"])
    assert quote_data["last_price"] == Decimal("210.25000000")

    budget_manifest = case_manifest(CASES_BY_ID["AQ05"])
    domain_fixture = cast(dict[str, object], budget_manifest["domain_fixture"])
    transactions = cast(list[dict[str, object]], domain_fixture["transactions"])
    assert [transaction["id"] for transaction in transactions] == [
        UUID(int=1),
        UUID(int=2),
        UUID(int=3),
    ]

    news_manifest = case_manifest(CASES_BY_ID["AQ18"])
    news_providers = cast(dict[str, object], news_manifest["provider_fixtures"])
    news_results = cast(dict[str, dict[str, object]], news_providers["news"])
    news_data = cast(dict[str, object], news_results["GOOG"]["data"])
    articles = cast(tuple[dict[str, object], ...], news_data["articles"])
    assert articles[0]["headline"] == "Alphabet says the service remains available"

    failure_manifest = case_manifest(CASES_BY_ID["AQ17b"])
    failure_providers = cast(dict[str, object], failure_manifest["provider_fixtures"])
    failure_results = cast(dict[str, dict[str, object]], failure_providers["news"])
    assert failure_results["GOOG"]["message"] == "固定 News Provider Failure"


def test_selected_cases_defaults_to_all_and_validates_explicit_subset() -> None:
    """正式全量与关键重复运行使用同一稳定 Case 选择器。"""

    assert selected_cases({}) == CASES
    assert tuple(case.id for case in selected_cases({"ASK_QUALITY_CASE_IDS": "AQ03,AQ17b"})) == (
        "AQ03",
        "AQ17b",
    )
    with pytest.raises(ValueError, match="未知 Case"):
        selected_cases({"ASK_QUALITY_CASE_IDS": "AQ99"})
    with pytest.raises(ValueError, match="重复 Case"):
        selected_cases({"ASK_QUALITY_CASE_IDS": "AQ03,AQ03"})


def test_metadata_records_versions_hashes_and_unknown_git(tmp_path: Path) -> None:
    """运行元数据必须保留版本和三类摘要，Git 不可用时明确 UNKNOWN。"""

    metadata = create_run_metadata(
        environment={
            "EVAL_RUN_ID": "fixed-run",
            "EVAL_REPETITION_INDEX": "2",
            "LLM_MODEL": "fixed-model",
            "LLM_PROVIDER": "openai",
            "LLM_BASE_URL": "https://user:secret@example.test/compatible/v1?token=hidden",
            "LLM_REQUEST_TIMEOUT_SECONDS": "45",
        },
        repository_root=tmp_path,
    )

    assert metadata.run_id == "fixed-run"
    assert metadata.repetition_index == 2
    assert metadata.model == "fixed-model"
    assert metadata.provider == "OPENAI"
    assert metadata.production_revision == PRODUCTION_BEHAVIOR_REVISION
    assert metadata.harness_revision == "UNKNOWN"
    assert metadata.llm_base_url == "https://example.test/compatible/v1"
    assert metadata.request_timeout_seconds == "45"
    assert len(metadata.prompt_sha256) == 64
    assert len(metadata.tool_contract_sha256) == 64
    assert len(metadata.fixture_manifest_sha256) == 64


@pytest.mark.parametrize("value", ["0", "-1", "bad"])
def test_metadata_rejects_invalid_repetition(value: str) -> None:
    """错误 repetition 必须作为 Harness 配置失败暴露。"""

    with pytest.raises(ValueError, match="必须是正整数"):
        create_run_metadata(environment={"EVAL_REPETITION_INDEX": value})


def test_multi_turn_diagnostic_submits_each_question_without_history_injection() -> None:
    """多轮诊断必须逐轮走当前单问题入口，不能拼接前文。"""

    llm = RecordingLLM()
    record = execute_case(CASES_BY_ID["AQ09"], llm, LLMResponseFormat.TEXT)

    assert record["execution_status"] == ExecutionStatus.COMPLETED.value
    turns = cast(list[dict[str, object]], record["turns"])
    assert len(turns) == 2
    assert len(llm.calls) == 2
    first_content = llm.calls[0][-1].content
    second_content = llm.calls[1][-1].content
    assert first_content is not None
    assert second_content is not None
    assert CASES_BY_ID["AQ09"].executable_questions[0] in first_content
    assert CASES_BY_ID["AQ09"].executable_questions[1] in second_content
    assert CASES_BY_ID["AQ09"].executable_questions[0] not in second_content


def test_request_failure_does_not_change_frozen_scope() -> None:
    """Provider Failure 改变 execution status，但不能把 FULL 改成 DIAGNOSTIC。"""

    record = execute_case(CASES_BY_ID["AQ20"], FailingLLM(), LLMResponseFormat.TEXT)

    assert record["scenario_execution_scope"] == ScenarioExecutionScope.FULL.value
    assert record["execution_status"] == ExecutionStatus.REQUEST_FAILED.value
    gate = cast(dict[str, object], record["critical_failure_gate"])
    assert gate["status"] == "NOT_EVALUATED"


def test_execution_records_fixed_tool_result_and_declared_source() -> None:
    """真实 Agent Tool 路径必须把固定 Result 与最终来源写入 Record。"""

    record = execute_case(CASES_BY_ID["AQ03"], QuoteCallingLLM(), LLMResponseFormat.TEXT)

    turns = cast(list[dict[str, object]], record["turns"])
    assert len(turns) == 1
    turn = turns[0]
    assert turn["execution_status"] == ExecutionStatus.COMPLETED.value
    assert turn["tool_call_count"] == 1
    assert record["tool_call_count"] == 1
    assert isinstance(record["total_latency_ms"], float)
    tool_trace = cast(dict[str, object], turn["tool_trace"])
    attempts = cast(list[dict[str, object]], tool_trace["tool_attempts"])
    assert attempts == [{"name": "get_current_quote", "ticker": "GOOG", "status": "OK"}]
    sources = cast(list[dict[str, object]], turn["sources"])
    assert {source["type"] for source in sources} == {"PORTFOLIO_SNAPSHOT", "CURRENT_QUOTE"}


def test_execution_aggregates_provider_usage_without_guessing_missing_values() -> None:
    """每次 Completion 都有 Usage 时才写入 Case 汇总。"""

    record = execute_case(
        CASES_BY_ID["AQ20"],
        RecordingLLM(usage=LLMUsage(11, 7, 18)),
        LLMResponseFormat.TEXT,
    )

    assert record["usage"] == {
        "input_tokens": 11,
        "output_tokens": 7,
        "total_tokens": 18,
    }


def test_summary_keeps_coverage_reliability_quality_and_gate_separate(tmp_path: Path) -> None:
    """NOT_RUN 与待人工评分不得制造成功率或零 Critical Failure。"""

    metadata = create_run_metadata(
        environment={"EVAL_RUN_ID": "summary-run"},
        repository_root=tmp_path,
    )
    records = [
        not_run_record(CASES_BY_ID["AQ03"], "CREDENTIAL_NOT_AVAILABLE"),
        execute_case(CASES_BY_ID["AQ20"], RecordingLLM(), LLMResponseFormat.TEXT),
    ]

    summary = build_summary(metadata, records)

    assert summary["capability_coverage"] == {
        "full_parent_case_count": 8,
        "target_parent_case_count": 20,
        "rate": 0.4,
        "full_parent_case_ids": ["AQ03", "AQ05", "AQ06", "AQ07", "AQ08", "AQ17", "AQ18", "AQ20"],
    }
    assert summary["request_reliability"] == {
        "completed": 1,
        "request_failed": 0,
        "not_run": 1,
        "success_rate": 1.0,
    }
    full_answer_quality = cast(dict[str, object], summary["full_answer_quality"])
    assert full_answer_quality["review_status"] == "PENDING"
    diagnostic_observations = cast(dict[str, object], summary["diagnostic_observations"])
    assert diagnostic_observations["target_variant_count"] == 0
    assert diagnostic_observations["review_status"] == "NOT_STARTED"
    assert summary["critical_failures"] == {
        "fail_count": 0,
        "affected_case_ids": [],
        "category_counts": {},
        "not_evaluated_count": 2,
    }
    tool_calls = cast(dict[str, object], summary["tool_calls"])
    assert tool_calls["total"] == 0


def test_summary_aggregates_explicit_human_scores_and_gate_categories(tmp_path: Path) -> None:
    """首页只汇总 Reviewer 明确写入的分数与 Critical Failure 类别。"""

    metadata = create_run_metadata(
        environment={"EVAL_RUN_ID": "reviewed-run"},
        repository_root=tmp_path,
    )
    record = execute_case(CASES_BY_ID["AQ20"], RecordingLLM(), LLMResponseFormat.TEXT)
    human_review = cast(dict[str, object], record["human_review"])
    human_review["status"] = "COMPLETED"
    dimension_reviews = cast(dict[str, dict[str, object]], human_review["dimension_reviews"])
    dimension_reviews["ANSWER_USEFULNESS"].update(
        {"status": "SCORED", "value": 2, "evidence": ["直接回答 Cash"]}
    )
    gate = cast(dict[str, object], record["critical_failure_gate"])
    gate.update({"status": "FAIL", "categories": ["GROUNDING", "CASH_FACT"]})

    summary = build_summary(metadata, [record])

    quality = cast(dict[str, object], summary["full_answer_quality"])
    assert quality["review_status"] == "COMPLETED"
    distributions = cast(dict[str, dict[str, int]], quality["dimension_distributions"])
    assert distributions["ANSWER_USEFULNESS"] == {"0": 0, "1": 0, "2": 1}
    failures = cast(dict[str, object], summary["critical_failures"])
    assert failures["category_counts"] == {"CASH_FACT": 1, "GROUNDING": 1}


def test_reporter_writes_manifest_case_records_and_summary(tmp_path: Path) -> None:
    """显式 Artifact 目录必须包含三个可复核文件。"""

    metadata = create_run_metadata(
        environment={"EVAL_RUN_ID": "artifact-run"},
        repository_root=tmp_path,
    )
    reporter = AskQualityReporter(metadata, (CASES_BY_ID["AQ03"],), tmp_path / "artifacts")
    reporter.record_not_run(CASES_BY_ID["AQ03"], "CREDENTIAL_NOT_AVAILABLE")

    summary = reporter.finalize()

    reliability = cast(dict[str, object], summary["request_reliability"])
    assert reliability["not_run"] == 1
    manifest_path = tmp_path / "artifacts" / "manifest.json"
    cases_path = tmp_path / "artifacts" / "cases.jsonl"
    assert manifest_path.is_file()
    assert cases_path.is_file()
    assert (tmp_path / "artifacts" / "summary.json").is_file()
    artifact_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert artifact_manifest["run_metadata"]["repetition_index"] == 1
    assert artifact_manifest["target_case_ids"] == ["AQ03"]
    case_record = json.loads(cases_path.read_text(encoding="utf-8"))
    assert case_record["run_metadata"]["run_id"] == "artifact-run"


@pytest.fixture(scope="session")
def ask_quality_reporter() -> Iterator[AskQualityReporter]:
    """真实模型 Session 结束时输出并可选持久化完整记录。"""

    reporter = AskQualityReporter(
        create_run_metadata(),
        selected_cases(),
        artifact_dir_from_environment(),
    )
    yield reporter
    reporter.finalize()


def _real_llm() -> OpenAICompatibleLLMProvider:
    """只从当前进程环境创建真实 Adapter，不读取 Repository `.env`。"""

    provider_name = os.getenv("LLM_PROVIDER", ALIYUN_MODEL_STUDIO).strip().upper()
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL", DEFAULT_LLM_BASE_URL)
    model = os.getenv("LLM_MODEL", DEFAULT_EVALUATION_MODEL)
    timeout_seconds = float(
        os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", DEFAULT_LLM_TIMEOUT_SECONDS)
    )
    if provider_name == ALIYUN_MODEL_STUDIO:
        return AliyunLLMProvider(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_seconds=timeout_seconds,
        )
    return OpenAICompatibleLLMProvider(
        provider_name=provider_name,
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
    )


@pytest.mark.online
@pytest.mark.behavioral
@pytest.mark.skipif(
    os.getenv(REAL_EVAL_ENV) != "1",
    reason="需要显式启用 Ask Quality 真实模型评测",
)
@pytest.mark.parametrize("case", selected_cases(), ids=lambda case: case.id)
def test_real_model_ask_quality_baseline(
    case: AskQualityCase,
    ask_quality_reporter: AskQualityReporter,
) -> None:
    """执行当前产品路径并记录证据，不用质量波动中止整个 Baseline。"""

    if not os.getenv("LLM_API_KEY"):
        ask_quality_reporter.record_not_run(case, "LLM_API_KEY_NOT_SET")
        pytest.skip("LLM_API_KEY 未配置")
    routing_format = LLMResponseFormat(ask_quality_reporter.metadata.routing_response_format)
    ask_quality_reporter.record(execute_case(case, _real_llm(), routing_format))
