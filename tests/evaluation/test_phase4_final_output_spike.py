"""Final Output Tool 独立实验的离线 Contract 测试。"""

import asyncio
import json
from collections.abc import Callable

from phase4_final_output_spike import (
    SOURCE_ID,
    _aggregate_usage,
    _FinalAnswer,
    _safe_endpoint,
    _TimedModel,
    _Trace,
    _validate,
)
from pydantic_ai import Agent, ToolOutput, UsageLimits
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RequestUsage


def _scripted(
    responses: list[ModelResponse],
) -> Callable[[list[ModelMessage], AgentInfo], ModelResponse]:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        """返回本地脚本响应，不请求网络。"""

        del messages, info
        return responses.pop(0)

    return respond


def _final_args() -> dict[str, object]:
    return {
        "answer": f"固定报价为 320 美元 [source:{SOURCE_ID}]。",
        "source_refs": [{"type": "CURRENT_QUOTE", "ticker": "GOOG"}],
    }


def test_final_output_tool_after_quote_is_structured_and_counted() -> None:
    """金融工具后输出工具完成，后者不耗普通 Tool Call Budget。"""

    trace = _Trace()
    model = _TimedModel(
        FunctionModel(
            _scripted(
                [
                    ModelResponse(
                        parts=(ToolCallPart("get_fixture_quote", {"ticker": "GOOG"}, "quote"),),
                        usage=RequestUsage(input_tokens=5, output_tokens=3),
                    ),
                    ModelResponse(
                        parts=(ToolCallPart("final_investment_answer", _final_args(), "final"),),
                        usage=RequestUsage(input_tokens=6, output_tokens=4),
                    ),
                ]
            ),
            model_name="scripted",
        ),
        trace,
    )
    called: list[str] = []

    def get_fixture_quote(ticker: str) -> str:
        """返回离线固定报价。"""

        called.append(ticker)
        return json.dumps({"status": "OK", "price": "320", "source_id": str(SOURCE_ID)})

    agent = Agent(
        model,
        output_type=ToolOutput(_FinalAnswer, name="final_investment_answer", max_retries=0),
        tools=[get_fixture_quote],
        retries=0,
    )
    result = asyncio.run(
        agent.run("先查 GOOG 再回答", usage_limits=UsageLimits(request_limit=3, tool_calls_limit=1))
    )

    assert called == ["GOOG"]
    assert _validate(result.output.model_dump_json(), quote_observed=True) == (True, None)
    assert len(trace.requests) == 2
    assert trace.requests[1]["output_tool_called"] is True
    assert _aggregate_usage(trace.requests) == {"input_tokens": 11, "output_tokens": 7}


def test_json_text_with_embedded_quotes_fails_application_contract() -> None:
    """外层 JSON 文本中的未转义引号由 Application 明确拒绝。"""

    invalid = (
        '{"answer":"模型称“是否值得加仓”中的 "值得" 必须重新判断 '
        f'[source:{SOURCE_ID}]","source_refs":[{{"type":"CURRENT_QUOTE","ticker":"GOOG"}}]}}'
    )
    valid, reason = _validate(invalid, quote_observed=True)
    assert valid is False
    assert reason == "InvalidStructuredAnswer"


def test_unobserved_source_is_not_accepted_even_with_valid_schema() -> None:
    """结构化输出不能绕过 Application 的本轮 Source 身份边界。"""

    content = _FinalAnswer.model_validate(_final_args()).model_dump_json()
    assert _validate(content, quote_observed=False)[0] is False
    assert _validate(content, quote_observed=True) == (True, None)


def test_json_text_baseline_is_valid_when_well_formed() -> None:
    """对照臂不是人为固定失败：合法 JSON 文本同样可以通过。"""

    response = ModelResponse(parts=(TextPart(json.dumps(_final_args())),))
    agent = Agent(FunctionModel(_scripted([response]), model_name="scripted"), output_type=str)
    result = asyncio.run(agent.run("输出固定报价"))
    assert _validate(result.output, quote_observed=True) == (True, None)


def test_failed_request_keeps_aggregate_usage_unknown() -> None:
    """一次失败请求缺少 Usage 时，不把其余 Token 误当整臂总量。"""

    assert (
        _aggregate_usage(
            [
                {"usage": {"input_tokens": 10, "output_tokens": 5}},
                {"status": "ERROR", "usage": "UNKNOWN"},
            ]
        )
        == "UNKNOWN"
    )


def test_artifact_endpoint_omits_userinfo_and_query() -> None:
    """实验 Artifact 不保留 URL 内潜在的密钥或临时查询参数。"""

    assert (
        _safe_endpoint("https://user:secret@example.com/compatible-mode/v1?token=secret")
        == "https://example.com/compatible-mode/v1"
    )
