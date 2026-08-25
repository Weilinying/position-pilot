"""FastAPI 应用入口。"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from position_pilot.application.errors import UserNotFound
from position_pilot.application.investment_agent import (
    MAX_QUESTION_LENGTH,
    ContextSource,
    ContextSourceType,
    InvestmentAgent,
    InvestmentAnswer,
    InvestmentFailureCode,
    InvestmentRequestFailure,
    InvestmentResponseStatus,
)
from position_pilot.application.portfolio_service import (
    PortfolioService,
    RecordCashEventCommand,
)
from position_pilot.bootstrap import get_investment_agent, get_portfolio_service
from position_pilot.domain.errors import InsufficientCash, InvalidPortfolioValue
from position_pilot.domain.portfolio import CashEventType


class HealthResponse(BaseModel):
    """应用存活检查的稳定响应。"""

    status: str


class InvestmentQuestionRequest(BaseModel):
    """M3 投资问答 Vertical Slice 的稳定输入。"""

    user_id: UUID
    question: str = Field(min_length=1, max_length=MAX_QUESTION_LENGTH)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        """拒绝只包含空白的问题，并避免把格式清理交给 LLM。"""

        normalized = value.strip()
        if not normalized:
            raise ValueError("question 不能为空")
        return normalized


class ContextSourceResponse(BaseModel):
    """API 暴露的事实来源与获取状态。"""

    model_config = ConfigDict(from_attributes=True)

    type: ContextSourceType
    status: str
    ticker: str | None = None
    provider: str | None = None
    feed: str | None = None
    market_timestamp: datetime | None = None
    fetched_at: datetime | None = None


class InvestmentQuestionResponse(BaseModel):
    """包含确定性状态、自然语言回答和 Source Tracking。"""

    status: InvestmentResponseStatus
    answer: str
    sources: tuple[ContextSourceResponse, ...]


class ApiErrorDetail(BaseModel):
    """无法形成 Final Answer 时的稳定错误内容。"""

    code: str
    message: str


class CashEventRequest(BaseModel):
    """Portfolio 创建后追加不可变现金调整的输入。"""

    event_type: CashEventType
    amount: Decimal = Field(gt=0, max_digits=28, decimal_places=8)
    occurred_at: datetime
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        """实际发生时间必须携带明确时区。"""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at 必须包含时区")
        return value


class CashEventResponse(BaseModel):
    """API 暴露的不可变 Cash Event Ledger Record。"""

    id: UUID
    user_id: UUID
    sequence: int
    event_type: CashEventType
    amount: Decimal
    occurred_at: datetime
    reason: str | None


class CashAdjustmentResponse(BaseModel):
    """Cash Event 写入结果及同事务重建后的现金状态。"""

    cash_event: CashEventResponse
    available_cash: Decimal


app = FastAPI(title="PositionPilot")


@app.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """返回应用进程的存活状态，不检查外部依赖。"""

    return HealthResponse(status="ok")


def get_investment_agent_dependency() -> InvestmentAgent:
    """延迟装配外部依赖，允许测试安全替换。"""

    return get_investment_agent()


def get_portfolio_service_dependency() -> PortfolioService:
    """延迟装配 Portfolio Service，允许 API Contract Test 替换。"""

    return get_portfolio_service()


@app.post(
    "/v1/portfolios/{user_id}/cash-events",
    response_model=CashAdjustmentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Portfolio User 不存在"},
        409: {"description": "Withdrawal 超过当前可用现金"},
        422: {"description": "Cash Event 输入不满足领域约束"},
    },
)
def record_cash_event(
    user_id: UUID,
    request: CashEventRequest,
    portfolio_service: Annotated[PortfolioService, Depends(get_portfolio_service_dependency)],
) -> CashAdjustmentResponse:
    """追加 DEPOSIT / WITHDRAWAL 并返回确定性 Cash Snapshot。"""

    try:
        result = portfolio_service.record_cash_event(
            RecordCashEventCommand(
                user_id=user_id,
                event_type=request.event_type,
                amount=request.amount,
                occurred_at=request.occurred_at,
                reason=request.reason,
            )
        )
    except UserNotFound:
        _raise_api_error(
            status.HTTP_404_NOT_FOUND,
            ApiErrorDetail(code="USER_NOT_FOUND", message="Portfolio User 不存在"),
        )
    except InsufficientCash as error:
        _raise_api_error(
            status.HTTP_409_CONFLICT,
            ApiErrorDetail(code="INSUFFICIENT_CASH", message=str(error)),
        )
    except InvalidPortfolioValue as error:
        _raise_api_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            ApiErrorDetail(code="INVALID_CASH_EVENT", message=str(error)),
        )

    return CashAdjustmentResponse(
        cash_event=CashEventResponse(
            id=result.cash_event.id,
            user_id=result.cash_event.user_id,
            sequence=result.cash_event.sequence,
            event_type=result.cash_event.event_type,
            amount=result.cash_event.amount,
            occurred_at=result.cash_event.occurred_at,
            reason=result.cash_event.reason,
        ),
        available_cash=result.portfolio.cash.available_cash,
    )


@app.post(
    "/v1/investment/questions",
    response_model=InvestmentQuestionResponse,
    responses={
        404: {"description": "Portfolio User 不存在"},
        502: {"description": "Agent / LLM Contract 无法形成回答"},
        503: {"description": "LLM Provider 当前无法形成回答"},
    },
)
def answer_investment_question(
    request: InvestmentQuestionRequest,
    agent: Annotated[InvestmentAgent, Depends(get_investment_agent_dependency)],
) -> InvestmentQuestionResponse:
    """读取 Structured State 并执行最小 Investment Agent Vertical Slice。"""

    try:
        result = agent.answer(request.user_id, request.question)
    except UserNotFound:
        _raise_api_error(
            status.HTTP_404_NOT_FOUND,
            ApiErrorDetail(code="USER_NOT_FOUND", message="Portfolio User 不存在"),
        )
    if isinstance(result, InvestmentRequestFailure):
        _raise_request_failure(result)
    assert isinstance(result, InvestmentAnswer)
    return InvestmentQuestionResponse(
        status=result.status,
        answer=result.answer,
        sources=tuple(_source_response(source) for source in result.sources),
    )


def _source_response(source: ContextSource) -> ContextSourceResponse:
    return ContextSourceResponse.model_validate(source)


def _raise_request_failure(failure: InvestmentRequestFailure) -> None:
    if failure.code is InvestmentFailureCode.INVALID_QUESTION:
        _raise_api_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            ApiErrorDetail(code=failure.code.value, message=failure.message),
        )
    provider_unavailable_codes = {
        InvestmentFailureCode.LLM_AUTHENTICATION_FAILED,
        InvestmentFailureCode.LLM_RATE_LIMITED,
        InvestmentFailureCode.LLM_PROVIDER_UNAVAILABLE,
    }
    status_code = (
        status.HTTP_503_SERVICE_UNAVAILABLE
        if failure.code in provider_unavailable_codes
        else status.HTTP_502_BAD_GATEWAY
    )
    _raise_api_error(
        status_code,
        ApiErrorDetail(code=failure.code.value, message=failure.message),
    )


def _raise_api_error(status_code: int, detail: ApiErrorDetail) -> None:
    raise HTTPException(status_code=status_code, detail=detail.model_dump())
