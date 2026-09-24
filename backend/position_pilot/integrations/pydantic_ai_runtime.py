"""PydanticAI Production Adapter 的最小 Native Agent Loop。"""

import asyncio
import json
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from time import monotonic

from openai import AsyncOpenAI
from pydantic_ai import (
    Agent,
    FunctionToolset,
    Tool,
    UsageLimitExceeded,
    UsageLimits,
)
from pydantic_ai import (
    AgentRunResult as PydanticAgentRunResult,
)
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError, UserError
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers import Provider
from pydantic_ai.providers.alibaba import AlibabaProvider
from pydantic_ai.providers.openai import OpenAIProvider

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
from position_pilot.application.llm import LLMMessage, LLMRole, LLMStatus, LLMUsage
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
    calls: int = 0

    def execute(self, name: str, arguments: Mapping[str, object]) -> str:
        """执行一次 Application Tool，并把失败转换为显式模型观察。"""

        self._check_wall_clock()
        if self.calls >= self.budget.tool_calls:
            raise UsageLimitExceeded("tool call budget exhausted")
        self.calls += 1
        binding = self.bindings.get(name)
        normalized_arguments = dict(arguments)
        if binding is None:
            result = ToolExecutionResult("UNKNOWN_TOOL", error_code="UNKNOWN_TOOL")
        else:
            try:
                result = binding.executor(normalized_arguments)
                if not isinstance(result, ToolExecutionResult):
                    raise TypeError("Tool Executor 必须返回 ToolExecutionResult")
            except AgentToolBudgetExceeded:
                raise UsageLimitExceeded("tool call budget exhausted") from None
            except (TypeError, ValueError):
                result = ToolExecutionResult(
                    "INVALID_ARGUMENTS",
                    error_code="INVALID_ARGUMENTS",
                )
            except Exception:  # noqa: BLE001 - Provider / Tool Failure 必须成为显式观察。
                result = ToolExecutionResult("TOOL_FAILURE", error_code="TOOL_FAILURE")

        trace = AgentToolTrace(
            name=name,
            arguments=normalized_arguments,
            status=result.status,
            error_code=result.error_code,
            sources=result.sources,
        )
        self.tool_trace.append(trace)
        self.sources.extend(result.sources)
        if result.status != "OK":
            self.warnings.append(f"{result.status}:{name}")
        for related in result.related_calls:
            self.calls += 1
            self.tool_trace.append(
                AgentToolTrace(
                    name=related.name,
                    arguments=related.arguments,
                    status=related.status,
                    error_code=related.error_code,
                    sources=related.sources,
                )
            )
            self.sources.extend(related.sources)
            if related.status != "OK":
                self.warnings.append(f"{related.status}:{related.name}")
        self._check_wall_clock()
        return self._serialize(result)

    def _check_wall_clock(self) -> None:
        if self.clock() - self.started_at >= self.budget.wall_clock_seconds:
            raise UsageLimitExceeded("wall-clock budget exhausted")

    def _serialize(self, result: ToolExecutionResult) -> str:
        """把不可信 Tool 数据作为模型观察传回，不把它提升为事实。"""

        payload: dict[str, object] = {"status": result.status}
        if result.data is not None:
            payload["data"] = dict(result.data)
        if result.error_code is not None:
            payload["error_code"] = result.error_code
        sources = [*result.sources]
        for related in result.related_calls:
            sources.extend(related.sources)
        if sources:
            payload["sources"] = [dict(source) for source in sources]
        try:
            return json.dumps(payload, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            self.warnings.append(f"UNSERIALIZABLE_TOOL_RESULT:{result.status}")
            return json.dumps(
                {"status": "TOOL_FAILURE", "error_code": "UNSERIALIZABLE_TOOL_RESULT"},
                ensure_ascii=False,
            )


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
            return self._failure(
                AgentRunStatus.FAILED,
                "MODEL_HTTP_FAILURE",
                started_at,
                bridge,
                llm_status=self._http_status(error.status_code),
            )
        except ModelAPIError:
            return self._failure(
                AgentRunStatus.FAILED,
                "MODEL_API_FAILURE",
                started_at,
                bridge,
                llm_status=LLMStatus.PROVIDER_UNAVAILABLE,
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
        if not isinstance(result.output, str) or not result.output.strip():
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
        return AgentRunResult(
            AgentRunStatus.COMPLETED,
            result.output,
            None,
            () if bridge is None else tuple(bridge.tool_trace),
            () if bridge is None else tuple(bridge.sources),
            usage,
            self._latency_ms(started_at),
            llm_status=LLMStatus.OK,
            warnings=tuple(warnings),
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
        toolset: FunctionToolset[None] | None,
    ) -> PydanticAgentRunResult[str]:
        """确保 Provider Client 的创建、使用和关闭发生在同一个 Event Loop。"""

        if self._model_context_factory is not None:
            async with self._model_context_factory() as model:
                return await self._run_with_wall_clock_limit(
                    model, user_prompt, history, request, instructions, toolset
                )
        assert self._model is not None
        return await self._run_with_wall_clock_limit(
            self._model, user_prompt, history, request, instructions, toolset
        )

    async def _run_with_wall_clock_limit(
        self,
        model: Model,
        user_prompt: str,
        history: list[ModelMessage],
        request: AgentRunRequest,
        instructions: tuple[str, ...],
        toolset: FunctionToolset[None] | None,
    ) -> PydanticAgentRunResult[str]:
        """对完整 Model / Tool Loop 应用可中断的总 Wall-clock Ceiling。"""

        agent = Agent(
            model,
            output_type=str,
            instructions=self._instructions(instructions, request),
            toolsets=(() if toolset is None else (toolset,)),
            retries=0,
            end_strategy="exhaustive",
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
                    tool_calls_limit=request.budget.tool_calls,
                ),
            ),
            timeout=request.budget.wall_clock_seconds,
        )

    @staticmethod
    def _instructions(
        instructions: tuple[str, ...],
        request: AgentRunRequest,
    ) -> str:
        """把 System Prompt 与输出格式约束保留在 Application 边界。"""

        values = list(instructions)
        if request.response_format.value == "JSON_OBJECT":
            values.append("最终候选必须是可由 Application 解析的 JSON object 文本。")
        return "\n\n".join(values)

    @staticmethod
    def _toolset(
        bindings: tuple[AgentToolBinding, ...],
        bridge: _ToolBridge,
    ) -> FunctionToolset[None] | None:
        """按本轮动态 Binding 建立 Framework Toolset。"""

        if not bindings:
            return None
        toolset: FunctionToolset[None] = FunctionToolset(id="position-pilot-production")
        for binding in bindings:

            def execute_dynamic(
                _tool_name: str = binding.definition.name,
                **arguments: object,
            ) -> str:
                """将动态 JSON Schema 参数交给 Application Executor。"""

                return bridge.execute(_tool_name, arguments)

            toolset.add_tool(
                Tool.from_schema(
                    execute_dynamic,
                    name=binding.definition.name,
                    description=binding.definition.description,
                    json_schema=dict(binding.definition.parameters),
                )
            )
        return toolset

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
    ) -> AgentRunResult:
        """创建不携带异常正文或伪造答案的稳定失败结果。"""

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
        )

    def _latency_ms(self, started_at: float) -> float:
        return max(0.0, (self._clock() - started_at) * 1000)


def create_pydantic_ai_runtime(settings: Settings) -> PydanticAIRuntime:
    """根据已校验 Settings 创建 Alibaba / OpenAI-compatible Native Adapter。"""

    api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
    if not api_key:
        return PydanticAIRuntime(
            None,
            provider_name=settings.llm_provider,
            model_name=settings.llm_model,
            timeout_seconds=settings.llm_request_timeout_seconds,
            max_retries=0,
        )

    @asynccontextmanager
    async def model_context() -> AsyncIterator[Model]:
        """每次同步 Run 创建独立异步客户端，避免跨已关闭的 Event Loop 复用连接。"""

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=str(settings.llm_base_url),
            timeout=settings.llm_request_timeout_seconds,
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
        timeout_seconds=settings.llm_request_timeout_seconds,
        max_retries=0,
        model_context_factory=model_context,
    )


__all__ = ["PydanticAIRuntime", "create_pydantic_ai_runtime"]
