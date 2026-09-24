"""测试专用 Final Output Tool 与 JSON 文本配对能力实验。"""

import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic
from typing import Literal
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict
from pydantic_ai import Agent, ToolOutput, UsageLimits
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    ToolCallPart,
)
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.providers.alibaba import AlibabaProvider
from pydantic_ai.settings import ModelSettings

from position_pilot.application.conversation_citations import (
    CitationValidationError,
    validate_citations,
)
from position_pilot.application.source_registry import (
    ContextSource,
    ContextSourceType,
    SourceValidator,
)

SOURCE_ID = UUID("c8e73e7b-bb75-4b41-b257-9cbad2a70607")
SOURCE = ContextSource(ContextSourceType.CURRENT_QUOTE, "OK", ticker="GOOG", source_id=SOURCE_ID)
WALL_CLOCK_SECONDS = 30.0
PROMPT = (
    "请先调用 get_fixture_quote 查询 GOOG，再用一句中文回答该固定报价，并在回答中写入 "
    f"[source:{SOURCE_ID}]。不得使用其他报价。"
)


class _SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["CURRENT_QUOTE"]
    ticker: Literal["GOOG"]


class _FinalAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str
    source_refs: list[_SourceRef]


@dataclass
class _Trace:
    requests: list[dict[str, object]] = field(default_factory=list)
    tools: list[dict[str, object]] = field(default_factory=list)


class _TimedModel(WrapperModel):
    """仅在实验中记录真实模型请求耗时和响应类型。"""

    def __init__(self, wrapped: Model, trace: _Trace):
        super().__init__(wrapped)
        self.trace = trace

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        started = monotonic()
        framework_retry = any(
            isinstance(part, RetryPromptPart)
            for message in messages[-1:]
            if isinstance(message, ModelRequest)
            for part in message.parts
        )
        try:
            response = await self.wrapped.request(
                messages, model_settings, model_request_parameters
            )
        except asyncio.CancelledError:
            self.trace.requests.append(
                {
                    "latency_ms": _ms(started),
                    "status": "CANCELLED_BY_WALL_CLOCK",
                    "framework_retry": framework_retry,
                    "usage": "UNKNOWN",
                }
            )
            raise
        except Exception as error:
            self.trace.requests.append(
                {
                    "latency_ms": _ms(started),
                    "status": "ERROR",
                    "error_type": type(error).__name__,
                    "framework_retry": framework_retry,
                    "usage": "UNKNOWN",
                }
            )
            raise
        usage = response.usage
        self.trace.requests.append(
            {
                "latency_ms": _ms(started),
                "status": "COMPLETED",
                "framework_retry": framework_retry,
                "part_types": [type(part).__name__ for part in response.parts],
                "output_tool_called": any(
                    isinstance(part, ToolCallPart) and part.tool_name == "final_investment_answer"
                    for part in response.parts
                ),
                "usage": _usage(usage.input_tokens, usage.output_tokens),
            }
        )
        return response


def _ms(started: float) -> float:
    return round((monotonic() - started) * 1000, 2)


def _usage(input_tokens: int, output_tokens: int) -> dict[str, int] | str:
    if input_tokens == 0 and output_tokens == 0:
        return "UNKNOWN"
    return {"input_tokens": input_tokens, "output_tokens": output_tokens}


def _validate(content: str, *, quote_observed: bool) -> tuple[bool, str | None]:
    sources = (SOURCE,) if quote_observed else ()
    answer, error = SourceValidator.evaluate(content, sources)
    if error is not None or answer is None:
        return False, type(error).__name__ if error is not None else "INVALID_ANSWER"
    try:
        validate_citations(answer.answer, sources)
    except CitationValidationError:
        return False, "CitationValidationError"
    if not quote_observed or answer.source_refs != (SOURCE.as_reference(),):
        return False, "MISSING_QUOTE_SOURCE_REF"
    return True, None


async def _run_arm(mode: str, *, api_key: str, base_url: str, model_name: str) -> dict[str, object]:
    trace = _Trace()
    started = monotonic()
    client = AsyncOpenAI(
        api_key=api_key, base_url=base_url, timeout=WALL_CLOCK_SECONDS, max_retries=0
    )
    try:
        model = _TimedModel(
            OpenAIChatModel(model_name, provider=AlibabaProvider(openai_client=client)), trace
        )

        def get_fixture_quote(ticker: str) -> str:
            """读取固定 GOOG 报价；这是实验 Fixture，不是实时价格。"""

            tool_started = monotonic()
            observation = json.dumps(
                {
                    "status": "OK",
                    "ticker": "GOOG",
                    "price": "320.00",
                    "currency": "USD",
                    "source_id": str(SOURCE_ID),
                    "fixture": True,
                }
            )
            trace.tools.append(
                {"name": "get_fixture_quote", "ticker": ticker, "latency_ms": _ms(tool_started)}
            )
            return observation

        output_type = (
            str
            if mode == "JSON_TEXT"
            else ToolOutput(_FinalAnswer, name="final_investment_answer", max_retries=0)
        )
        agent = Agent(
            model,
            output_type=output_type,
            instructions=(
                "仅用工具观察到的事实回答。最终输出必须包含 answer 字符串和 "
                "source_refs 数组，引用 CURRENT_QUOTE / GOOG。"
                + ("请直接输出合法 JSON object 文本。" if mode == "JSON_TEXT" else "")
            ),
            tools=[get_fixture_quote],
            retries=0,
        )
        record: dict[str, object] = {"mode": mode, "repair_triggered": False}
        try:
            result = await asyncio.wait_for(
                agent.run(
                    PROMPT,
                    model_settings={"timeout": WALL_CLOCK_SECONDS},
                    usage_limits=UsageLimits(request_limit=3, tool_calls_limit=1),
                ),
                timeout=WALL_CLOCK_SECONDS,
            )
            if not isinstance(result.output, (str, _FinalAnswer)):
                raise TypeError("实验输出类型不符合预期")
            content = (
                result.output if isinstance(result.output, str) else result.output.model_dump_json()
            )
            quote_observed = any(
                item["name"] == "get_fixture_quote" and item["ticker"] == "GOOG"
                for item in trace.tools
            )
            valid, reason = _validate(content, quote_observed=quote_observed)
            record.update(
                first_output_valid=valid,
                first_output_error=reason,
                first_output_ms=_ms(started),
                first_candidate=content,
            )
            if not valid and (remaining := WALL_CLOCK_SECONDS - (monotonic() - started)) > 0:
                record["repair_triggered"] = True
                repair_started = monotonic()
                repair_agent = Agent(
                    model,
                    output_type=output_type,
                    instructions="修正先前输出的格式或引用；不得调用工具。",
                    retries=0,
                )
                try:
                    repaired = await asyncio.wait_for(
                        repair_agent.run(
                            f"先前候选：{content}\n校验失败：{reason}。"
                            + (
                                "请修正并保留已观察 GOOG 报价的引用。"
                                if quote_observed
                                else "报价工具未被调用；不得编造报价或来源。"
                            ),
                            model_settings={"timeout": remaining},
                            usage_limits=UsageLimits(request_limit=1, tool_calls_limit=0),
                        ),
                        timeout=remaining,
                    )
                    if not isinstance(repaired.output, (str, _FinalAnswer)):
                        raise TypeError("Repair 输出类型不符合预期")
                    repaired_content = (
                        repaired.output
                        if isinstance(repaired.output, str)
                        else repaired.output.model_dump_json()
                    )
                    record["repair_output_valid"], record["repair_output_error"] = _validate(
                        repaired_content, quote_observed=quote_observed
                    )
                    record["repair_candidate"] = repaired_content
                except Exception as error:
                    record["repair_error_type"] = type(error).__name__
                    record["repair_output_valid"] = False
                record["repair_ms"] = _ms(repair_started)
        except Exception as error:
            record.update(
                first_output_valid=False,
                first_output_error=type(error).__name__,
                first_output_ms=_ms(started),
            )
        record["request_count"] = len(trace.requests)
        record["requests"] = trace.requests
        record["framework_output_retry_count"] = sum(
            bool(item["framework_retry"]) for item in trace.requests
        )
        record["tools"] = trace.tools
        record["total_ms"] = _ms(started)
        record["final_valid"] = bool(
            record.get("first_output_valid") or record.get("repair_output_valid")
        )
        record["usage"] = _aggregate_usage(trace.requests)
        record["cost"] = "UNKNOWN"
        return record
    finally:
        await client.close()


def _aggregate_usage(requests: list[dict[str, object]]) -> dict[str, int] | str:
    usages = [item["usage"] for item in requests if "usage" in item]
    if not usages or any(value == "UNKNOWN" for value in usages):
        return "UNKNOWN"
    measured = [value for value in usages if isinstance(value, dict)]
    return {
        "input_tokens": sum(int(value["input_tokens"]) for value in measured),
        "output_tokens": sum(int(value["output_tokens"]) for value in measured),
    }


def run_spike(environment: Mapping[str, str]) -> dict[str, object]:
    """运行两个独立 30 秒配对实验，并将原始候选写入新的 Artifact。"""

    artifact_dir = Path(environment["FINAL_OUTPUT_ARTIFACT_DIR"])
    artifact_dir.mkdir(parents=True, exist_ok=False)

    async def run_pair() -> list[dict[str, object]]:
        return [
            await _run_arm(
                mode,
                api_key=environment["LLM_API_KEY"],
                base_url=environment["LLM_BASE_URL"],
                model_name=environment["LLM_MODEL"],
            )
            for mode in ("JSON_TEXT", "FINAL_OUTPUT_TOOL")
        ]

    arms = asyncio.run(run_pair())
    report: dict[str, object] = {
        "model": environment["LLM_MODEL"],
        "provider": "ALIYUN_MODEL_STUDIO",
        "endpoint": _safe_endpoint(environment["LLM_BASE_URL"]),
        "scenario": "FIXTURE_QUOTE_THEN_FINAL",
        "production_changed": False,
        "arms": arms,
    }
    (artifact_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8"
    )
    return report


def _safe_endpoint(base_url: str) -> str:
    """Artifact 只保留复现 Region 所需 Endpoint，移除凭证与查询参数。"""

    parsed = urlsplit(base_url)
    hostname = parsed.hostname or ""
    return urlunsplit((parsed.scheme, hostname, parsed.path, "", ""))
