"""Gemini 官方原生 API 的固定 A/B 探针，不接入 Production 或 Search。"""

import asyncio
import json
from dataclasses import dataclass, field
from time import monotonic

import httpx
from google.genai import Client
from google.genai.types import HttpOptions, HttpRetryOptions
from phase4_final_output_spike import PROMPT, SOURCE_ID, _aggregate_usage, _ms, _Trace
from phase4_output_mechanism_spike import (
    NO_TOOL_PROMPT,
    _CandidateTraceModel,
    _failure_classification,
    _provider_error,
)
from phase4_output_mechanism_spike import (
    WALL_CLOCK_SECONDS as WALL_CLOCK_SECONDS,
)
from pydantic_ai import Agent, NativeOutput, UsageLimits
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from position_pilot.integrations.pydantic_ai_runtime import _NativeStructuredFinalCandidate

GOOGLE_ENDPOINT = "https://generativelanguage.googleapis.com"
GOOGLE_MODEL = "gemini-3.8-flash"
FIXTURE = {"status": "OK", "ticker": "GOOG", "price": "320.00", "source_id": str(SOURCE_ID)}


@dataclass
class _GoogleCapture:
    """只保留机制字段；不记录 API Key、请求 Header 或完整上下文。"""

    requests: list[dict[str, object]] = field(default_factory=list)

    async def on_request(self, request: httpx.Request) -> None:
        payload = json.loads(request.content)
        config = payload.get("generationConfig", {})
        names = [
            declaration["name"]
            for tool in payload.get("tools", [])
            for declaration in tool.get("functionDeclarations", [])
        ]
        calls: set[str] = set()
        returned = False
        for content in payload.get("contents", []):
            for part in content.get("parts", []):
                call = part.get("functionCall", {})
                if call.get("name") == "get_fixture_quote" and call.get("args") == {
                    "ticker": "GOOG"
                }:
                    calls.add(call.get("id", "get_fixture_quote"))
                response = part.get("functionResponse", {})
                if (
                    response.get("name") == "get_fixture_quote"
                    and response.get("id", "get_fixture_quote") in calls
                ):
                    returned = response.get("response") == FIXTURE
        self.requests.append(
            {
                "response_mime_type": config.get("responseMimeType"),
                "response_json_schema": config.get("responseJsonSchema"),
                "tool_names": names,
                "thinking_config": config.get("thinkingConfig", "OMITTED"),
                "fixture_result_in_context": returned,
                "http_status": None,
            }
        )

    async def on_response(self, response: httpx.Response) -> None:
        self.requests[-1]["http_status"] = response.status_code


def _contract(requests: list[dict[str, object]], *, with_quote: bool) -> bool:
    if not requests:
        return False
    return all(
        item["response_mime_type"] == "application/json"
        and isinstance(item["response_json_schema"], dict)
        and bool(item["response_json_schema"])
        and item["response_json_schema"] == requests[0]["response_json_schema"]
        and item["tool_names"] == (["get_fixture_quote"] if with_quote else [])
        for item in requests
    )


async def run_google_arm(
    *,
    api_key: str,
    model_name: str,
    with_quote: bool,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, object]:
    """最多一次 A 或两次 B 请求；SDK 不重试，工具执行由 PydanticAI 持有。"""

    if model_name != GOOGLE_MODEL:
        raise ValueError(f"本轮 Gemini 只允许 {GOOGLE_MODEL}")
    capture = _GoogleCapture()
    trace = _Trace()
    started = monotonic()
    record: dict[str, object] = {
        "provider": "GOOGLE_GEMINI",
        "model": model_name,
        "endpoint_family": "GEMINI_GENERATE_CONTENT",
        "stage": "B" if with_quote else "A",
        "mode": "NATIVE",
        "with_quote": with_quote,
        "thinking_mode": "PROVIDER_DEFAULT",
        "behavioral_status": "NOT_EVALUATED",
        "application_repair_count": 0,
        "sdk_retry_count": 0,
        "pydantic_schema_valid": "NOT_PRODUCED",
        "position_pilot_validation_valid": "NOT_RUN",
        "final_output_tool_called": False,
    }
    async with httpx.AsyncClient(
        timeout=WALL_CLOCK_SECONDS,
        transport=transport,
        trust_env=False,
        event_hooks={"request": [capture.on_request], "response": [capture.on_response]},
    ) as http_client:
        client = Client(
            vertexai=False,
            api_key=api_key,
            http_options=HttpOptions(
                base_url=GOOGLE_ENDPOINT,
                timeout=int(WALL_CLOCK_SECONDS * 1000),
                retry_options=HttpRetryOptions(attempts=1),
                httpx_async_client=http_client,
            ),
        )
        try:
            model = _CandidateTraceModel(
                GoogleModel(model_name, provider=GoogleProvider(client=client)),
                trace,
            )

            def get_fixture_quote(ticker: str) -> dict[str, str]:
                """返回与其他探针相同的固定报价，参数错误不能成为 PASS。"""
                trace.tools.append({"name": "get_fixture_quote", "ticker": ticker})
                return {**FIXTURE, "ticker": ticker}

            agent = Agent(
                model,
                output_type=NativeOutput(
                    _NativeStructuredFinalCandidate,
                    name="final_investment_answer",
                    strict=True,
                ),
                instructions="仅用已观察的事实回答；source_refs 只声明成功取得的来源。",
                tools=[get_fixture_quote] if with_quote else [],
                retries=0,
                end_strategy="exhaustive",
            )
            try:
                result = await asyncio.wait_for(
                    agent.run(
                        PROMPT if with_quote else NO_TOOL_PROMPT,
                        model_settings={"timeout": WALL_CLOCK_SECONDS},
                        usage_limits=UsageLimits(request_limit=2 if with_quote else 1),
                    ),
                    timeout=WALL_CLOCK_SECONDS,
                )
                record.update(
                    pydantic_schema_valid=True, first_candidate=result.output.model_dump_json()
                )
            except Exception as error:
                record.update(
                    failure_type=(
                        "TimeoutError"
                        if isinstance(error, httpx.TimeoutException)
                        else type(error).__name__
                    ),
                    failure_message=str(error)[:400],
                    failure_cause=str(error.__cause__)[:400] if error.__cause__ else None,
                    provider_error=_provider_error(error),
                )
        finally:
            await client.aio.aclose()
            client.close()
    record.update(
        requests=capture.requests,
        model_requests=trace.requests,
        business_tools=trace.tools,
        quote_tool_called=bool(trace.tools),
        request_contract_valid=_contract(capture.requests, with_quote=with_quote),
        tool_result_entered_context=any(
            r["fixture_result_in_context"] for r in capture.requests[1:]
        ),
        framework_retry_count=sum(bool(r["framework_retry"]) for r in trace.requests),
        latency_ms=_ms(started),
        usage=_aggregate_usage(trace.requests),
    )
    record["passed"] = bool(
        record["pydantic_schema_valid"] is True
        and record["request_contract_valid"]
        and record["framework_retry_count"] == 0
        and (
            not with_quote
            or (
                len(trace.tools) == 1
                and record["tool_result_entered_context"]
                and all(t["ticker"] == "GOOG" for t in trace.tools)
            )
        )
    )
    record["status"] = "PASS" if record["passed"] else "FAIL"
    record["failure_domain"], record["failure_reason"] = _failure_classification(record)
    return record
