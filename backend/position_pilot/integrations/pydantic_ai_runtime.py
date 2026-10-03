"""PydanticAI Production Adapter 的最小 Native Agent Loop。"""

import asyncio
import json
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from time import monotonic
from typing import Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict
from pydantic_ai import (
    Agent,
    FunctionToolset,
    NativeOutput,
    Tool,
    ToolOutput,
    UsageLimitExceeded,
    UsageLimits,
)
from pydantic_ai import (
    AgentRunResult as PydanticAgentRunResult,
)
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.exceptions import (
    ModelAPIError,
    ModelHTTPError,
    UnexpectedModelBehavior,
    UserError,
)
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import Model, ModelRequestContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers import Provider
from pydantic_ai.providers.alibaba import AlibabaProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.tools import RunContext, ToolDefinition
from pydantic_ai.toolsets import AbstractToolset

from position_pilot.application.agent_runtime import (
    AgentRunBudget,
    AgentRunRequest,
    AgentRunResult,
    AgentRunStatus,
    AgentRuntime,
    AgentToolBinding,
    AgentToolBudgetExceeded,
    AgentToolTrace,
)
from position_pilot.application.llm import (
    LLMMessage,
    LLMResponseFormat,
    LLMRole,
    LLMStatus,
    LLMUsage,
)
from position_pilot.application.tool_catalog import ToolExecutionResult
from position_pilot.config import Settings


@dataclass(slots=True)
class _ToolBridge:
    """将 PydanticAI Function Tool 绑定到 Application-owned Executor。"""

    bindings: Mapping[str, AgentToolBinding]
    budget: AgentRunBudget
    clock: Callable[[], float]
    started_at: float
    tool_trace: list[AgentToolTrace] = field(default_factory=list)
    sources: list[Mapping[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    invocation_count: int = 0
    provider_fetch_count: int = 0
    model_request_count: int = 0
    tool_attempt_count: int = 0
    final_only_request_count: int = 0
    final_only_reason: str | None = None
    final_only_violation: bool = False
    admissions: dict[str, bool] = field(default_factory=dict)
    duplicate_calls: set[str] = field(default_factory=set)
    seen_arguments: set[str] = field(default_factory=set)

    def prepare_tools(
        self, ctx: RunContext[None], definitions: list[ToolDefinition]
    ) -> list[ToolDefinition]:
        """仅在取证额度耗尽或最后请求时隐藏业务工具，输出机制保持原样。"""
        if self.invocation_count >= self.budget.tool_calls:
            self.final_only_reason = "TOOL_CALL_BUDGET_EXCEEDED"
        elif ctx.usage.requests >= self.budget.model_requests - 1:
            self.final_only_reason = "MODEL_REQUEST_BUDGET_EXCEEDED"
        return [] if self.final_only_reason is not None else definitions

    def observe_attempts(self, response: ModelResponse, output_names: set[str]) -> None:
        """按响应原顺序准入，记录全部模型 attempt，包括整批超额和未知工具。"""
        self.admissions.clear()
        self.duplicate_calls.clear()
        for part in response.parts:
            if not isinstance(part, ToolCallPart) or part.tool_name in output_names:
                continue
            self.tool_attempt_count += 1
            try:
                arguments: object = part.args_as_dict()
            except ValueError:
                arguments = part.args
            if isinstance(arguments, dict) and isinstance(ticker := arguments.get("ticker"), str):
                arguments = {**arguments, "ticker": ticker.strip().upper()}
            key = json.dumps([part.tool_name, arguments], sort_keys=True)
            if key in self.seen_arguments:
                self.duplicate_calls.add(part.tool_call_id)
            self.seen_arguments.add(key)
            admitted = (
                self.final_only_reason is None and self.invocation_count < self.budget.tool_calls
            )
            self.admissions[part.tool_call_id] = admitted
            if admitted:
                self.invocation_count += 1
            if self.final_only_reason is not None:
                self.final_only_violation = True
                self.warnings.append("TOOL_CALL_AFTER_FINAL_ONLY")

    def execute(self, name: str, arguments: Mapping[str, object], call_id: str) -> str:
        """执行一次 Application Tool，并把失败转换为显式模型观察。"""

        self._check_wall_clock()
        binding = self.bindings.get(name)
        normalized_arguments = dict(arguments)
        if not self.admissions[call_id]:
            result = ToolExecutionResult(
                "TOOL_ATTEMPT_BUDGET_EXHAUSTED",
                {"tool": name, "retry_same_tool": False},
                error_code="TOOL_ATTEMPT_BUDGET_EXHAUSTED",
                provider_fetch_count=0,
                application_execution_count=0,
            )
        elif binding is None:
            result = ToolExecutionResult(
                "UNKNOWN_TOOL",
                error_code="UNKNOWN_TOOL",
                provider_fetch_count=0,
                application_execution_count=0,
            )
        else:
            try:
                result = binding.executor(normalized_arguments)
                if not isinstance(result, ToolExecutionResult):
                    raise TypeError("Tool Executor 必须返回 ToolExecutionResult")
            except AgentToolBudgetExceeded as error:
                result = ToolExecutionResult(
                    "TOOL_QUOTA_EXHAUSTED",
                    {
                        "tool": name,
                        "blocking_tool": error.tool_name or name,
                        "existing_observation_available": False,
                        "retry_same_tool": False,
                    },
                    error_code="TOOL_QUOTA_EXHAUSTED",
                    provider_fetch_count=0,
                    application_execution_count=0,
                )
            except (TypeError, ValueError):
                result = ToolExecutionResult(
                    "INVALID_ARGUMENTS",
                    error_code="INVALID_ARGUMENTS",
                    provider_fetch_count=0,
                    application_execution_count=0,
                )
            except Exception:  # noqa: BLE001 - Provider / Tool Failure 必须成为显式观察。
                result = ToolExecutionResult(
                    "TOOL_FAILURE", error_code="TOOL_FAILURE", provider_fetch_count=0
                )

        trace = AgentToolTrace(
            name=name,
            arguments=normalized_arguments,
            status=result.status,
            error_code=result.error_code,
            sources=result.sources,
            provider_fetch_count=result.provider_fetch_count,
            application_execution_count=result.application_execution_count,
            cache_reused=result.cache_reused,
            duplicate_attempt=call_id in self.duplicate_calls or result.cache_reused,
            tool_call_id=call_id,
        )
        self.tool_trace.append(trace)
        self.provider_fetch_count += result.provider_fetch_count
        self.sources.extend(result.sources)
        if result.status != "OK":
            self.warnings.append(f"{result.status}:{name}")
        for related in result.related_calls:
            self.tool_trace.append(
                AgentToolTrace(
                    name=related.name,
                    arguments=related.arguments,
                    status=related.status,
                    error_code=related.error_code,
                    sources=related.sources,
                    invoked_by_model=False,
                    provider_fetch_count=related.provider_fetch_count,
                    application_execution_count=related.application_execution_count,
                    cache_reused=related.cache_reused,
                )
            )
            self.provider_fetch_count += related.provider_fetch_count
            self.sources.extend(related.sources)
            if related.status != "OK":
                self.warnings.append(f"{related.status}:{related.name}")
        self._check_wall_clock()
        return self._serialize(name, result)

    def _check_wall_clock(self) -> None:
        if self.clock() - self.started_at >= self.budget.wall_clock_seconds:
            raise UsageLimitExceeded("wall-clock budget exhausted")

    def _serialize(self, name: str, result: ToolExecutionResult) -> str:
        """仅向模型暴露可引用 Source，失败尝试仍独立可见。"""

        payload: dict[str, object] = {"status": result.status}
        if result.data is not None:
            payload["data"] = dict(result.data)
        if result.error_code is not None:
            payload["error_code"] = result.error_code
        sources = [*result.sources]
        for related in result.related_calls:
            sources.extend(related.sources)
        payload["sources"] = [
            dict(source)
            for source in sources
            if source.get("status") == "OK"
            and isinstance(source_id := source.get("source_id"), str)
            and bool(source_id.strip())
            and isinstance(source_type := source.get("type"), str)
            and bool(source_type.strip())
        ]
        payload["attempt_observations"] = [
            {"tool_name": name, "status": result.status, "error_code": result.error_code},
            *(
                {
                    "tool_name": related.name,
                    "status": related.status,
                    "error_code": related.error_code,
                }
                for related in result.related_calls
            ),
        ]
        try:
            return json.dumps(payload, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            self.warnings.append(f"UNSERIALIZABLE_TOOL_RESULT:{result.status}")
            return json.dumps(
                {
                    "status": "TOOL_FAILURE",
                    "error_code": "UNSERIALIZABLE_TOOL_RESULT",
                    "sources": [],
                    "attempt_observations": [
                        {
                            "tool_name": name,
                            "status": "TOOL_FAILURE",
                            "error_code": "UNSERIALIZABLE_TOOL_RESULT",
                        }
                    ],
                },
                ensure_ascii=False,
            )


@dataclass
class _ToolLoopCapability(AbstractCapability[None]):
    """复用框架响应边界记录 attempt，不包装 Provider 或改写模型结果。"""

    bridge: _ToolBridge

    async def before_model_request(
        self, ctx: RunContext[None], request_context: ModelRequestContext
    ) -> ModelRequestContext:
        """记录请求开始与无业务 Tool 的 Final-only 机会，不增加额外请求。"""
        self.bridge.model_request_count += 1
        if not request_context.model_request_parameters.function_tools:
            self.bridge.final_only_request_count += 1
        return request_context

    async def after_model_request(
        self,
        ctx: RunContext[None],
        *,
        request_context: ModelRequestContext,
        response: ModelResponse,
    ) -> ModelResponse:
        """登记完整响应的 attempt，再交回原生框架处理，Final Tool 不占取证额度。"""
        self.bridge.observe_attempts(
            response,
            {tool.name for tool in request_context.model_request_parameters.output_tools},
        )
        return response


class _StructuredFinalCandidate(BaseModel):
    """只约束 Final Tool 的基本形状，来源身份仍由 Application 校验。"""

    model_config = ConfigDict(extra="forbid")

    answer: str
    source_refs: list[dict[str, str]]


class _NativePortfolioSourceRef(BaseModel):
    """Native strict Schema 中不带 ticker 的 Portfolio 来源。"""

    model_config = ConfigDict(extra="forbid")
    type: Literal["PORTFOLIO_SNAPSHOT"]


class _NativeTickerSourceRef(BaseModel):
    """Native strict Schema 中必须带 ticker 的市场来源。"""

    model_config = ConfigDict(extra="forbid")
    type: Literal["CURRENT_QUOTE", "PRICE_HISTORY", "RECENT_NEWS", "MARKET_CONTEXT"]
    ticker: str


class _NativeStructuredFinalCandidate(BaseModel):
    """与业务 Final Contract 等价，并能通过 Bedrock strict JSON Schema 表达。"""

    model_config = ConfigDict(extra="forbid")
    answer: str
    source_refs: list[_NativePortfolioSourceRef | _NativeTickerSourceRef]


class PydanticAIRuntime(AgentRuntime):
    """使用 PydanticAI 原生 Agent.run 与 Tool Loop 的 Production Adapter。"""

    def __init__(
        self,
        model: Model | None,
        *,
        provider_name: str = "PYDANTIC_AI",
        model_name: str = "unknown",
        timeout_seconds: float = 30.0,
        max_retries: int = 0,
        clock: Callable[[], float] = monotonic,
        model_context_factory: Callable[[], AbstractAsyncContextManager[Model]] | None = None,
        output_mechanism: Literal["TOOL", "NATIVE"] = "TOOL",
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds 必须是正数")
        if max_retries != 0:
            raise ValueError("Production Adapter 当前不启用隐式重试，max_retries 必须为 0")
        self._model = model
        self._model_context_factory = model_context_factory
        self._provider_name = provider_name
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._clock = clock
        self._output_mechanism = output_mechanism

    @property
    def provider_name(self) -> str:
        """返回用于运行元数据的 Provider 标签。"""

        return self._provider_name

    @property
    def model_name(self) -> str:
        """返回用于运行元数据的 Model 标签。"""

        return self._model_name

    @property
    def timeout_seconds(self) -> float:
        """返回单个模型请求的 HTTP timeout。"""

        return self._timeout_seconds

    @property
    def max_retries(self) -> int:
        """返回 Adapter 配置的 Provider retry 次数。"""

        return self._max_retries

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        """使用框架原生 Loop 执行请求，并返回 Application-owned 结果。"""

        started_at = self._clock()
        if self._model is None and self._model_context_factory is None:
            return self._failure(
                AgentRunStatus.FAILED,
                "MODEL_CREDENTIAL_MISSING",
                started_at,
                None,
                llm_status=LLMStatus.AUTHENTICATION_FAILED,
            )
        bridge: _ToolBridge | None = None
        try:
            history, user_prompt, instructions = self._message_history(request.messages)
            bridge = _ToolBridge(
                {binding.definition.name: binding for binding in request.tools},
                request.budget,
                self._clock,
                started_at,
            )
            toolset = self._toolset(request.tools, bridge)
            result = asyncio.run(
                self._run_with_model_context(
                    user_prompt,
                    history,
                    request,
                    instructions,
                    toolset,
                    bridge,
                )
            )
        except TimeoutError:
            return self._failure(
                AgentRunStatus.BUDGET_EXHAUSTED,
                "WALL_CLOCK_BUDGET_EXCEEDED",
                started_at,
                bridge,
            )
        except UsageLimitExceeded as error:
            return self._failure(
                AgentRunStatus.BUDGET_EXHAUSTED,
                self._budget_failure_code(error),
                started_at,
                bridge,
            )
        except ModelHTTPError as error:
            provider_error_code, provider_error_message = self._provider_http_error(error)
            return self._failure(
                AgentRunStatus.FAILED,
                "MODEL_HTTP_FAILURE",
                started_at,
                bridge,
                llm_status=self._http_status(error.status_code),
                provider_http_status=error.status_code,
                provider_error_code=provider_error_code,
                provider_error_message=provider_error_message,
            )
        except ModelAPIError:
            return self._failure(
                AgentRunStatus.FAILED,
                "MODEL_API_FAILURE",
                started_at,
                bridge,
                llm_status=LLMStatus.PROVIDER_UNAVAILABLE,
            )
        except UnexpectedModelBehavior as error:
            return self._failure(
                AgentRunStatus.BUDGET_EXHAUSTED
                if bridge and bridge.final_only_violation
                else AgentRunStatus.FAILED,
                bridge.final_only_reason
                if bridge and bridge.final_only_violation and bridge.final_only_reason is not None
                else "INVALID_PROVIDER_RESPONSE",
                started_at,
                bridge,
                llm_status=LLMStatus.INVALID_PROVIDER_RESPONSE,
                framework_error_kind=self._framework_error_kind(error),
                framework_error_cause=(
                    type(error.__cause__).__name__ if error.__cause__ is not None else None
                ),
            )
        except (UserError, ValueError, TypeError):
            return self._failure(
                AgentRunStatus.FAILED,
                "INVALID_AGENT_REQUEST",
                started_at,
                bridge,
                llm_status=LLMStatus.INVALID_REQUEST,
            )
        except OSError:
            return self._failure(
                AgentRunStatus.FAILED,
                "MODEL_TIMEOUT_OR_TRANSPORT_FAILURE",
                started_at,
                bridge,
                llm_status=LLMStatus.PROVIDER_UNAVAILABLE,
            )
        except Exception:  # noqa: BLE001 - Adapter 不向上泄露 Provider 异常正文。
            return self._failure(
                AgentRunStatus.FAILED,
                "PYDANTIC_AI_RUNTIME_FAILURE",
                started_at,
                bridge,
                llm_status=LLMStatus.PROVIDER_UNAVAILABLE,
            )

        if self._clock() - started_at >= request.budget.wall_clock_seconds:
            return self._failure(
                AgentRunStatus.BUDGET_EXHAUSTED,
                "WALL_CLOCK_BUDGET_EXCEEDED",
                started_at,
                bridge,
            )
        if isinstance(result.output, (_StructuredFinalCandidate, _NativeStructuredFinalCandidate)):
            final_candidate = result.output.model_dump_json()
        elif isinstance(result.output, str):
            final_candidate = result.output
        else:
            final_candidate = ""
        if not final_candidate.strip():
            return self._failure(
                AgentRunStatus.FAILED,
                "INVALID_PROVIDER_RESPONSE",
                started_at,
                bridge,
                llm_status=LLMStatus.INVALID_PROVIDER_RESPONSE,
            )
        usage = self._map_usage(result.usage)
        warnings = () if usage is not None else ("USAGE_NOT_REPORTED",)
        if bridge is not None:
            warnings = (*bridge.warnings, *warnings)
        responses = (
            message for message in result.all_messages() if isinstance(message, ModelResponse)
        )
        last_response = next(reversed(tuple(responses)), None)
        provider_details = None if last_response is None else last_response.provider_details
        finish_reason = (
            provider_details.get("finish_reason") if isinstance(provider_details, Mapping) else None
        )
        return AgentRunResult(
            AgentRunStatus.COMPLETED,
            final_candidate,
            None,
            () if bridge is None else tuple(bridge.tool_trace),
            () if bridge is None else tuple(bridge.sources),
            usage,
            self._latency_ms(started_at),
            llm_status=LLMStatus.OK,
            warnings=tuple(warnings),
            provider_finish_reason=finish_reason if isinstance(finish_reason, str) else None,
            model_request_count=bridge.model_request_count,
            tool_attempt_count=bridge.tool_attempt_count,
            tool_attempt_admission_count=bridge.invocation_count,
            final_only_request_count=bridge.final_only_request_count,
        )

    @staticmethod
    def _message_history(
        messages: tuple[LLMMessage, ...],
    ) -> tuple[list[ModelMessage], str, tuple[str, ...]]:
        """将 Provider-neutral Messages 映射到 PydanticAI 原生 History。"""

        if not messages or messages[-1].role is not LLMRole.USER:
            raise ValueError("Native Agent 请求必须以当前 User Message 结束")
        current = messages[-1]
        if current.content is None:
            raise ValueError("当前 User Message 不能为空")
        history: list[ModelMessage] = []
        instructions: list[str] = []
        tool_names: dict[str, str] = {}
        for message in messages[:-1]:
            if message.role is LLMRole.SYSTEM:
                if message.content is not None:
                    instructions.append(message.content)
            elif message.role is LLMRole.USER:
                if message.content is None:
                    raise ValueError("History User Message 不能为空")
                history.append(ModelRequest(parts=(UserPromptPart(message.content),)))
            elif message.role is LLMRole.ASSISTANT:
                parts: list[TextPart | ToolCallPart] = []
                if message.content is not None:
                    parts.append(TextPart(message.content))
                for call in message.tool_calls:
                    tool_names[call.id] = call.name
                    parts.append(ToolCallPart(call.name, dict(call.arguments), call.id))
                if not parts:
                    raise ValueError("History Assistant Message 不能为空")
                history.append(ModelResponse(parts=tuple(parts)))
            elif message.role is LLMRole.TOOL:
                if message.content is None or message.tool_call_id is None:
                    raise ValueError("History Tool Message 不完整")
                tool_name = tool_names.get(message.tool_call_id)
                if tool_name is None:
                    raise ValueError("History Tool Message 缺少对应 Tool Call")
                history.append(
                    ModelRequest(
                        parts=(
                            ToolReturnPart(
                                tool_name,
                                message.content,
                                message.tool_call_id,
                            ),
                        )
                    )
                )
            else:
                raise ValueError("不支持的 LLM Message Role")
        return history, current.content, tuple(instructions)

    async def _run_with_model_context(
        self,
        user_prompt: str,
        history: list[ModelMessage],
        request: AgentRunRequest,
        instructions: tuple[str, ...],
        toolset: AbstractToolset[None] | None,
        bridge: _ToolBridge,
    ) -> PydanticAgentRunResult[object]:
        """确保 Provider Client 的创建、使用和关闭发生在同一个 Event Loop。"""

        if self._model_context_factory is not None:
            async with self._model_context_factory() as model:
                return await self._run_with_wall_clock_limit(
                    model, user_prompt, history, request, instructions, toolset, bridge
                )
        assert self._model is not None
        return await self._run_with_wall_clock_limit(
            self._model, user_prompt, history, request, instructions, toolset, bridge
        )

    async def _run_with_wall_clock_limit(
        self,
        model: Model,
        user_prompt: str,
        history: list[ModelMessage],
        request: AgentRunRequest,
        instructions: tuple[str, ...],
        toolset: AbstractToolset[None] | None,
        bridge: _ToolBridge,
    ) -> PydanticAgentRunResult[object]:
        """对完整 Model / Tool Loop 应用可中断的总 Wall-clock Ceiling。"""

        output_type: (
            NativeOutput[_NativeStructuredFinalCandidate]
            | ToolOutput[_StructuredFinalCandidate]
            | type[str]
        )
        if request.response_format is LLMResponseFormat.JSON_OBJECT:
            output_type = (
                NativeOutput(
                    _NativeStructuredFinalCandidate,
                    name="final_investment_answer",
                    strict=True,
                )
                if self._output_mechanism == "NATIVE"
                else ToolOutput(
                    _StructuredFinalCandidate,
                    name="final_investment_answer",
                    max_retries=0,
                )
            )
        else:
            output_type = str
        agent = Agent(
            model,
            output_type=output_type,
            instructions=self._instructions(instructions, request),
            toolsets=(() if toolset is None else (toolset,)),
            retries=0,
            end_strategy="exhaustive",
            capabilities=(_ToolLoopCapability(bridge),),
        )
        return await asyncio.wait_for(
            agent.run(
                user_prompt,
                message_history=history,
                model_settings={
                    "timeout": min(
                        self._timeout_seconds,
                        request.budget.wall_clock_seconds,
                    )
                },
                usage_limits=UsageLimits(
                    request_limit=request.budget.model_requests,
                    # 整批超额由 admission 返回 Observation，框架只保留请求 Ceiling。
                ),
            ),
            timeout=request.budget.wall_clock_seconds,
        )

    def _instructions(
        self,
        instructions: tuple[str, ...],
        request: AgentRunRequest,
    ) -> str:
        """把 System Prompt 与输出格式约束保留在 Application 边界。"""

        values = list(instructions)
        if request.response_format is LLMResponseFormat.JSON_OBJECT:
            if self._output_mechanism == "NATIVE":
                values.append("最终按结构化输出格式返回 answer 和 source_refs。")
            else:
                values.append(
                    "最终请调用 final_investment_answer 输出 answer 和 source_refs；"
                    "不要以普通文本或 Markdown 代码围栏返回 JSON。"
                )
        return "\n\n".join(values)

    @staticmethod
    def _toolset(
        bindings: tuple[AgentToolBinding, ...],
        bridge: _ToolBridge,
    ) -> AbstractToolset[None] | None:
        """按本轮动态 Binding 建立 Framework Toolset。"""

        if not bindings:
            return None
        toolset: FunctionToolset[None] = FunctionToolset(id="position-pilot-production")
        for binding in bindings:

            def execute_dynamic(
                ctx: RunContext[None],
                **arguments: object,
            ) -> str:
                """将动态 JSON Schema 参数交给 Application Executor。"""

                assert ctx.tool_call_id is not None
                assert ctx.tool_name is not None
                return bridge.execute(ctx.tool_name, arguments, ctx.tool_call_id)

            toolset.add_tool(
                Tool.from_schema(
                    execute_dynamic,
                    name=binding.definition.name,
                    description=binding.definition.description,
                    json_schema=dict(binding.definition.parameters),
                    takes_ctx=True,
                )
            )
        return toolset.prepared(bridge.prepare_tools)

    @staticmethod
    def _map_usage(usage: object) -> LLMUsage | None:
        """Provider 未报告 Token 时保留 UNKNOWN，而不是伪造 Usage。"""

        input_tokens = getattr(usage, "input_tokens", 0)
        output_tokens = getattr(usage, "output_tokens", 0)
        if input_tokens == 0 and output_tokens == 0:
            return None
        return LLMUsage(input_tokens, output_tokens, input_tokens + output_tokens)

    @staticmethod
    def _http_status(status_code: int) -> LLMStatus:
        if status_code in {401, 403}:
            return LLMStatus.AUTHENTICATION_FAILED
        if status_code == 429:
            return LLMStatus.RATE_LIMITED
        if status_code == 408 or status_code >= 500:
            return LLMStatus.PROVIDER_UNAVAILABLE
        return LLMStatus.INVALID_REQUEST

    @staticmethod
    def _provider_http_error(error: ModelHTTPError) -> tuple[str | None, str | None]:
        """仅提取 Provider 的错误码与说明，不携带整个响应正文。"""

        body = error.body
        if not isinstance(body, Mapping):
            return None, None
        detail = body.get("error", body.get("Error", body))
        if not isinstance(detail, Mapping):
            return None, None
        code = detail.get("code", detail.get("error_code", detail.get("Code")))
        message = detail.get("message", detail.get("error_message", detail.get("Message")))
        return (
            code if isinstance(code, str) else None,
            message if isinstance(message, str) else None,
        )

    @staticmethod
    def _framework_error_kind(error: UnexpectedModelBehavior) -> str:
        """仅记录安全的框架失败类别，不保存可能包含请求内容的异常正文。"""

        if error.message.startswith("Exceeded maximum output retries"):
            return "OUTPUT_RETRY_EXHAUSTED"
        if error.message.startswith("Invalid response, unable to"):
            return "OUTPUT_RESPONSE_INVALID"
        if error.message.startswith("Invalid response from"):
            return "PROVIDER_RESPONSE_SHAPE_INVALID"
        return "UNEXPECTED_MODEL_BEHAVIOR"

    @staticmethod
    def _budget_failure_code(error: UsageLimitExceeded) -> str:
        text = str(error)
        if "wall-clock" in text:
            return "WALL_CLOCK_BUDGET_EXCEEDED"
        if "tool" in text:
            return "TOOL_CALL_BUDGET_EXCEEDED"
        if "request" in text:
            return "MODEL_REQUEST_BUDGET_EXCEEDED"
        return "AGENT_BUDGET_EXCEEDED"

    def _failure(
        self,
        status: AgentRunStatus,
        failure_code: str,
        started_at: float,
        bridge: _ToolBridge | None,
        *,
        llm_status: LLMStatus | None = None,
        provider_http_status: int | None = None,
        provider_error_code: str | None = None,
        provider_error_message: str | None = None,
        framework_error_kind: str | None = None,
        framework_error_cause: str | None = None,
    ) -> AgentRunResult:
        """创建稳定失败结果；Provider 诊断仅留在内部结果，不生成伪造答案。"""

        return AgentRunResult(
            status,
            None,
            failure_code,
            () if bridge is None else tuple(bridge.tool_trace),
            () if bridge is None else tuple(bridge.sources),
            None,
            self._latency_ms(started_at),
            llm_status=llm_status,
            warnings=() if bridge is None else tuple(bridge.warnings),
            provider_http_status=provider_http_status,
            provider_error_code=provider_error_code,
            provider_error_message=provider_error_message,
            framework_error_kind=framework_error_kind,
            framework_error_cause=framework_error_cause,
            model_request_count=0 if bridge is None else bridge.model_request_count,
            tool_attempt_count=0 if bridge is None else bridge.tool_attempt_count,
            tool_attempt_admission_count=0 if bridge is None else bridge.invocation_count,
            final_only_request_count=0 if bridge is None else bridge.final_only_request_count,
        )

    def _latency_ms(self, started_at: float) -> float:
        return max(0.0, (self._clock() - started_at) * 1000)


def create_pydantic_ai_runtime(settings: Settings) -> PydanticAIRuntime:
    """根据已校验 Settings 创建当前 Provider 对应的 PydanticAI Adapter。"""

    api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
    if not api_key:
        return PydanticAIRuntime(
            None,
            provider_name=settings.llm_provider,
            model_name=settings.llm_model,
            timeout_seconds=settings.native_llm_request_timeout_seconds,
            max_retries=0,
        )

    @asynccontextmanager
    async def model_context() -> AsyncIterator[Model]:
        """每次同步 Run 创建独立异步客户端，避免跨已关闭的 Event Loop 复用连接。"""

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=str(settings.llm_base_url),
            timeout=settings.native_llm_request_timeout_seconds,
            max_retries=0,
        )
        try:
            provider: Provider[AsyncOpenAI]
            if settings.llm_provider == "ALIYUN_MODEL_STUDIO":
                provider = AlibabaProvider(openai_client=client)
            else:
                provider = OpenAIProvider(openai_client=client)
            yield OpenAIChatModel(settings.llm_model, provider=provider)
        finally:
            await client.close()

    return PydanticAIRuntime(
        None,
        provider_name=settings.llm_provider,
        model_name=settings.llm_model,
        timeout_seconds=settings.native_llm_request_timeout_seconds,
        max_retries=0,
        model_context_factory=model_context,
    )


__all__ = ["PydanticAIRuntime", "create_pydantic_ai_runtime"]
