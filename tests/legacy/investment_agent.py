"""冻结的旧手写 Agent Loop，仅用于历史 Characterization 与 Spike 对照。"""

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from time import monotonic
from typing import cast
from uuid import UUID

from position_pilot.application.investment_agent import (
    BASE_SYSTEM_PROMPT,
    CONTEXT_TOOLS,
    MAX_QUESTION_LENGTH,
    InvestmentAgentResult,
    InvestmentAnswer,
    InvestmentFailureCode,
    InvestmentRequestFailure,
    InvestmentResponseStatus,
    MarketContextReader,
    MarketDataReader,
    PortfolioContextReader,
    QuoteRequestPurpose,
    RecentNewsReader,
)
from position_pilot.application.investment_answer import (
    InvalidStructuredAnswer,
    StructuredInvestmentAnswer,
    UnresolvedSourceReference,
    structured_answer_schema,
    structured_repair_instruction,
)
from position_pilot.application.investment_context import (
    M5_CONTEXT_CAPABILITIES,
    PortfolioSnapshot,
    m3_decision_context,
    m3_response_contract,
)
from position_pilot.application.investment_context_builder import InvestmentContextBuilder
from position_pilot.application.investment_routing import ContextSelectionTrace
from position_pilot.application.investment_tool_executor import (
    CURRENT_QUOTE_TOOL_NAME as CURRENT_QUOTE_TOOL_NAME,
)
from position_pilot.application.investment_tool_executor import (
    MARKET_CONTEXT_TOOL_NAME as MARKET_CONTEXT_TOOL_NAME,
)
from position_pilot.application.investment_tool_executor import (
    RECENT_NEWS_TOOL_NAME as RECENT_NEWS_TOOL_NAME,
)
from position_pilot.application.investment_tool_executor import (
    RECENT_PRICE_HISTORY_TOOL_NAME as RECENT_PRICE_HISTORY_TOOL_NAME,
)
from position_pilot.application.investment_tool_executor import (
    FinancialToolExecutor,
    InvalidFinancialToolResult,
)
from position_pilot.application.investment_tool_results import (
    history_tool_result,
    market_context_tool_result,
    news_tool_result,
    quote_tool_result,
    validate_financial_tool_call,
)
from position_pilot.application.llm import (
    LLMMessage,
    LLMProvider,
    LLMResponseFormat,
    LLMResult,
    LLMRole,
    LLMStatus,
    LLMToolCall,
)
from position_pilot.application.source_registry import (
    ContextSource as ContextSource,
)
from position_pilot.application.source_registry import (
    ContextSourceType as ContextSourceType,
)
from position_pilot.application.source_registry import (
    SourceValidator,
)
from position_pilot.application.tool_catalog import (
    DescriptorToolProvider,
    StaticToolAccessPolicy,
    ToolCatalog,
    ToolCatalogError,
    ToolExposurePlanner,
    current_financial_tool_descriptors,
)
from position_pilot.domain.market_context import (
    MarketRegimeContext,
)
from position_pilot.domain.market_data import (
    HistoricalBars,
    MarketDataResult,
    MarketDataStatus,
    MarketQuote,
)
from position_pilot.domain.news import NewsResult, NewsStatus, RecentNews

LOGGER = logging.getLogger(__name__)
MAX_TOOL_CALLS_PER_ROUND = 4


LEGACY_AMOUNT_ANALYSIS_PROMPT = "\n".join(
    (
        (
            "普通投资分析、加仓建议和资金分配按用户明确金额表达，不要求先查询或确认碎股权限；"
            "不得因权限 UNKNOWN 拒绝分析，也不得擅自提高本轮预算。"
        ),
        (
            "用户明确说明账户支持碎股时可作为本轮条件使用；只有用户明确询问券商账户权限时才"
            "核验，缺少依据则保持 UNKNOWN。"
        ),
        (
            "executable_purchase_quantity=UNKNOWN 只限制实际可执行订单结论。用户明确要求股数时，"
            "只有 Application 提供了基于本轮预算与可靠 Quote 的确定性理论股数，才可引用并必须"
            "标明不代表账户实际可执行数量。"
        ),
    )
)


SYSTEM_PROMPT = BASE_SYSTEM_PROMPT + "\n" + LEGACY_AMOUNT_ANALYSIS_PROMPT


class InvestmentAgent:
    """协调 Portfolio Snapshot、Native Tool Call 与 Final Response。"""

    def __init__(
        self,
        portfolio_reader: PortfolioContextReader,
        market_data: MarketDataReader,
        llm_provider: LLMProvider,
        *,
        news: RecentNewsReader,
        market_context: MarketContextReader,
        clock: Callable[[], datetime] | None = None,
        enabled_tool_names: frozenset[str] | None = None,
    ) -> None:
        self._portfolio_reader = portfolio_reader
        self._market_data = market_data
        self._llm_provider = llm_provider
        self._news = news
        self._market_context = market_context
        self._clock = clock or (lambda: datetime.now(UTC))
        self._tool_catalog = ToolCatalog(
            (DescriptorToolProvider(current_financial_tool_descriptors(CONTEXT_TOOLS)),)
        )
        self._enabled_tool_names = enabled_tool_names
        self._tool_policy = StaticToolAccessPolicy(enabled_names=enabled_tool_names)

    def answer(self, user_id: UUID, question: str) -> InvestmentAgentResult:
        """执行最多一个 Tool Round，并返回 Answer 或明确 Request Failure。"""

        normalized_question = question.strip() if isinstance(question, str) else ""
        if not normalized_question or len(normalized_question) > MAX_QUESTION_LENGTH:
            return InvestmentRequestFailure(
                InvestmentFailureCode.INVALID_QUESTION,
                f"question 必须包含 1 到 {MAX_QUESTION_LENGTH} 个字符",
            )

        started_at = monotonic()
        portfolio_context = self._portfolio_reader.get_investment_context(user_id)
        snapshot = PortfolioSnapshot.from_context(portfolio_context)
        sources: list[ContextSource] = [
            ContextSource(
                ContextSourceType.PORTFOLIO_SNAPSHOT,
                InvestmentResponseStatus.OK.value,
            )
        ]
        initial_messages = InvestmentContextBuilder(SYSTEM_PROMPT).build(
            portfolio_context,
            normalized_question,
        )
        exposure_planner = ToolExposurePlanner(
            self._tool_catalog,
            self._tool_policy,
            account_id=user_id,
        )
        requested_tool_names = (
            self._tool_catalog.names
            if self._enabled_tool_names is None
            else tuple(
                name for name in self._tool_catalog.names if name in self._enabled_tool_names
            )
        )
        exposed_tools = exposure_planner.plan(requested_tool_names)
        LOGGER.info(
            "investment_agent_context_ready",
            extra={
                "position_count": len(snapshot.positions),
                "tool_count": len(exposed_tools.definitions),
            },
        )

        routing_started_at = monotonic()
        first_result = self._llm_provider.complete(
            initial_messages,
            tools=exposed_tools.definitions,
            response_format=LLMResponseFormat.TEXT,
        )
        first_failure = self._from_llm_failure(first_result)
        if first_failure is not None:
            self._log_failure(first_failure, started_at)
            return first_failure
        first_message = self._completion_message(first_result)

        tool_call_failure = self._validate_tool_calls(first_message.tool_calls)
        if tool_call_failure is not None:
            self._log_failure(tool_call_failure, started_at)
            return tool_call_failure
        try:
            call_exposure = exposure_planner.plan_calls(first_message.tool_calls)
        except ToolCatalogError as error:
            failure_code = (
                InvestmentFailureCode.TOOL_CALL_LIMIT_EXCEEDED
                if str(error).startswith("TOOL_CALL_LIMIT_EXCEEDED")
                else InvestmentFailureCode.INVALID_TOOL_CALL
            )
            floor_failure = InvestmentRequestFailure(failure_code, str(error))
            self._log_failure(floor_failure, started_at)
            return floor_failure
        required_tool_calls = call_exposure.required_tool_calls
        effective_tool_calls = call_exposure.effective_tool_calls
        effective_first_message = (
            first_message
            if not required_tool_calls
            else LLMMessage(
                LLMRole.ASSISTANT,
                first_message.content,
                effective_tool_calls,
            )
        )
        selection_trace = ContextSelectionTrace.from_tool_calls(
            snapshot=snapshot,
            available_tools=tuple(tool.name for tool in exposed_tools.definitions),
            model_tool_calls=first_message.tool_calls,
            required_tool_calls=required_tool_calls,
        )
        LOGGER.info(
            "investment_agent_context_selected",
            extra=selection_trace.as_log_extra(
                routing_latency_ms=round((monotonic() - routing_started_at) * 1000, 2)
            ),
        )

        if not effective_tool_calls:
            validated_answer = self._validate_or_repair(
                messages_before_final=initial_messages,
                final_message=first_message,
                sources=tuple(sources),
            )
            if isinstance(validated_answer, InvestmentRequestFailure):
                self._log_failure(validated_answer, started_at)
                return validated_answer
            answer = InvestmentAnswer(
                InvestmentResponseStatus.OK,
                validated_answer.answer,
                self._select_declared_sources(validated_answer, tuple(sources)),
            )
            self._log_success(answer, started_at, tool_call_count=0)
            return answer

        tool_messages: list[LLMMessage] = []
        tool_executor = FinancialToolExecutor(
            self._market_data,
            self._news,
            self._market_context,
            clock=self._clock,
        )
        degraded = False
        for tool_call in effective_tool_calls:
            try:
                execution = tool_executor.execute(tool_call)
            except InvalidFinancialToolResult as error:
                failure = InvestmentRequestFailure(
                    InvestmentFailureCode.INVALID_TOOL_CALL,
                    str(error),
                )
                self._log_failure(failure, started_at)
                return failure
            if tool_call.name == MARKET_CONTEXT_TOOL_NAME:
                market_context_result = cast(
                    MarketDataResult[MarketRegimeContext], execution.result
                )
                tool_message, source = self._market_context_tool_result(
                    tool_call,
                    market_context_result,
                )
                tool_succeeded = market_context_result.status is MarketDataStatus.OK
                tool_status_value = market_context_result.status.value
            elif tool_call.name == CURRENT_QUOTE_TOOL_NAME:
                market_result = cast(MarketDataResult[MarketQuote], execution.result)
                tool_message, source = self._quote_tool_result(
                    tool_call,
                    market_result,
                    snapshot,
                )
                tool_succeeded = market_result.status is MarketDataStatus.OK
                tool_status_value = market_result.status.value
            elif tool_call.name == RECENT_PRICE_HISTORY_TOOL_NAME:
                historical_result = cast(MarketDataResult[HistoricalBars], execution.result)
                tool_message, source = self._history_tool_result(
                    tool_call,
                    historical_result,
                )
                tool_succeeded = historical_result.status is MarketDataStatus.OK
                tool_status_value = historical_result.status.value
            else:
                news_result = cast(NewsResult[RecentNews], execution.result)
                tool_message, source = self._news_tool_result(tool_call, news_result)
                tool_succeeded = news_result.status is NewsStatus.OK
                tool_status_value = news_result.status.value
            tool_messages.append(tool_message)
            if execution.is_duplicate:
                LOGGER.info(
                    "investment_agent_tool_deduplicated",
                    extra={
                        "tool_name": tool_call.name,
                        "ticker": source.ticker,
                    },
                )
            else:
                sources.append(source)
                degraded = degraded or not tool_succeeded
                LOGGER.info(
                    "investment_agent_tool_completed",
                    extra={
                        "tool_name": tool_call.name,
                        "ticker": source.ticker,
                        "tool_status": tool_status_value,
                    },
                )

        final_result = self._llm_provider.complete(
            (*initial_messages, effective_first_message, *tool_messages),
            tools=(),
            response_format=LLMResponseFormat.JSON_OBJECT,
        )
        final_failure = self._from_llm_failure(final_result)
        if final_failure is not None:
            self._log_failure(final_failure, started_at)
            return final_failure
        final_message = self._completion_message(final_result)
        if final_message.tool_calls:
            failure = InvestmentRequestFailure(
                InvestmentFailureCode.TOOL_ROUND_LIMIT_EXCEEDED,
                "Tool Result 返回后必须生成 Final Response",
            )
            self._log_failure(failure, started_at)
            return failure

        validated_answer = self._validate_or_repair(
            messages_before_final=(
                *initial_messages,
                effective_first_message,
                *tool_messages,
            ),
            final_message=final_message,
            sources=tuple(sources),
        )
        if isinstance(validated_answer, InvestmentRequestFailure):
            self._log_failure(validated_answer, started_at)
            return validated_answer

        answer = InvestmentAnswer(
            InvestmentResponseStatus.DEGRADED if degraded else InvestmentResponseStatus.OK,
            validated_answer.answer,
            self._select_declared_sources(validated_answer, tuple(sources)),
        )
        self._log_success(
            answer,
            started_at,
            tool_call_count=tool_executor.unique_execution_count,
        )
        return answer

    def _validate_or_repair(
        self,
        *,
        messages_before_final: tuple[LLMMessage, ...],
        final_message: LLMMessage,
        sources: tuple[ContextSource, ...],
    ) -> StructuredInvestmentAnswer | InvestmentRequestFailure:
        """验证 Structured Sources，并最多执行一次 No-Tool Repair。"""

        content = self._require_final_content(final_message)
        structured_answer, validation_error = self._evaluate_structured_response(content, sources)
        if validation_error is None:
            assert structured_answer is not None
            return structured_answer

        LOGGER.warning(
            "investment_agent_source_reference_validation_failed",
            extra={
                "repair_attempt": 0,
                "violation_code": self._structured_error_code(validation_error),
            },
        )
        repair_payload = self._build_structured_repair_instruction(validation_error)
        repair_message = LLMMessage(
            LLMRole.USER,
            json.dumps(
                repair_payload,
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
        repair_result = self._llm_provider.complete(
            (*messages_before_final, final_message, repair_message),
            tools=(),
            response_format=LLMResponseFormat.JSON_OBJECT,
        )
        repair_failure = self._from_llm_failure(repair_result)
        if repair_failure is not None:
            return repair_failure
        repaired_message = self._completion_message(repair_result)
        if repaired_message.tool_calls:
            return InvestmentRequestFailure(
                InvestmentFailureCode.LLM_INVALID_PROVIDER_RESPONSE,
                "Response Repair 不得请求 Tool",
            )

        repaired_content = self._require_final_content(repaired_message)
        repaired_answer, remaining_error = self._evaluate_structured_response(
            repaired_content, sources
        )
        if remaining_error is not None:
            LOGGER.warning(
                "investment_agent_source_reference_validation_failed",
                extra={
                    "repair_attempt": 1,
                    "violation_code": self._structured_error_code(remaining_error),
                },
            )
            return InvestmentRequestFailure(
                InvestmentFailureCode.LLM_INVALID_PROVIDER_RESPONSE,
                "LLM Final Response 在一次 Repair 后仍违反 Structured Source Contract",
            )
        LOGGER.info("investment_agent_response_repaired", extra={"repair_attempt": 1})
        assert repaired_answer is not None
        return repaired_answer

    @staticmethod
    def _evaluate_structured_response(
        content: str,
        sources: tuple[ContextSource, ...],
    ) -> tuple[
        StructuredInvestmentAnswer | None,
        InvalidStructuredAnswer | UnresolvedSourceReference | None,
    ]:
        """只解析外层 Contract，并验证模型声明的 Context 是否真实存在。"""

        return SourceValidator.evaluate(content, sources)

    @staticmethod
    def _structured_error_code(
        error: InvalidStructuredAnswer | UnresolvedSourceReference,
    ) -> str:
        if isinstance(error, InvalidStructuredAnswer):
            return "INVALID_STRUCTURED_ANSWER"
        return "UNRESOLVED_SOURCE_REFERENCE"

    _build_structured_repair_instruction = staticmethod(structured_repair_instruction)

    @staticmethod
    def _select_declared_sources(
        answer: StructuredInvestmentAnswer,
        sources: tuple[ContextSource, ...],
    ) -> tuple[ContextSource, ...]:
        """返回声明的成功 Context，并保留失败 Tool Attempt 的既有可观测性。"""

        return SourceValidator.select_declared(answer, sources)

    @staticmethod
    def _initial_messages(
        snapshot: PortfolioSnapshot,
        question: str,
    ) -> tuple[LLMMessage, ...]:
        """兼容既有测试的 Context Builder 委托入口。"""

        content = json.dumps(
            {
                "question": question,
                "context_capabilities": M5_CONTEXT_CAPABILITIES.as_dict(),
                "decision_context": m3_decision_context(),
                "portfolio_snapshot": snapshot.as_dict(),
                "available_source_reference": {"type": "PORTFOLIO_SNAPSHOT"},
                "response_contract": m3_response_contract(),
                "structured_answer_schema": structured_answer_schema(),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return (
            LLMMessage(LLMRole.SYSTEM, SYSTEM_PROMPT),
            LLMMessage(LLMRole.USER, content),
        )

    @staticmethod
    def _validate_tool_calls(
        tool_calls: tuple[LLMToolCall, ...],
    ) -> InvestmentRequestFailure | None:
        if len(tool_calls) > MAX_TOOL_CALLS_PER_ROUND:
            return InvestmentRequestFailure(
                InvestmentFailureCode.TOOL_CALL_LIMIT_EXCEEDED,
                f"每个 Tool Round 最多允许 {MAX_TOOL_CALLS_PER_ROUND} 个调用",
            )
        for tool_call in tool_calls:
            failure = validate_financial_tool_call(tool_call)
            if failure is not None:
                return failure
        return None

    @staticmethod
    def _required_context_floor(
        model_tool_calls: tuple[LLMToolCall, ...],
    ) -> tuple[LLMToolCall, ...]:
        """只补足 LLM 已声明的 discretionary current risk action 所需 Market Context。"""

        if any(call.name == MARKET_CONTEXT_TOOL_NAME for call in model_tool_calls):
            return ()
        requires_market_context = any(
            call.name == CURRENT_QUOTE_TOOL_NAME
            and call.arguments.get("request_purpose")
            == QuoteRequestPurpose.DISCRETIONARY_CURRENT_RISK_ACTION.value
            for call in model_tool_calls
        )
        if not requires_market_context:
            return ()
        existing_ids = {call.id for call in model_tool_calls}
        call_id = "required-market-context"
        suffix = 1
        while call_id in existing_ids:
            call_id = f"required-market-context-{suffix}"
            suffix += 1
        return (LLMToolCall(call_id, MARKET_CONTEXT_TOOL_NAME, {}),)

    _quote_tool_result = staticmethod(quote_tool_result)

    _history_tool_result = staticmethod(history_tool_result)

    _market_context_tool_result = staticmethod(market_context_tool_result)

    _news_tool_result = staticmethod(news_tool_result)

    @staticmethod
    def _from_llm_failure(result: LLMResult) -> InvestmentRequestFailure | None:
        if result.status is LLMStatus.OK:
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
        return InvestmentRequestFailure(
            code_by_status[result.status],
            result.error_message or "LLM Provider 调用失败",
        )

    @staticmethod
    def _completion_message(result: LLMResult) -> LLMMessage:
        assert result.completion is not None
        return result.completion.message

    @staticmethod
    def _require_final_content(message: LLMMessage) -> str:
        if message.content is None:
            # LLMMessage 已保证无 Tool Call 时必须存在 content，此分支只保护未来修改。
            raise RuntimeError("Final Response 缺少 content")
        return message.content

    @staticmethod
    def _log_success(
        answer: InvestmentAnswer,
        started_at: float,
        *,
        tool_call_count: int,
    ) -> None:
        LOGGER.info(
            "investment_agent_completed",
            extra={
                "response_status": answer.status.value,
                "tool_call_count": tool_call_count,
                "latency_ms": round((monotonic() - started_at) * 1000, 2),
            },
        )

    @staticmethod
    def _log_failure(failure: InvestmentRequestFailure, started_at: float) -> None:
        LOGGER.warning(
            "investment_agent_failed",
            extra={
                "failure_code": failure.code.value,
                "latency_ms": round((monotonic() - started_at) * 1000, 2),
            },
        )
