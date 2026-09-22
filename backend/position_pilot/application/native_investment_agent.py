"""使用 Native AgentRuntime 的 Production Investment Agent Facade。"""

import json
import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from uuid import UUID

from position_pilot.application.agent_runtime import (
    AgentRunBudget,
    AgentRunRequest,
    AgentRunResult,
    AgentRunStatus,
    AgentRuntime,
    AgentToolBinding,
    AgentToolBudgetExceeded,
)
from position_pilot.application.investment_agent import (
    CONTEXT_TOOLS,
    CURRENT_QUOTE_TOOL_NAME,
    MARKET_CONTEXT_TOOL_NAME,
    MAX_QUESTION_LENGTH,
    RECENT_NEWS_TOOL_NAME,
    RECENT_PRICE_HISTORY_TOOL_NAME,
    SYSTEM_PROMPT,
    ContextSource,
    ContextSourceType,
    InvestmentAgent,
    InvestmentAnswer,
    InvestmentFailureCode,
    InvestmentRequestFailure,
    InvestmentResponseStatus,
    MarketContextReader,
    MarketDataReader,
    PortfolioContextReader,
    RecentNewsReader,
)
from position_pilot.application.investment_answer import StructuredInvestmentAnswer
from position_pilot.application.investment_context import PortfolioSnapshot
from position_pilot.application.investment_context_builder import InvestmentContextBuilder
from position_pilot.application.investment_tool_executor import (
    FinancialToolExecution,
    FinancialToolExecutor,
    InvalidFinancialToolResult,
)
from position_pilot.application.llm import (
    LLMMessage,
    LLMResponseFormat,
    LLMRole,
    LLMStatus,
    LLMToolCall,
)
from position_pilot.application.source_registry import SourceValidator
from position_pilot.application.tool_catalog import (
    DescriptorToolProvider,
    StaticToolAccessPolicy,
    ToolCatalog,
    ToolExecutionRecord,
    ToolExecutionResult,
    ToolExposure,
    ToolExposurePlanner,
    current_financial_tool_descriptors,
)
from position_pilot.domain.market_data import MarketDataResult
from position_pilot.domain.news import NewsResult

LOGGER = logging.getLogger(__name__)
DEFAULT_MODEL_REQUEST_BUDGET = 3
DEFAULT_TOOL_CALL_BUDGET = 4
DEFAULT_WALL_CLOCK_BUDGET_SECONDS = 30.0


class _AuthorizedToolSession:
    """在 Provider 调用前统一执行本轮 Tool 授权与预算预留。"""

    def __init__(self, allowed_names: frozenset[str], call_budget: int) -> None:
        self._allowed_names = allowed_names
        self._call_budget = call_budget
        self._used_calls = 0

    def reserve(self, names: tuple[str, ...]) -> bool:
        """原子预留一组实际调用，避免复合 Tool 只计算外层调用。"""

        if any(name not in self._allowed_names for name in names):
            return False
        if self._used_calls + len(names) > self._call_budget:
            raise AgentToolBudgetExceeded
        self._used_calls += len(names)
        return True


class NativeInvestmentAgent:
    """组合 Application Context、Tool 与 PydanticAI 等 Native Runtime。"""

    def __init__(
        self,
        portfolio_reader: PortfolioContextReader,
        market_data: MarketDataReader,
        runtime: AgentRuntime,
        *,
        news: RecentNewsReader,
        market_context: MarketContextReader,
        clock: Callable[[], datetime] | None = None,
        enabled_tool_names: frozenset[str] | None = None,
        wall_clock_budget_seconds: float = DEFAULT_WALL_CLOCK_BUDGET_SECONDS,
    ) -> None:
        self._portfolio_reader = portfolio_reader
        self._market_data = market_data
        self._runtime = runtime
        self._news = news
        self._market_context = market_context
        self._clock = clock or (lambda: datetime.now(UTC))
        self._enabled_tool_names = enabled_tool_names
        self._wall_clock_budget_seconds = wall_clock_budget_seconds
        self._tool_catalog = ToolCatalog(
            (DescriptorToolProvider(current_financial_tool_descriptors(CONTEXT_TOOLS)),)
        )
        self._tool_policy = StaticToolAccessPolicy(enabled_names=enabled_tool_names)

    def answer(
        self,
        user_id: UUID,
        question: str,
    ) -> InvestmentAnswer | InvestmentRequestFailure:
        """执行一次 Native Tool Loop，并应用 PositionPilot 最终业务校验。"""

        normalized_question = question.strip() if isinstance(question, str) else ""
        if not normalized_question or len(normalized_question) > MAX_QUESTION_LENGTH:
            return InvestmentRequestFailure(
                InvestmentFailureCode.INVALID_QUESTION,
                f"question 必须包含 1 到 {MAX_QUESTION_LENGTH} 个字符",
            )

        portfolio_context = self._portfolio_reader.get_investment_context(user_id)
        snapshot = PortfolioSnapshot.from_context(portfolio_context)
        sources: list[ContextSource] = [
            ContextSource(
                ContextSourceType.PORTFOLIO_SNAPSHOT,
                InvestmentResponseStatus.OK.value,
            )
        ]
        messages = InvestmentContextBuilder(SYSTEM_PROMPT).build(
            portfolio_context,
            normalized_question,
        )
        exposure = self._exposure(user_id)
        executor = FinancialToolExecutor(
            self._market_data,
            self._news,
            self._market_context,
            clock=self._clock,
        )
        tool_session = _AuthorizedToolSession(
            frozenset(descriptor.name for descriptor in exposure.descriptors),
            DEFAULT_TOOL_CALL_BUDGET,
        )
        bindings = tuple(
            AgentToolBinding(
                descriptor.definition,
                self._runtime_executor(
                    descriptor.name,
                    executor,
                    snapshot,
                    tool_session,
                ),
            )
            for descriptor in exposure.descriptors
        )
        result = self._runtime.run(
            AgentRunRequest(
                messages,
                bindings,
                AgentRunBudget(
                    model_requests=DEFAULT_MODEL_REQUEST_BUDGET,
                    tool_calls=DEFAULT_TOOL_CALL_BUDGET,
                    wall_clock_seconds=self._wall_clock_budget_seconds,
                ),
                LLMResponseFormat.JSON_OBJECT,
            )
        )
        failure = self._runtime_failure(result)
        if failure is not None:
            return failure
        assert result.final_candidate is not None
        sources.extend(self._context_sources(result.sources))

        floor_failure = self._validate_context_floor(result)
        if floor_failure is not None:
            return floor_failure
        structured = self._validate_or_repair(
            messages=messages,
            candidate=result.final_candidate,
            sources=tuple(sources),
            remaining_wall_clock_seconds=(
                self._wall_clock_budget_seconds - result.latency_ms / 1000
            ),
        )
        if isinstance(structured, InvestmentRequestFailure):
            return structured
        degraded = any(trace.status != "OK" for trace in result.tool_trace)
        return InvestmentAnswer(
            InvestmentResponseStatus.DEGRADED if degraded else InvestmentResponseStatus.OK,
            structured.answer,
            SourceValidator.select_declared(structured, tuple(sources)),
        )

    def _exposure(self, user_id: UUID) -> ToolExposure:
        planner = ToolExposurePlanner(
            self._tool_catalog,
            self._tool_policy,
            account_id=user_id,
        )
        requested = (
            self._tool_catalog.names
            if self._enabled_tool_names is None
            else tuple(
                name for name in self._tool_catalog.names if name in self._enabled_tool_names
            )
        )
        return planner.plan(requested)

    def _runtime_executor(
        self,
        tool_name: str,
        executor: FinancialToolExecutor,
        snapshot: PortfolioSnapshot,
        tool_session: _AuthorizedToolSession,
    ) -> Callable[[Mapping[str, object]], ToolExecutionResult]:
        def execute(arguments: Mapping[str, object]) -> ToolExecutionResult:
            tool_call = LLMToolCall("native-runtime-call", tool_name, arguments)
            validation_failure = InvestmentAgent._validate_tool_calls((tool_call,))
            if validation_failure is not None:
                return ToolExecutionResult(
                    "INVALID_ARGUMENTS",
                    error_code=validation_failure.code.value,
                )
            needs_market_context = (
                tool_name == CURRENT_QUOTE_TOOL_NAME
                and arguments.get("request_purpose") == "DISCRETIONARY_CURRENT_RISK_ACTION"
            )
            required_names = (
                (tool_name, MARKET_CONTEXT_TOOL_NAME) if needs_market_context else (tool_name,)
            )
            if not tool_session.reserve(required_names):
                return ToolExecutionResult(
                    "REQUIRED_CONTEXT_UNAUTHORIZED",
                    error_code="REQUIRED_CONTEXT_UNAUTHORIZED",
                )
            try:
                execution = executor.execute(tool_call)
            except InvalidFinancialToolResult:
                return ToolExecutionResult(
                    "INVALID_ARGUMENTS",
                    error_code=InvestmentFailureCode.INVALID_TOOL_CALL.value,
                )
            message, source = self._format_tool_execution(execution, snapshot)
            assert message.content is not None
            payload = json.loads(message.content)
            status = str(payload.pop("status"))
            source_mapping = self._source_mapping(source)
            related_calls: tuple[ToolExecutionRecord, ...] = ()
            if needs_market_context:
                required_call = LLMToolCall(
                    "required-market-context",
                    MARKET_CONTEXT_TOOL_NAME,
                    {},
                )
                required_execution = executor.execute(required_call)
                required_message, required_source = self._format_tool_execution(
                    required_execution,
                    snapshot,
                )
                assert required_message.content is not None
                required_payload = json.loads(required_message.content)
                payload["required_market_context"] = required_payload
                required_source_mapping = self._source_mapping(required_source)
                related_calls = (
                    ToolExecutionRecord(
                        MARKET_CONTEXT_TOOL_NAME,
                        {},
                        str(required_payload["status"]),
                        sources=(required_source_mapping,),
                    ),
                )
                if required_payload["status"] != "OK":
                    status = "DEGRADED"
            return ToolExecutionResult(
                status,
                payload,
                sources=(source_mapping,),
                related_calls=related_calls,
            )

        return execute

    @staticmethod
    def _format_tool_execution(
        execution: FinancialToolExecution,
        snapshot: PortfolioSnapshot,
    ) -> tuple[LLMMessage, ContextSource]:
        call = execution.tool_call
        if call.name == CURRENT_QUOTE_TOOL_NAME:
            result = execution.result
            assert isinstance(result, MarketDataResult)
            return InvestmentAgent._quote_tool_result(call, result, snapshot)  # type: ignore[arg-type]
        if call.name == RECENT_PRICE_HISTORY_TOOL_NAME:
            result = execution.result
            assert isinstance(result, MarketDataResult)
            return InvestmentAgent._history_tool_result(call, result)  # type: ignore[arg-type]
        if call.name == RECENT_NEWS_TOOL_NAME:
            result = execution.result
            assert isinstance(result, NewsResult)
            return InvestmentAgent._news_tool_result(call, result)
        result = execution.result
        assert isinstance(result, MarketDataResult)
        return InvestmentAgent._market_context_tool_result(call, result)  # type: ignore[arg-type]

    @staticmethod
    def _source_mapping(source: ContextSource) -> Mapping[str, object]:
        return {
            "type": source.type.value,
            "status": source.status,
            "ticker": source.ticker,
            "provider": source.provider,
            "feed": source.feed,
            "market_timestamp": (
                source.market_timestamp.isoformat() if source.market_timestamp else None
            ),
            "fetched_at": source.fetched_at.isoformat() if source.fetched_at else None,
        }

    @classmethod
    def _context_sources(
        cls,
        values: tuple[Mapping[str, object], ...],
    ) -> tuple[ContextSource, ...]:
        return tuple(cls._context_source(value) for value in values)

    @staticmethod
    def _context_source(value: Mapping[str, object]) -> ContextSource:
        return ContextSource(
            type=ContextSourceType(str(value["type"])),
            status=str(value["status"]),
            ticker=_optional_string(value.get("ticker")),
            provider=_optional_string(value.get("provider")),
            feed=_optional_string(value.get("feed")),
            market_timestamp=_optional_datetime(value.get("market_timestamp")),
            fetched_at=_optional_datetime(value.get("fetched_at")),
        )

    @staticmethod
    def _validate_context_floor(
        result: AgentRunResult,
    ) -> InvestmentRequestFailure | None:
        needs_market_context = any(
            trace.name == CURRENT_QUOTE_TOOL_NAME
            and trace.arguments.get("request_purpose") == "DISCRETIONARY_CURRENT_RISK_ACTION"
            for trace in result.tool_trace
        )
        has_market_context = any(
            source.get("type") == ContextSourceType.MARKET_CONTEXT.value
            for source in result.sources
        )
        if needs_market_context and not has_market_context:
            return InvestmentRequestFailure(
                InvestmentFailureCode.LLM_INVALID_PROVIDER_RESPONSE,
                "当前风险动作判断缺少必要 Market Context",
            )
        return None

    def _validate_or_repair(
        self,
        *,
        messages: tuple[LLMMessage, ...],
        candidate: str,
        sources: tuple[ContextSource, ...],
        remaining_wall_clock_seconds: float,
    ) -> StructuredInvestmentAnswer | InvestmentRequestFailure:
        answer, error = SourceValidator.evaluate(candidate, sources)
        if error is None:
            assert answer is not None
            return answer
        repair_payload = InvestmentAgent._build_structured_repair_instruction(error)
        if remaining_wall_clock_seconds <= 0:
            return InvestmentRequestFailure(
                InvestmentFailureCode.LLM_PROVIDER_UNAVAILABLE,
                "Agent Runtime 无法形成有效回答",
            )
        repair_result = self._runtime.run(
            AgentRunRequest(
                (
                    *messages,
                    LLMMessage(LLMRole.ASSISTANT, candidate),
                    LLMMessage(
                        LLMRole.USER,
                        json.dumps(repair_payload, ensure_ascii=False, sort_keys=True),
                    ),
                ),
                (),
                AgentRunBudget(1, 0, remaining_wall_clock_seconds),
                LLMResponseFormat.JSON_OBJECT,
            )
        )
        failure = self._runtime_failure(repair_result)
        if failure is not None:
            return failure
        assert repair_result.final_candidate is not None
        repaired, remaining_error = SourceValidator.evaluate(
            repair_result.final_candidate,
            sources,
        )
        if remaining_error is not None:
            return InvestmentRequestFailure(
                InvestmentFailureCode.LLM_INVALID_PROVIDER_RESPONSE,
                "LLM Final Response 在一次 Repair 后仍违反 Structured Source Contract",
            )
        assert repaired is not None
        return repaired

    @staticmethod
    def _runtime_failure(result: AgentRunResult) -> InvestmentRequestFailure | None:
        if result.status is AgentRunStatus.COMPLETED:
            return None
        code_by_status = {
            LLMStatus.INVALID_REQUEST: InvestmentFailureCode.LLM_INVALID_REQUEST,
            LLMStatus.AUTHENTICATION_FAILED: (InvestmentFailureCode.LLM_AUTHENTICATION_FAILED),
            LLMStatus.RATE_LIMITED: InvestmentFailureCode.LLM_RATE_LIMITED,
            LLMStatus.PROVIDER_UNAVAILABLE: (InvestmentFailureCode.LLM_PROVIDER_UNAVAILABLE),
            LLMStatus.INVALID_PROVIDER_RESPONSE: (
                InvestmentFailureCode.LLM_INVALID_PROVIDER_RESPONSE
            ),
        }
        if result.llm_status is not None and result.llm_status is not LLMStatus.OK:
            code = code_by_status[result.llm_status]
        elif result.failure_code == "TOOL_CALL_BUDGET_EXCEEDED":
            code = InvestmentFailureCode.TOOL_CALL_LIMIT_EXCEEDED
        else:
            code = InvestmentFailureCode.LLM_PROVIDER_UNAVAILABLE
        LOGGER.warning(
            "native_investment_agent_runtime_failed",
            extra={"failure_code": result.failure_code, "runtime_status": result.status.value},
        )
        return InvestmentRequestFailure(code, "Agent Runtime 无法形成有效回答")


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    return datetime.fromisoformat(value)


type NativeInvestmentAgentResult = InvestmentAnswer | InvestmentRequestFailure

__all__ = ["NativeInvestmentAgent", "NativeInvestmentAgentResult"]
