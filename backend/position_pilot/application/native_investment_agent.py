"""使用 Native AgentRuntime 的 Production Investment Agent Facade。"""

import json
import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from uuid import UUID, uuid4

from position_pilot.application.agent_runtime import (
    AgentRunBudget,
    AgentRunRequest,
    AgentRunResult,
    AgentRunStatus,
    AgentRuntime,
    AgentToolBinding,
    AgentToolBudgetExceeded,
)
from position_pilot.application.conversation_citations import (
    CitationValidationError,
    validate_citations,
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
from position_pilot.domain.market_context import MARKET_PROXY_TICKER
from position_pilot.domain.market_data import MarketDataResult
from position_pilot.domain.news import NewsResult

LOGGER = logging.getLogger(__name__)
DEFAULT_MODEL_REQUEST_BUDGET = 3
DEFAULT_TOOL_CALL_BUDGET = 4
DEFAULT_WALL_CLOCK_BUDGET_SECONDS = 60.0


class _AuthorizedToolSession:
    """在 Provider 调用前统一执行本轮 Tool 授权与预算预留。"""

    def __init__(self, allowed_names: frozenset[str], call_budget: int) -> None:
        self._allowed_names = allowed_names
        self._call_budget = call_budget
        self._used_calls = 0
        self._explicit_market_context_observed = False
        self._automatic_market_context_credit = False
        self._market_context_source: Mapping[str, object] | None = None

    @property
    def explicit_market_context_observed(self) -> bool:
        """标识模型本轮是否已明确调用 Market Context。"""

        return self._explicit_market_context_observed

    def note_explicit_market_context(self) -> None:
        """记录模型已为 Market Context 单独消耗一次 Tool Call。"""

        self._explicit_market_context_observed = True

    def note_automatic_market_context(self) -> None:
        """标记自动获取已占预算，可供随后首次显式调用复用。"""

        self._automatic_market_context_credit = True

    def market_context_source(self, source: ContextSource) -> Mapping[str, object]:
        """同轮复用 Market Context 的 Source 身份，包括失败状态。"""

        if self._market_context_source is None:
            self._market_context_source = NativeInvestmentAgent._source_mapping(source)
        return self._market_context_source

    def reserve(self, names: tuple[str, ...], *, reuse_automatic_market: bool = False) -> bool:
        """原子预留一组实际调用，避免复合 Tool 只计算外层调用。"""

        if any(name not in self._allowed_names for name in names):
            return False
        reuse = (
            reuse_automatic_market
            and names == (MARKET_CONTEXT_TOOL_NAME,)
            and self._automatic_market_context_credit
        )
        charge = len(names) - int(reuse)
        if self._used_calls + charge > self._call_budget:
            raise AgentToolBudgetExceeded
        self._used_calls += charge
        if reuse:
            self._automatic_market_context_credit = False
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

        return self._answer(user_id, question, conversation_history=())

    def answer_with_history(
        self,
        user_id: UUID,
        question: str,
        conversation_history: tuple[LLMMessage, ...],
    ) -> InvestmentAnswer | InvestmentRequestFailure:
        """使用 Application 筛选后的用户可见历史执行一次 Native Run。"""

        return self._answer(
            user_id,
            question,
            conversation_history=conversation_history,
            citation_mode=True,
        )

    def _answer(
        self,
        user_id: UUID,
        question: str,
        *,
        conversation_history: tuple[LLMMessage, ...],
        citation_mode: bool = False,
    ) -> InvestmentAnswer | InvestmentRequestFailure:
        """共享单问与 Thread Ask 流程，不让 Runtime 持有 Conversation 状态。"""

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
        prompt = SYSTEM_PROMPT + (
            "\n在 Native Tool Loop 中，若 get_current_quote 使用 "
            "DISCRETIONARY_CURRENT_RISK_ACTION，本次 Quote Observation 的 "
            "required_market_context 已包含必要的 Market Context；不要为同一问题重复调用 "
            "get_market_context。若 required_market_context 未成功，须按失败状态保持 UNKNOWN。"
            "\n缺少已确认 Strategy、风险预算或交易计划时，仍须先基于已知 Portfolio、"
            "当前市场事实与已成功 Tool 结果完成条件式分析：说明哪些已知条件支持继续评估加仓，"
            "哪些风险或未知条件支持暂缓，并按已知 Position Type 区分分析。"
            "若加仓目的未确认，可比较 LONG_TERM 追加与 SWING 新仓的条件，"
            "但不得把假设分支说成用户已有仓位或已确认策略。"
            "随后只澄清会改变判断的关键个人条件；不得因缺少策略把整个判断退回给用户，"
            "也不得代用户创造目标仓位、价格触发条件或持久 Strategy。"
            "普通加仓分析涉及资金分配时按用户本轮预算的金额讨论，未提供预算不得自拟金额；"
            "账户 Cash 是 Ledger 事实，不等于用户本轮 Budget；没有本轮 Budget 时，"
            "不得把 Cash 数值充裕说成已满足个人加仓资金约束。"
            "不把碎股权限或实际可执行股数列为建议前置或关键澄清问题；"
            "只有用户明确询问购买股数、实际可执行数量或账户权限时，才按已有理论股数"
            "与可靠账户证据回答；理论股数不代表实际订单数量，缺乏执行证据时保持 UNKNOWN。"
            "\n现价与平均成本的关系仅在本轮可靠报价已提供时用于描述当前盈亏，"
            "不证明用户的长期投资判断或 Thesis 正确；Portfolio 成本和 Position Type 不能证明"
            "当前浮盈、浮亏或个人风险承受度，缺少依据保持 UNKNOWN；"
            "示例条件须明确假设，不能冒充用户当前事实。"
            "持仓成本占比的分母不含 Cash，不等于全部资产或市值占比；"
            "单一标的成本占比已为 100% 时，继续买入不能使该口径占比进一步提高，"
            "只能在有依据时讨论绝对资金敞口增加，不臆造个人集中度上限。"
        )
        if citation_mode:
            prompt += (
                "\nConversation 历史 Assistant Answer 只用于理解指代与当时判断；"
                "复述须保留原判断的条件、假设和未决状态，不能强化成先前已作出的买卖或观望决定。"
                "历史回答不能替代本轮 Portfolio Snapshot、当前 confirmed Strategy 或市场事实；"
                "用户历史预算和意图更正只按未被后续消息覆盖的适用上下文使用。"
                "历史 Quote、News、Market Context 只代表当时证据。用户询问过去的"
                "投资结论现在是否仍成立或需要修改时，必须重新调用支撑该结论所需的"
                "当前 Quote、News 或 Market Context Tool，取得本轮证据后再比较；"
                "不得仅凭历史报价或旧回答断言结论未变。若所需 Tool 失败或不可用，"
                "明确说明尚未核实当前变化，仅基于本轮已知事实给条件式分析。"
                "\nConversation 回答中，凡引用本轮成功 Tool 结果，请在相关陈述附近使用"
                " [source:<source_id>]；source_id 只能复制 Tool Observation 的 sources 字段。"
                "PORTFOLIO_SNAPSHOT 没有 source_id：可以在 source_refs 声明它，"
                "但不要给 Portfolio 事实添加 [source:PORTFOLIO_SNAPSHOT]"
                " 或其他伪造的 inline Citation。"
                "不要编造 URL；Tool Observation 的 sources 只列本轮成功且可引用的"
                "外部来源。attempt_observations 记录调用状态和失败或空结果，"
                "不是 Source，不能写入 source_refs，也不能生成 inline Citation。"
                "只说明失败或空结果且未使用 Portfolio Facts 时，source_refs 必须是空数组 []。"
                "即使 Tool Observation 整体 status 为 DEGRADED，其中 sources 列出的"
                "成功来源仍可按需声明和引用。"
                "source_refs 仍按原结构声明。"
            )
        messages = InvestmentContextBuilder(prompt).build(
            portfolio_context,
            normalized_question,
            conversation_history=conversation_history,
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
                    citation_mode=citation_mode,
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
            citation_mode=citation_mode,
        )
        if isinstance(structured, InvestmentRequestFailure):
            return structured
        degraded = any(trace.status != "OK" for trace in result.tool_trace)
        return InvestmentAnswer(
            InvestmentResponseStatus.DEGRADED if degraded else InvestmentResponseStatus.OK,
            structured.answer,
            SourceValidator.select_declared(structured, tuple(sources)),
            result.warnings,
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
        *,
        citation_mode: bool,
    ) -> Callable[[Mapping[str, object]], ToolExecutionResult]:
        def execute(arguments: Mapping[str, object]) -> ToolExecutionResult:
            tool_call = LLMToolCall("native-runtime-call", tool_name, arguments)
            validation_failure = InvestmentAgent._validate_tool_calls((tool_call,))
            if validation_failure is not None:
                return ToolExecutionResult(
                    "INVALID_ARGUMENTS",
                    error_code=validation_failure.code.value,
                    provider_fetch_count=0,
                )
            needs_market_context = (
                tool_name == CURRENT_QUOTE_TOOL_NAME
                and arguments.get("request_purpose") == "DISCRETIONARY_CURRENT_RISK_ACTION"
            )
            auto_fetch_market_context = (
                needs_market_context and not tool_session.explicit_market_context_observed
            )
            required_names = (
                (tool_name, MARKET_CONTEXT_TOOL_NAME) if auto_fetch_market_context else (tool_name,)
            )
            if not tool_session.reserve(
                required_names,
                reuse_automatic_market=(tool_name == MARKET_CONTEXT_TOOL_NAME),
            ):
                return ToolExecutionResult(
                    "REQUIRED_CONTEXT_UNAUTHORIZED",
                    error_code="REQUIRED_CONTEXT_UNAUTHORIZED",
                    provider_fetch_count=0,
                )
            fetch_count_before = executor.provider_fetch_count
            try:
                execution = executor.execute(tool_call)
            except InvalidFinancialToolResult:
                return ToolExecutionResult(
                    "INVALID_ARGUMENTS",
                    error_code=InvestmentFailureCode.INVALID_TOOL_CALL.value,
                    provider_fetch_count=executor.provider_fetch_count - fetch_count_before,
                )
            except Exception:  # noqa: BLE001 - 保留已发生的 Provider 请求与明确失败状态。
                failed_sources: tuple[Mapping[str, object], ...] = ()
                if tool_name == MARKET_CONTEXT_TOOL_NAME:
                    tool_session.note_explicit_market_context()
                    failed_sources = (
                        tool_session.market_context_source(
                            ContextSource(
                                ContextSourceType.MARKET_CONTEXT,
                                "TOOL_FAILURE",
                                ticker=MARKET_PROXY_TICKER,
                            )
                        ),
                    )
                return ToolExecutionResult(
                    "TOOL_FAILURE",
                    error_code="TOOL_FAILURE",
                    sources=failed_sources,
                    provider_fetch_count=executor.provider_fetch_count - fetch_count_before,
                )
            provider_fetch_count = executor.provider_fetch_count - fetch_count_before
            if tool_name == MARKET_CONTEXT_TOOL_NAME:
                tool_session.note_explicit_market_context()
            message, source = self._format_tool_execution(execution, snapshot)
            assert message.content is not None
            payload = json.loads(message.content)
            status = str(payload.pop("status"))
            if tool_name == CURRENT_QUOTE_TOOL_NAME and status == "OK":
                # Quote 不提供账户执行能力；不把固定 UNKNOWN 伪装成行情派生事实。
                # 用户询问执行权限时仍由 Prompt 要求无证据保持未知，不从 Quote 推断。
                del payload["deterministic_derived_facts"]["executable_purchase_quantity"]
                # 旧 Runtime 保留冻结基线；Native 不要求普通分析报告无关的执行状态。
                contract = payload["response_contract"]
                del contract["required_purchase_execution_status"]
                contract["purchase_execution_status_reporting"] = (
                    "ONLY_WHEN_USER_ASKS_EXECUTABILITY_OR_ACCOUNT_PERMISSIONS"
                )
                contract["unknown_execution_status_blocks_analysis"] = False
                contract["price_above_cost_proves_investment_thesis"] = False
            observed_sources = self._observed_sources(execution, source, citation_mode)
            source_mappings = tuple(
                tool_session.market_context_source(item)
                if item.type is ContextSourceType.MARKET_CONTEXT
                else self._source_mapping(item)
                for item in observed_sources
            )
            related_calls: tuple[ToolExecutionRecord, ...] = ()
            if needs_market_context:
                required_call = LLMToolCall(
                    "required-market-context",
                    MARKET_CONTEXT_TOOL_NAME,
                    {},
                )
                required_fetch_count_before = executor.provider_fetch_count
                try:
                    required_execution = executor.execute(required_call)
                except Exception:  # noqa: BLE001 - 复合 Tool 保留 Quote 与 Market 失败审计。
                    failed_market = tool_session.market_context_source(
                        ContextSource(
                            ContextSourceType.MARKET_CONTEXT,
                            "TOOL_FAILURE",
                            ticker=MARKET_PROXY_TICKER,
                        )
                    )
                    payload["required_market_context"] = {
                        "status": "TOOL_FAILURE",
                        "error_code": "TOOL_FAILURE",
                    }
                    if auto_fetch_market_context:
                        tool_session.note_automatic_market_context()
                        related_calls = (
                            ToolExecutionRecord(
                                MARKET_CONTEXT_TOOL_NAME,
                                {},
                                "TOOL_FAILURE",
                                "TOOL_FAILURE",
                                (failed_market,),
                                executor.provider_fetch_count - required_fetch_count_before,
                            ),
                        )
                    return ToolExecutionResult(
                        "DEGRADED",
                        payload,
                        sources=source_mappings,
                        related_calls=related_calls,
                        provider_fetch_count=provider_fetch_count,
                    )
                required_provider_fetch_count = (
                    executor.provider_fetch_count - required_fetch_count_before
                )
                required_message, required_source = self._format_tool_execution(
                    required_execution,
                    snapshot,
                )
                assert required_message.content is not None
                required_payload = json.loads(required_message.content)
                payload["required_market_context"] = required_payload
                required_source_mapping = tool_session.market_context_source(required_source)
                if auto_fetch_market_context:
                    tool_session.note_automatic_market_context()
                    related_calls = (
                        ToolExecutionRecord(
                            MARKET_CONTEXT_TOOL_NAME,
                            {},
                            str(required_payload["status"]),
                            sources=(required_source_mapping,),
                            provider_fetch_count=required_provider_fetch_count,
                        ),
                    )
                if required_payload["status"] != "OK":
                    status = "DEGRADED"
            return ToolExecutionResult(
                status,
                payload,
                sources=source_mappings,
                related_calls=related_calls,
                provider_fetch_count=provider_fetch_count,
            )

        return execute

    @staticmethod
    def _observed_sources(
        execution: FinancialToolExecution,
        source: ContextSource,
        citation_mode: bool,
    ) -> tuple[ContextSource, ...]:
        """Conversation News 按文章建立可打开的来源身份。"""

        if not citation_mode or execution.tool_call.name != RECENT_NEWS_TOOL_NAME:
            return (source,)
        result = execution.result
        if not isinstance(result, NewsResult) or result.status.value != "OK":
            return (source,)
        recent_news = result.data
        assert recent_news is not None
        return tuple(
            ContextSource(
                type=ContextSourceType.RECENT_NEWS,
                status="OK",
                ticker=recent_news.ticker,
                provider=recent_news.provider,
                feed=article.source,
                market_timestamp=article.created_at,
                fetched_at=recent_news.fetched_at,
                url=article.url,
                title=article.headline,
                publisher=article.source,
                published_at=article.created_at,
                provider_reference=article.article_id,
            )
            for article in recent_news.articles
        )

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
            "source_id": str(source.source_id or uuid4()) if source.status == "OK" else None,
            "url": source.url,
            "title": source.title,
            "publisher": source.publisher,
            "published_at": source.published_at.isoformat() if source.published_at else None,
            "provider_reference": source.provider_reference,
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
            source_id=UUID(str(value["source_id"])) if value.get("source_id") else None,
            url=_optional_string(value.get("url")),
            title=_optional_string(value.get("title")),
            publisher=_optional_string(value.get("publisher")),
            published_at=_optional_datetime(value.get("published_at")),
            provider_reference=_optional_string(value.get("provider_reference")),
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
        citation_mode: bool,
    ) -> StructuredInvestmentAnswer | InvestmentRequestFailure:
        answer, error = SourceValidator.evaluate(candidate, sources)
        citation_error: CitationValidationError | None = None
        if error is None and citation_mode:
            assert answer is not None
            try:
                validate_citations(
                    answer.answer,
                    SourceValidator.select_declared(answer, sources),
                )
            except CitationValidationError as invalid:
                citation_error = invalid
        if error is None and citation_error is None:
            assert answer is not None
            return answer
        repair_payload = (
            InvestmentAgent._build_structured_repair_instruction(error)
            if error is not None
            else self._citation_repair_instruction(citation_error, sources)
        )
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
        if citation_mode:
            try:
                validate_citations(
                    repaired.answer,
                    SourceValidator.select_declared(repaired, sources),
                )
            except CitationValidationError:
                return InvestmentRequestFailure(
                    InvestmentFailureCode.LLM_INVALID_PROVIDER_RESPONSE,
                    "LLM Final Response 在一次 Repair 后仍违反 Citation Contract",
                )
        return repaired

    @staticmethod
    def _citation_repair_instruction(
        error: CitationValidationError | None,
        sources: tuple[ContextSource, ...],
    ) -> dict[str, object]:
        """Repair 只提供本轮已观察的来源 ID，不重新获取外部数据。"""

        return {
            "task": "REPAIR_FINAL_RESPONSE_CITATIONS",
            "validation_error": str(error),
            "observed_successful_source_ids": [
                str(source.source_id)
                for source in sources
                if source.status == "OK" and source.source_id is not None
            ],
            "instructions": [
                "保留符合原 Contract 的 answer 与 source_refs JSON 结构。",
                "只在实际引用的陈述附近使用 [source:<source_id>]。",
                "PORTFOLIO_SNAPSHOT 没有 source_id；只在 source_refs 中声明，"
                "不要写 [source:PORTFOLIO_SNAPSHOT]。",
                "仅使用列出的成功来源 ID，不编造 URL，不引用失败来源。",
                "不得请求 Tool。",
            ],
        }

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
