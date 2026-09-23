"""Account-owned Conversation Thread / Message API。"""

from __future__ import annotations

from typing import Annotated, NoReturn, cast
from uuid import UUID

from fastapi import APIRouter, Body, Cookie, Depends, HTTPException, Query, status

from position_pilot.api.schemas.conversation import (
    AnswerV2,
    ConversationAskRequest,
    ConversationAskResponse,
    ConversationHistoryResponse,
    ConversationMessageResponse,
    ConversationSourceResponse,
    ConversationThreadListResponse,
    ConversationThreadResponse,
    ConversationThreadSnapshotResponse,
    ConversationThreadStartRequest,
    ConversationTurnResponse,
)
from position_pilot.application.auth_service import Account, AuthService
from position_pilot.application.conversation_service import (
    ConversationCompletion,
    ConversationError,
    ConversationIdempotencyConflict,
    ConversationRevisionConflict,
    ConversationRunExpired,
    ConversationService,
    ConversationSource,
    ConversationThreadNotFound,
    ConversationTurnInProgress,
    ConversationTurnNotFound,
    ConversationValidationError,
)
from position_pilot.application.errors import AuthenticationRequired

SESSION_COOKIE_NAME = "positionpilot_session"

router = APIRouter(tags=["conversation"])


def get_conversation_auth_service_dependency() -> AuthService:
    """延迟获取 Auth Service，允许 API Contract Test 替换。"""

    from position_pilot.bootstrap import get_auth_service

    return get_auth_service()


def get_conversation_service_dependency() -> ConversationService:
    """延迟获取 Conversation Service，允许 Composition Root 替换。"""

    from position_pilot.bootstrap import get_conversation_service

    return get_conversation_service()


def get_conversation_account_dependency(
    auth_service: Annotated[
        AuthService,
        Depends(get_conversation_auth_service_dependency),
    ],
    session_token: Annotated[
        str | None,
        Cookie(alias=SESSION_COOKIE_NAME),
    ] = None,
) -> Account:
    """只从 HttpOnly Session Cookie 解析当前 Account。"""

    try:
        return auth_service.authenticate(session_token)
    except AuthenticationRequired as error:
        _raise_api_error(
            status.HTTP_401_UNAUTHORIZED,
            "AUTHENTICATION_REQUIRED",
            str(error),
        )


@router.post(
    "/v1/threads",
    response_model=ConversationThreadResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_thread(
    account: Annotated[Account, Depends(get_conversation_account_dependency)],
    service: Annotated[
        ConversationService,
        Depends(get_conversation_service_dependency),
    ],
    request: Annotated[ConversationThreadStartRequest | None, Body()] = None,
) -> ConversationThreadResponse:
    """创建当前 Session Account 的空 Thread。"""

    try:
        thread = service.start_thread(account.id, title=request.title if request else None)
    except ConversationValidationError as error:
        _raise_api_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "CONVERSATION_INVALID", str(error))
    return ConversationThreadResponse.from_domain(thread)


@router.get(
    "/v1/threads",
    response_model=ConversationThreadListResponse,
)
def list_threads(
    account: Annotated[Account, Depends(get_conversation_account_dependency)],
    service: Annotated[
        ConversationService,
        Depends(get_conversation_service_dependency),
    ],
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ConversationThreadListResponse:
    """列出当前 Account 未删除的 Thread。"""

    try:
        page = service.list_threads(account.id, cursor=cursor, limit=limit)
    except ConversationValidationError as error:
        _raise_api_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "CONVERSATION_INVALID", str(error))
    return ConversationThreadListResponse.from_domain(page)


@router.get(
    "/v1/threads/{thread_id}",
    response_model=ConversationThreadSnapshotResponse,
)
def get_thread(
    thread_id: UUID,
    account: Annotated[Account, Depends(get_conversation_account_dependency)],
    service: Annotated[
        ConversationService,
        Depends(get_conversation_service_dependency),
    ],
) -> ConversationThreadSnapshotResponse:
    """读取当前 Account 可访问的 Thread Snapshot。"""

    try:
        snapshot = service.get_thread(account.id, thread_id)
    except ConversationThreadNotFound as error:
        _raise_api_error(status.HTTP_404_NOT_FOUND, "THREAD_NOT_FOUND", str(error))
    return ConversationThreadSnapshotResponse.from_domain(snapshot)


@router.get(
    "/v1/threads/{thread_id}/messages",
    response_model=ConversationHistoryResponse,
)
def get_messages(
    thread_id: UUID,
    account: Annotated[Account, Depends(get_conversation_account_dependency)],
    service: Annotated[
        ConversationService,
        Depends(get_conversation_service_dependency),
    ],
    before: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ConversationHistoryResponse:
    """读取当前 Account Thread 的用户可见 Message。"""

    try:
        page = service.history(account.id, thread_id, before_sequence=before, limit=limit)
    except ConversationThreadNotFound as error:
        _raise_api_error(status.HTTP_404_NOT_FOUND, "THREAD_NOT_FOUND", str(error))
    except ConversationValidationError as error:
        _raise_api_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "CONVERSATION_INVALID", str(error))
    return ConversationHistoryResponse(
        thread=ConversationThreadResponse.from_domain(page.thread),
        messages=tuple(ConversationMessageResponse.from_domain(item) for item in page.messages),
        active_turn=ConversationTurnResponse.from_domain(page.active_turn),
        next_cursor=page.next_cursor,
    )


@router.post(
    "/v1/threads/{thread_id}/messages",
    response_model=ConversationAskResponse,
)
def post_message(
    thread_id: UUID,
    request: ConversationAskRequest,
    account: Annotated[Account, Depends(get_conversation_account_dependency)],
    service: Annotated[
        ConversationService,
        Depends(get_conversation_service_dependency),
    ],
) -> ConversationAskResponse:
    """提交一次同步 Ask，并返回持久化的 User / Assistant Message。"""

    if account.portfolio_user_id is None:
        _raise_api_error(
            status.HTTP_409_CONFLICT,
            "PORTFOLIO_SETUP_REQUIRED",
            "请先完成 Portfolio Setup",
        )
    try:
        completion = service.ask(
            account.id,
            thread_id,
            portfolio_user_id=account.portfolio_user_id,
            question=request.content,
            client_request_id=request.client_request_id,
            expected_thread_revision=request.expected_thread_revision,
        )
    except ConversationThreadNotFound as error:
        _raise_api_error(status.HTTP_404_NOT_FOUND, "THREAD_NOT_FOUND", str(error))
    except ConversationRevisionConflict as error:
        _raise_api_error(status.HTTP_409_CONFLICT, "THREAD_CONFLICT", str(error))
    except ConversationIdempotencyConflict as error:
        _raise_api_error(status.HTTP_409_CONFLICT, "THREAD_CONFLICT", str(error))
    except ConversationTurnInProgress as error:
        _raise_api_error(
            status.HTTP_409_CONFLICT,
            "TURN_IN_PROGRESS",
            str(error),
            turn_id=error.turn_id,
        )
    except ConversationTurnNotFound as error:
        _raise_api_error(status.HTTP_404_NOT_FOUND, "THREAD_NOT_FOUND", str(error))
    except ConversationRunExpired as error:
        _raise_api_error(status.HTTP_502_BAD_GATEWAY, "AGENT_REQUEST_FAILED", str(error))
    except ConversationValidationError as error:
        _raise_api_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "CONVERSATION_INVALID", str(error))
    except ConversationError as error:
        _raise_api_error(status.HTTP_409_CONFLICT, "THREAD_CONFLICT", str(error))
    except Exception:
        # Service 已将 Agent 异常记录为 FAILED；API 不泄露 Provider 原始异常。
        _raise_api_error(
            status.HTTP_502_BAD_GATEWAY,
            "AGENT_REQUEST_FAILED",
            "Agent 请求失败",
        )
    if completion.turn.status.value == "FAILED":
        _raise_failure_completion(completion)
    return _ask_response(completion)


@router.delete(
    "/v1/threads/{thread_id}",
    response_model=ConversationThreadResponse,
)
def delete_thread(
    thread_id: UUID,
    account: Annotated[Account, Depends(get_conversation_account_dependency)],
    service: Annotated[
        ConversationService,
        Depends(get_conversation_service_dependency),
    ],
) -> ConversationThreadResponse:
    """软删除当前 Account Thread。"""

    try:
        deleted = service.delete_thread(account.id, thread_id)
    except ConversationThreadNotFound as error:
        _raise_api_error(status.HTTP_404_NOT_FOUND, "THREAD_NOT_FOUND", str(error))
    except ConversationTurnInProgress as error:
        _raise_api_error(
            status.HTTP_409_CONFLICT,
            "TURN_IN_PROGRESS",
            str(error),
            turn_id=error.turn_id,
        )
    return ConversationThreadResponse.from_domain(deleted)


def _ask_response(completion: ConversationCompletion) -> ConversationAskResponse:
    """把 Service Completion 映射为 T3 最小 Answer V2。"""

    assistant = completion.assistant_message
    sources = tuple(
        # Source 只能来自 Service 已经持久化的真实 Metadata。
        _source_response(source)
        for source in completion.sources
    )
    answer = (
        AnswerV2(
            text=assistant.content if assistant is not None else None,
            warnings=completion.warnings,
            sources=sources,
            citations=(),
            candidate=None,
        )
        if assistant is not None
        else None
    )
    return ConversationAskResponse(
        thread=ConversationThreadResponse.from_domain(completion.thread),
        turn=cast(ConversationTurnResponse, ConversationTurnResponse.from_domain(completion.turn)),
        user_message=ConversationMessageResponse.from_domain(completion.user_message),
        assistant_message=(
            ConversationMessageResponse.from_domain(assistant) if assistant is not None else None
        ),
        answer=answer,
    )


def _raise_failure_completion(completion: ConversationCompletion) -> NoReturn:
    """将 Service 已持久化的失败 Turn 映射为稳定 Provider/API 错误。"""

    code = completion.turn.failure_code or "AGENT_REQUEST_FAILED"
    provider_codes = {
        "LLM_AUTHENTICATION_FAILED",
        "LLM_RATE_LIMITED",
        "LLM_PROVIDER_UNAVAILABLE",
        "PROVIDER_UNAVAILABLE",
        "AUTHENTICATION_FAILED",
        "RATE_LIMITED",
    }
    status_code = (
        status.HTTP_503_SERVICE_UNAVAILABLE
        if code in provider_codes
        else status.HTTP_502_BAD_GATEWAY
    )
    message = "Agent Provider 当前不可用" if code in provider_codes else "Agent 请求失败"
    _raise_api_error(status_code, code, message)


def _source_response(source: ConversationSource) -> ConversationSourceResponse:
    """把 Application Source DTO 映射为稳定 Public Response。"""

    return ConversationSourceResponse.from_domain(source)


def _raise_api_error(
    status_code: int,
    code: str,
    message: str,
    *,
    turn_id: UUID | None = None,
) -> NoReturn:
    detail = {"code": code, "message": message}
    if turn_id is not None:
        detail["turn_id"] = str(turn_id)
    raise HTTPException(
        status_code=status_code,
        detail=detail,
    )


__all__ = [
    "get_conversation_account_dependency",
    "get_conversation_auth_service_dependency",
    "get_conversation_service_dependency",
    "router",
]
