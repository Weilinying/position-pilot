"""持续用户意图的 scope、允许字段与生命周期，不保存账本派生值。"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from position_pilot.domain.portfolio import PositionType, normalize_ticker


class StrategyKind(StrEnum):
    POSITION_PLAN_V1 = "POSITION_PLAN_V1"
    INVESTMENT_THESIS_V1 = "INVESTMENT_THESIS_V1"
    HOLDING_HORIZON_V1 = "HOLDING_HORIZON_V1"


class StrategyOperation(StrEnum):
    UPSERT = "UPSERT"
    INVALIDATE = "INVALIDATE"


class StrategyOrigin(StrEnum):
    USER_STATED_INTENT = "USER_STATED_INTENT"
    USER_REQUESTED_DRAFT = "USER_REQUESTED_DRAFT"


class CandidateStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    STALE = "STALE"


class StrategyVersionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"


class IntentModel(BaseModel):
    """明确拒绝额外字段，防止派生事实或实时建议进入持久意图。"""

    model_config = ConfigDict(extra="forbid", frozen=True)


class StrategyScope(IntentModel):
    """三种 Intent 均按独立仓位类型隔离；Account 属于外层 Owner。"""

    ticker: str
    position_type: Literal[PositionType.LONG_TERM, PositionType.SWING]

    @field_validator("ticker")
    @classmethod
    def canonical_ticker(cls, value: str) -> str:
        return normalize_ticker(value)

    @property
    def key(self) -> str:
        return f"{self.ticker}:{self.position_type.value}"


class PositionPlanPayload(IntentModel):
    """目标当前资本配置；不是本轮投入授权或历史累计买入上限。"""

    target_budget: Decimal = Field(gt=0, max_digits=24, decimal_places=8)
    currency: str = Field(default="USD", pattern="^USD$")

    @field_validator("target_budget", mode="before")
    @classmethod
    def reject_boolean_amount(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("预算必须是金额，不能是布尔值")
        return value


class ThesisPayload(IntentModel):
    thesis_text: str = Field(min_length=1, max_length=2000)

    @field_validator("thesis_text")
    @classmethod
    def nonempty_thesis(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Thesis 不能为空白")
        return value


class HorizonPayload(IntentModel):
    horizon_category: str = Field(pattern="^(LONG_TERM|MEDIUM_TERM|SHORT_TERM|UNTIL_DATE)$")
    until: datetime | None = None

    @model_validator(mode="after")
    def validate_until(self) -> Self:
        if (self.horizon_category == "UNTIL_DATE") != (self.until is not None):
            raise ValueError("UNTIL_DATE 必须且仅该类别可提供 until")
        if self.until is not None and self.until.utcoffset() is None:
            raise ValueError("until 必须带时区")
        return self


IntentPayload = PositionPlanPayload | ThesisPayload | HorizonPayload


class StrategyDraft(IntentModel):
    """模型只提出待审草案；确认与版本信息由 Application 决定。"""

    operation: StrategyOperation
    scope: StrategyScope
    kind: StrategyKind
    payload: IntentPayload | None
    origin: StrategyOrigin
    evidence_quote: str = Field(min_length=1, max_length=4000)
    replaces_candidate_id: UUID | None = None
    replaces_candidate_revision: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_payload(self) -> Self:
        expected = {
            StrategyKind.POSITION_PLAN_V1: PositionPlanPayload,
            StrategyKind.INVESTMENT_THESIS_V1: ThesisPayload,
            StrategyKind.HOLDING_HORIZON_V1: HorizonPayload,
        }[self.kind]
        if self.operation is StrategyOperation.INVALIDATE:
            if self.payload is not None:
                raise ValueError("失效草案不携带新意图 payload")
        elif not isinstance(self.payload, expected):
            raise ValueError("payload 与 Intent kind 不匹配")
        if (self.replaces_candidate_id is None) != (self.replaces_candidate_revision is None):
            raise ValueError("替换草案必须同时提供 ID 与 revision")
        return self


class StrategyCandidate(StrategyDraft):
    """来源可追溯、未确认不生效的跨会话意图草案。"""

    purpose: Literal["PERSISTENT_USER_INTENT"] = "PERSISTENT_USER_INTENT"
    payload_schema_version: Literal[1] = 1
    id: UUID
    account_id: UUID
    thread_id: UUID
    source_user_message_id: UUID
    assistant_message_id: UUID
    strategy_id: UUID
    base_version: int
    candidate_revision: int
    proposal_request_id: UUID
    status: CandidateStatus
    created_at: datetime
    expires_at: datetime
    resolved_at: datetime | None = None


class StrategyVersion(IntentModel):
    """确认意图版本；生效与失效保留历史，不重写交易事实。"""

    payload_schema_version: Literal[1] = 1
    id: UUID
    strategy_id: UUID
    account_id: UUID
    confirmed_by_account_id: UUID
    scope: StrategyScope
    kind: StrategyKind
    payload: IntentPayload | None
    version: int
    status: StrategyVersionStatus
    previous_version_id: UUID | None
    source_candidate_id: UUID
    confirmation_request_id: UUID
    confirmed_at: datetime
    superseded_at: datetime | None = None
    invalidated_at: datetime | None = None
