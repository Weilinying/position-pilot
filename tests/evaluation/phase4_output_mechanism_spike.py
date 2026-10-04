"""独立验证指定模型的原生严格输出与正常工具调用兼容性。"""

import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic
from typing import Literal

import httpx2
from openai import AsyncOpenAI
from phase4_final_output_spike import (
    PROMPT,
    SOURCE_ID,
    _aggregate_usage,
    _ms,
    _safe_endpoint,
    _TimedModel,
    _Trace,
    _validate,
)
from phase4_provider_support import classify_failure, native_profile, probe_provider
from pydantic_ai import Agent, NativeOutput, ToolOutput, UsageLimits
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers import Provider
from pydantic_ai.settings import ModelSettings

from position_pilot.application.conversation_citations import (
    CitationValidationError,
    validate_citations,
)
from position_pilot.application.source_registry import SourceValidator
from position_pilot.integrations.pydantic_ai_runtime import (
    _NativeStructuredFinalCandidate as _NativeStructuredFinalCandidate,
)
from position_pilot.integrations.pydantic_ai_runtime import (
    _StructuredFinalCandidate,
)

THINKING_MODE = "PROVIDER_DEFAULT"
WALL_CLOCK_SECONDS = 30.0
NO_TOOL_PROMPT = "只输出一句中文：这是一个固定结构化输出测试。source_refs 必须为空数组。"


def _fixture_in_context(messages: list[dict[str, object]]) -> bool:
    """只接受对应 Quote 调用的完整固定结果，不能仅匹配来源子串。"""

    quote_ids = set()
    for message in messages:
        calls = message.get("tool_calls", [])
        if isinstance(calls, list):
            for call in calls:
                if call.get("function", {}).get("name") == "get_fixture_quote":
                    quote_ids.add(call["id"])
        if message.get("role") == "tool" and message.get("tool_call_id") in quote_ids:
            try:
                result = json.loads(str(message.get("content", "")))
            except json.JSONDecodeError:
                continue
            if result == {
                "status": "OK",
                "ticker": "GOOG",
                "price": "320.00",
                "source_id": str(SOURCE_ID),
            }:
                return True
    return False


@dataclass(slots=True)
class _RequestCapture:
    """只记录输出机制相关字段，避免把密钥或完整消息写进 Artifact。"""

    requests: list[dict[str, object]] = field(default_factory=list)

    async def on_request(self, request: httpx2.Request) -> None:
        payload = json.loads(request.content)
        tools = payload.get("tools", [])
        self.requests.append(
            {
                "response_format": payload.get("response_format"),
                "tool_choice": payload.get("tool_choice"),
                "tool_names": [tool["function"]["name"] for tool in tools],
                "enable_thinking": payload.get("enable_thinking", "OMITTED"),
                "reasoning_effort": payload.get("reasoning_effort", "OMITTED"),
                "fixture_result_in_context": _fixture_in_context(payload.get("messages", [])),
                "http_status": None,
            }
        )

    async def on_response(self, response: httpx2.Response) -> None:
        self.requests[-1]["http_status"] = response.status_code


class _CandidateTraceModel(_TimedModel):
    """只在固定 Fixture Spike 中保存模型返回的文本候选，便于定位框架拒绝原因。"""

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        response = await super().request(messages, model_settings, model_request_parameters)
        self.trace.requests[-1]["text_candidates"] = [
            part.content for part in response.parts if isinstance(part, TextPart)
        ]
        self.trace.requests[-1]["tool_call_candidates"] = [
            {"name": part.tool_name, "arguments": part.args_as_dict()}
            for part in response.parts
            if isinstance(part, ToolCallPart)
        ]
        return response


def _native_profile(provider: Provider[AsyncOpenAI], model_name: str) -> OpenAIModelProfile:
    """复用测试专用局部 Profile，不限制模型名称。"""

    return native_profile(provider, model_name)


def _request_contract(requests: list[dict[str, object]], *, native: bool, with_quote: bool) -> bool:
    """检查每次真实 HTTP 请求的输出模式及工具集合。"""

    if not requests:
        return False
    first_names = requests[0]["tool_names"]
    if not isinstance(first_names, list) or with_quote != ("get_fixture_quote" in first_names):
        return False
    for request in requests:
        output_format = request["response_format"]
        names = request["tool_names"]
        if not isinstance(names, list):
            return False
        if not with_quote and "get_fixture_quote" in names:
            return False
        if native:
            if "final_investment_answer" in names or not isinstance(output_format, dict):
                return False
            schema = output_format.get("json_schema")
            if output_format.get("type") != "json_schema" or not isinstance(schema, dict):
                return False
            if schema.get("strict") is not True or output_format != requests[0]["response_format"]:
                return False
        elif "final_investment_answer" not in names:
            return False
    return True


async def _run_arm(
    mode: Literal["NATIVE", "TOOL"],
    *,
    with_quote: bool,
    api_key: str,
    base_url: str,
    model_name: str,
    transport: httpx2.AsyncBaseTransport | None = None,
    provider_name: str = "ALIYUN_MODEL_STUDIO",
) -> dict[str, object]:
    """单臂独立创建 Provider Client，并保留真实请求的安全字段。"""

    capture = _RequestCapture()
    trace = _Trace()
    started = monotonic()
    http_client = httpx2.AsyncClient(
        event_hooks={"request": [capture.on_request], "response": [capture.on_response]},
        transport=transport,
    )
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=WALL_CLOCK_SECONDS,
        max_retries=0,
        http_client=http_client,
    )
    record: dict[str, object] = {
        "mode": mode,
        "actual_output_mode_expected": (
            "PROVIDER_JSON_SCHEMA" if mode == "NATIVE" else "FINAL_OUTPUT_TOOL"
        ),
        "with_quote": with_quote,
        "provider": provider_name,
        "model": model_name,
        "endpoint_family": "OPENAI_CHAT_COMPLETIONS",
        "thinking_mode": THINKING_MODE,
        "stage": "C" if mode == "TOOL" else "B" if with_quote else "A",
        "behavioral_status": "NOT_EVALUATED",
        "thinking": THINKING_MODE,
        "application_repair_count": 0,
        "pydantic_schema_valid": "NOT_PRODUCED",
        "position_pilot_validation_valid": "NOT_RUN",
    }
    try:
        provider = probe_provider(client, provider_name)
        provider_profile = OpenAIModelProfile.from_profile(provider.model_profile(model_name))
        profile = _native_profile(provider, model_name) if mode == "NATIVE" else provider_profile
        record["profile"] = {
            "supports_json_schema_output": profile.supports_json_schema_output,
            "provider_default_supports_json_schema_output": (
                provider_profile.supports_json_schema_output
            ),
            "override": mode == "NATIVE",
        }
        model = _CandidateTraceModel(
            OpenAIChatModel(model_name, provider=provider, profile=profile), trace
        )

        def get_fixture_quote(ticker: str) -> str:
            """固定只读报价，Stage B 必须证明调用真实进入了后续模型请求。"""

            trace.tools.append({"name": "get_fixture_quote", "ticker": ticker})
            return json.dumps(
                {"status": "OK", "ticker": ticker, "price": "320.00", "source_id": str(SOURCE_ID)}
            )

        try:
            output_type = (
                NativeOutput(
                    _NativeStructuredFinalCandidate, name="final_investment_answer", strict=True
                )
                if mode == "NATIVE"
                else ToolOutput(
                    _StructuredFinalCandidate, name="final_investment_answer", max_retries=0
                )
            )
            agent = Agent(
                model,
                output_type=output_type,
                instructions="仅用已观察的事实回答；source_refs 只声明成功取得的来源。",
                tools=[get_fixture_quote] if with_quote else [],
                retries=0,
                end_strategy="exhaustive",
            )
            result = await asyncio.wait_for(
                agent.run(
                    PROMPT if with_quote else NO_TOOL_PROMPT,
                    model_settings={"timeout": WALL_CLOCK_SECONDS},
                    usage_limits=UsageLimits(request_limit=3, tool_calls_limit=1),
                ),
                timeout=WALL_CLOCK_SECONDS,
            )
            content = result.output.model_dump_json()
            record["pydantic_schema_valid"] = True
            quote_observed = any(tool["name"] == "get_fixture_quote" for tool in trace.tools)
            if with_quote:
                valid, error = _validate(content, quote_observed=quote_observed)
            else:
                parsed, parse_error = SourceValidator.evaluate(content, ())
                valid = parse_error is None and parsed is not None and parsed.source_refs == ()
                error = str(parse_error) if parse_error is not None else None
                if valid and parsed is not None:
                    try:
                        validate_citations(parsed.answer, ())
                    except CitationValidationError as citation_error:
                        valid, error = False, type(citation_error).__name__
            record.update(
                first_candidate=content,
                first_candidate_valid=valid,
                validation_error=error,
                quote_tool_called=quote_observed,
                position_pilot_validation_valid=valid,
            )
        except Exception as error:
            record.update(
                first_candidate_valid=False,
                failure_type=type(error).__name__,
                failure_message=str(error)[:400],
                failure_cause=(str(error.__cause__)[:400] if error.__cause__ else None),
                provider_error=_provider_error(error),
                quote_tool_called=bool(trace.tools),
            )
        record["requests"] = capture.requests
        record["request_contract_valid"] = _request_contract(
            capture.requests, native=mode == "NATIVE", with_quote=with_quote
        )
        record["tool_result_entered_context"] = any(
            request["fixture_result_in_context"] for request in capture.requests[1:]
        )
        record["framework_retry_count"] = sum(
            bool(request["framework_retry"]) for request in trace.requests
        )
        record["first_attempt_success"] = bool(
            record["pydantic_schema_valid"] is True and record["framework_retry_count"] == 0
        )
        record["final_output_tool_called"] = any(
            bool(request.get("output_tool_called")) for request in trace.requests
        )
        record["model_requests"] = trace.requests
        record["business_tools"] = trace.tools
        record["latency_ms"] = _ms(started)
        record["usage"] = _aggregate_usage(trace.requests)
        record["passed"] = (
            record["first_attempt_success"]
            and record["request_contract_valid"]
            and record["final_output_tool_called"] == (mode == "TOOL")
            and (
                not with_quote
                or (
                    record["quote_tool_called"]
                    and record["tool_result_entered_context"]
                    and all(tool["ticker"] == "GOOG" for tool in trace.tools)
                )
            )
        )
        record["status"] = "PASS" if record["passed"] else "FAIL"
        record["failure_domain"], record["failure_reason"] = _failure_classification(record)
        return record
    finally:
        await client.close()


def _provider_error(error: Exception) -> dict[str, object] | None:
    """仅保留 Provider 错误码与简短消息，不保留完整请求或响应。"""

    status = getattr(error, "status_code", None)
    body = getattr(error, "body", None)
    if status is None and body is None:
        return None
    item = body.get("error", body) if isinstance(body, dict) else {}
    return {
        "http_status": status,
        "code": item.get("code") if isinstance(item, dict) else None,
        "message": str(item.get("message", ""))[:300] if isinstance(item, dict) else "",
    }


def run_output_mechanism_spike(environment: Mapping[str, str]) -> dict[str, object]:
    """默认 A 成功才执行 B；显式 B/C 仅用于独立排障。"""

    stages = environment.get("OUTPUT_MECHANISM_STAGES", "A,B")
    if stages not in {"A", "B", "A,B", "C"}:
        raise ValueError("OUTPUT_MECHANISM_STAGES 只接受 A、B、A,B 或 C")
    control = environment.get("OUTPUT_MECHANISM_RUN_TOOL_CONTROL", "0")
    if control not in {"0", "1"}:
        raise ValueError("OUTPUT_MECHANISM_RUN_TOOL_CONTROL 只接受 0 或 1")
    provider = environment.get("LLM_PROVIDER", "ALIYUN_MODEL_STUDIO").strip().upper()
    if provider not in {"ALIYUN_MODEL_STUDIO", "AIHUBMIX", "GOOGLE_GEMINI"}:
        raise ValueError(f"未接入的实验 Provider: {provider}")
    google = provider == "GOOGLE_GEMINI"
    if google:
        if environment["LLM_MODEL"] != "gemini-3.8-flash":
            raise ValueError("本轮 Gemini 只允许 gemini-3.8-flash")
        if stages == "C" or control == "1":
            raise ValueError("本轮 Gemini 仅允许 Stage A/B，不运行 ToolOutput")
    required = ("GEMINI_API_KEY",) if google else ("LLM_API_KEY", "LLM_BASE_URL")
    missing = [key for key in required if not environment.get(key, "").strip()]
    if missing:
        raise ValueError(f"缺少进程环境变量: {', '.join(missing)}")
    artifact_dir = Path(environment["OUTPUT_MECHANISM_ARTIFACT_DIR"])
    artifact_dir.mkdir(parents=True, exist_ok=False)

    async def run_arm(mode: Literal["NATIVE", "TOOL"], with_quote: bool) -> dict[str, object]:
        if google:
            from phase4_google_output_spike import run_google_arm

            return await run_google_arm(
                api_key=environment["GEMINI_API_KEY"],
                model_name=environment["LLM_MODEL"],
                with_quote=with_quote,
            )
        return await _run_arm(
            mode,
            with_quote=with_quote,
            api_key=environment["LLM_API_KEY"],
            base_url=environment["LLM_BASE_URL"],
            model_name=environment["LLM_MODEL"],
            provider_name=provider,
        )

    async def run_stages() -> dict[str, object]:
        a = await run_arm("NATIVE", False) if "A" in stages else None
        b = await run_arm("NATIVE", True) if "B" in stages and (a is None or a["passed"]) else None
        c = await run_arm("TOOL", True) if stages == "C" or control == "1" else None
        return {"stage_a": a, "stage_b": b, "stage_c_tool": c}

    report: dict[str, object] = {
        "provider": provider,
        "model": environment["LLM_MODEL"],
        "endpoint": (
            "https://generativelanguage.googleapis.com"
            if google
            else _safe_endpoint(environment["LLM_BASE_URL"])
        ),
        "endpoint_family": "GEMINI_GENERATE_CONTENT" if google else "OPENAI_CHAT_COMPLETIONS",
        "thinking_mode": THINKING_MODE,
        "production_changed": False,
        **asyncio.run(run_stages()),
    }
    for stage, key in (("a", "stage_a"), ("b", "stage_b"), ("c", "stage_c_tool")):
        report[f"stage_{stage}_status"] = "MEASURED" if report[key] is not None else "NOT_RUN"
    (artifact_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8"
    )
    return report


def _failure_classification(record: dict[str, object]) -> tuple[str | None, str | None]:
    """根据请求与候选证据区分机制失败和业务诊断，不由框架异常名猜测根因。"""

    if record["passed"]:
        return None, None
    error = record.get("provider_error")
    error = error if isinstance(error, dict) else {}
    if error or record.get("failure_type") in {"TimeoutError", "APITimeoutError"}:
        return classify_failure(
            status=error.get("http_status"),
            message=str(error.get("message", "")),
            code=str(error.get("code") or record.get("failure_type", "")),
        )
    if not record["request_contract_valid"]:
        return "HARNESS_OR_INTEGRATION", "REQUEST_CONTRACT_INVALID"
    if record["with_quote"]:
        if not record["quote_tool_called"]:
            return "UNCLASSIFIED", "QUOTE_TOOL_NOT_CALLED"
        if not record["tool_result_entered_context"]:
            return "HARNESS_OR_INTEGRATION", "TOOL_RESULT_NOT_IN_CONTEXT"
    requests = record["requests"]
    models = record["model_requests"]
    if (
        record["stage"] == "B"
        and isinstance(models, list)
        and len(models) >= 2
        and models[1].get("tool_call_candidates")
    ):
        return "UNCLASSIFIED", "TOOL_CALLED_AGAIN_AFTER_FIXTURE"
    if (
        record["stage"] == "B"
        and isinstance(requests, list)
        and all(r["http_status"] == 200 for r in requests)
        and isinstance(models, list)
        and models
    ):
        for text in models[-1].get("text_candidates", []):
            try:
                json.loads(text)
            except json.JSONDecodeError:
                return "PROVIDER_CAPABILITY", "NATIVE_OUTPUT_NOT_ENFORCED_AFTER_TOOL"
    return "UNCLASSIFIED", str(record.get("failure_type") or "OUTPUT_CONTRACT_FAILED")
