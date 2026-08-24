"""FastAPI 应用入口。"""

from datetime import datetime
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
from position_pilot.bootstrap import get_investment_agent


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


class InvestmentErrorDetail(BaseModel):
    """无法形成 Final Answer 时的稳定错误内容。"""

    code: str
    message: str


app = FastAPI(title="PositionPilot")


@app.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """返回应用进程的存活状态，不检查外部依赖。"""

    return HealthResponse(status="ok")


def get_investment_agent_dependency() -> InvestmentAgent:
    """延迟装配外部依赖，允许测试安全替换。"""

    return get_investment_agent()


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
            InvestmentErrorDetail(code="USER_NOT_FOUND", message="Portfolio User 不存在"),
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
        InvestmentErrorDetail(code=failure.code.value, message=failure.message),
    )


def _raise_api_error(status_code: int, detail: InvestmentErrorDetail) -> None:
    raise HTTPException(status_code=status_code, detail=detail.model_dump())
