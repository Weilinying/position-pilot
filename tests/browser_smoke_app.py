"""M7 Human Browser Smoke 使用的确定性本地应用。"""

from datetime import UTC, datetime
from decimal import Decimal
from time import sleep
from uuid import UUID

from position_pilot.application.errors import UserNotFound
from position_pilot.application.investment_agent import (
    ContextSource,
    ContextSourceType,
    InvestmentAnswer,
    InvestmentFailureCode,
    InvestmentRequestFailure,
    InvestmentResponseStatus,
)
from position_pilot.domain.portfolio import (
    CashBalance,
    PortfolioState,
    Position,
    PositionType,
)
from position_pilot.main import (
    app,
    get_investment_agent_dependency,
    get_portfolio_service_dependency,
)

USER_A = UUID("10000000-0000-4000-8000-000000000001")
USER_B = UUID("20000000-0000-4000-8000-000000000002")
SLOW_USER = UUID("30000000-0000-4000-8000-000000000003")
EMPTY_USER = UUID("40000000-0000-4000-8000-000000000004")
NOW = datetime(2026, 8, 29, 8, 0, tzinfo=UTC)


def _portfolio(user_id: UUID, *, ticker: str) -> PortfolioState:
    """创建包含双 Position Type 的稳定 Browser Fixture。"""

    return PortfolioState(
        user_id=user_id,
        cash=CashBalance(
            user_id=user_id,
            initial_cash=Decimal("10000.00000000"),
            available_cash=Decimal("5120.50000000"),
        ),
        positions=(
            Position(
                ticker=ticker,
                position_type=PositionType.LONG_TERM,
                shares=Decimal("10.00000000"),
                average_cost=Decimal("180.03500000"),
                cost_basis=Decimal("1800.35000000"),
            ),
            Position(
                ticker=ticker,
                position_type=PositionType.SWING,
                shares=Decimal("4.00000000"),
                average_cost=Decimal("210.08750000"),
                cost_basis=Decimal("840.35000000"),
            ),
        ),
        transaction_count=2,
    )


class BrowserSmokePortfolioService:
    """按 User ID 返回稳定 Portfolio，并提供一个可控延迟场景。"""

    def get_portfolio(self, user_id: UUID) -> PortfolioState:
        if user_id == EMPTY_USER:
            return PortfolioState(
                user_id=user_id,
                cash=CashBalance(
                    user_id=user_id,
                    initial_cash=Decimal("10000.00000000"),
                    available_cash=Decimal("10000.00000000"),
                ),
                positions=(),
                transaction_count=0,
            )
        if user_id == SLOW_USER:
            sleep(0.6)
            return _portfolio(user_id, ticker="SLOW")
        if user_id == USER_A:
            return _portfolio(user_id, ticker="GOOG")
        if user_id == USER_B:
            return _portfolio(user_id, ticker="NVDA")
        raise UserNotFound(user_id)


class BrowserSmokeInvestmentAgent:
    """按问题文本返回 OK、降级、失败、延迟与注入场景。"""

    def answer(
        self,
        user_id: UUID,
        question: str,
    ) -> InvestmentAnswer | InvestmentRequestFailure:
        if question == "FAIL_503":
            return InvestmentRequestFailure(
                InvestmentFailureCode.LLM_PROVIDER_UNAVAILABLE,
                "Controlled provider failure",
            )
        if question == "FAIL_422":
            return InvestmentRequestFailure(
                InvestmentFailureCode.INVALID_QUESTION,
                "Controlled invalid question",
            )
        if question == "ERROR_XSS":
            return InvestmentRequestFailure(
                InvestmentFailureCode.LLM_PROVIDER_UNAVAILABLE,
                '<img src=x onerror="window.__xssExecuted=true">',
            )
        if question == "SLOW_A":
            sleep(0.6)
            return InvestmentAnswer(
                InvestmentResponseStatus.OK,
                f"Delayed answer for {user_id}",
                (ContextSource(ContextSourceType.PORTFOLIO_SNAPSHOT, "OK"),),
            )
        if question == "DEGRADED":
            return InvestmentAnswer(
                InvestmentResponseStatus.DEGRADED,
                "当前报价不可用；该回答只使用已加载持仓。",
                (
                    ContextSource(ContextSourceType.PORTFOLIO_SNAPSHOT, "OK"),
                    ContextSource(
                        ContextSourceType.CURRENT_QUOTE,
                        "NO_DATA",
                        ticker="GOOG",
                    ),
                    ContextSource(
                        ContextSourceType.RECENT_NEWS,
                        "PROVIDER_UNAVAILABLE",
                        ticker="GOOG",
                    ),
                ),
            )
        if question == "XSS":
            return InvestmentAnswer(
                InvestmentResponseStatus.OK,
                '<img src=x onerror="window.__xssExecuted=true">',
                (
                    ContextSource(ContextSourceType.PORTFOLIO_SNAPSHOT, "OK"),
                    ContextSource(
                        ContextSourceType.CURRENT_QUOTE,
                        "OK",
                        ticker="GOOG",
                        provider="<script>window.__xssExecuted=true</script>",
                        feed='<img src=x onerror="window.__xssExecuted=true">',
                        market_timestamp=NOW,
                        fetched_at=NOW,
                    ),
                ),
            )
        return InvestmentAnswer(
            InvestmentResponseStatus.OK,
            "基于当前长期仓与波段仓的回答。",
            (
                ContextSource(ContextSourceType.PORTFOLIO_SNAPSHOT, "OK"),
                ContextSource(
                    ContextSourceType.CURRENT_QUOTE,
                    "OK",
                    ticker="GOOG",
                    provider="ALPACA",
                    feed="IEX",
                    market_timestamp=NOW,
                    fetched_at=NOW,
                ),
            ),
        )


app.dependency_overrides[get_portfolio_service_dependency] = BrowserSmokePortfolioService
app.dependency_overrides[get_investment_agent_dependency] = BrowserSmokeInvestmentAgent
