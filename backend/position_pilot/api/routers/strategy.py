"""只有显式 Session-owned API 可以确认持续意图；没有任意 Payload Create API。"""

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from position_pilot.api.routers.conversation import get_conversation_account_dependency
from position_pilot.application.auth_service import Account
from position_pilot.application.strategy_service import StrategyError, StrategyService
from position_pilot.domain.strategy import StrategyCandidate, StrategyScope, StrategyVersion

router = APIRouter(tags=["strategy"])


class ConfirmIntentRequest(BaseModel):
    """绑定已展示草案和版本，确认重放不能复用于其他内容。"""

    model_config = ConfigDict(extra="forbid")
    candidate_revision: StrictInt = Field(ge=1)
    base_version: StrictInt = Field(ge=0)
    client_request_id: UUID


class CancelIntentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_revision: StrictInt = Field(ge=1)


def get_strategy_service_dependency() -> StrategyService:
    from position_pilot.bootstrap import get_strategy_service

    return get_strategy_service()


def raise_strategy_error(error: StrategyError) -> NoReturn:
    codes = {"STRATEGY_NOT_FOUND": 404, "STRATEGY_INVALID": 422}
    raise HTTPException(
        codes.get(error.code, 409), detail={"code": error.code, "message": str(error)}
    )


@router.get("/v1/strategies", response_model=tuple[StrategyVersion, ...])
def list_strategies(
    account: Annotated[Account, Depends(get_conversation_account_dependency)],
    service: Annotated[StrategyService, Depends(get_strategy_service_dependency)],
    scope: Annotated[str | None, Query()] = None,
) -> tuple[StrategyVersion, ...]:
    """仅返回当前 Account 的 ACTIVE 意图，scope 使用规范化 ticker:type。"""

    if scope is not None:
        try:
            ticker, position_type = scope.split(":")
            scope = StrategyScope.model_validate(
                {"ticker": ticker, "position_type": position_type}
            ).key
        except ValueError as error:
            raise HTTPException(
                422,
                detail={
                    "code": "STRATEGY_INVALID",
                    "message": "scope 必须是 ticker:LONG_TERM 或 ticker:SWING",
                },
            ) from error
    return service.active(account.id, scope)


@router.get("/v1/strategy-candidates/{candidate_id}", response_model=StrategyCandidate)
def get_candidate(
    candidate_id: UUID,
    account: Annotated[Account, Depends(get_conversation_account_dependency)],
    service: Annotated[StrategyService, Depends(get_strategy_service_dependency)],
) -> StrategyCandidate:
    try:
        return service.get(account.id, candidate_id)
    except StrategyError as error:
        raise_strategy_error(error)


@router.post("/v1/strategy-candidates/{candidate_id}/confirm", response_model=StrategyVersion)
def confirm_candidate(
    candidate_id: UUID,
    request: ConfirmIntentRequest,
    account: Annotated[Account, Depends(get_conversation_account_dependency)],
    service: Annotated[StrategyService, Depends(get_strategy_service_dependency)],
) -> StrategyVersion:
    """明确 UI / API 确认后原子替代，模型 Tool 没有此入口。"""
    try:
        return service.confirm(account.id, candidate_id, **request.model_dump())
    except StrategyError as error:
        raise_strategy_error(error)


@router.post("/v1/strategy-candidates/{candidate_id}/cancel", response_model=StrategyCandidate)
def cancel_candidate(
    candidate_id: UUID,
    request: CancelIntentRequest,
    account: Annotated[Account, Depends(get_conversation_account_dependency)],
    service: Annotated[StrategyService, Depends(get_strategy_service_dependency)],
) -> StrategyCandidate:
    try:
        return service.cancel(
            account.id, candidate_id, candidate_revision=request.candidate_revision
        )
    except StrategyError as error:
        raise_strategy_error(error)
