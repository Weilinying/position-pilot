"""持久用户意图表；独立唯一约束允许 ACTIVE 与 PENDING 同时存在。"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from position_pilot.database import Base


class StrategyIdentityModel(Base):
    """稳定冲突域行：首次确认前也能锁定 scope，不使用 Account-wide 锁。"""

    __tablename__ = "strategy_identities"
    __table_args__ = (
        UniqueConstraint("account_id", "scope_key", "kind", name="uq_strategy_identity_scope"),
        UniqueConstraint(
            "id", "account_id", "scope_key", "kind", name="uq_strategy_identity_owner"
        ),
        CheckConstraint("position_type IN ('LONG_TERM','SWING')", name="ck_strategy_scope_type"),
        CheckConstraint("scope_key = ticker || ':' || position_type", name="ck_strategy_scope_key"),
        CheckConstraint(
            "kind IN ('POSITION_PLAN_V1','INVESTMENT_THESIS_V1','HOLDING_HORIZON_V1')",
            name="ck_strategy_kind",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(128))
    ticker: Mapped[str] = mapped_column(String(32))
    position_type: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(64))


class StrategyCandidateModel(Base):
    """只保留意图及溯源，无账本派生字段。"""

    __tablename__ = "strategy_candidates"
    __table_args__ = (
        ForeignKeyConstraint(
            ("strategy_id", "account_id", "scope_key", "kind"),
            (
                "strategy_identities.id",
                "strategy_identities.account_id",
                "strategy_identities.scope_key",
                "strategy_identities.kind",
            ),
            name="fk_candidate_scope",
        ),
        ForeignKeyConstraint(
            ("thread_id", "account_id"),
            ("conversation_threads.id", "conversation_threads.account_id"),
            name="fk_candidate_thread_owner",
        ),
        ForeignKeyConstraint(
            ("source_user_message_id", "thread_id", "account_id"),
            (
                "conversation_messages.id",
                "conversation_messages.thread_id",
                "conversation_messages.account_id",
            ),
            name="fk_candidate_user_owner",
        ),
        ForeignKeyConstraint(
            ("assistant_message_id", "thread_id", "account_id"),
            (
                "conversation_messages.id",
                "conversation_messages.thread_id",
                "conversation_messages.account_id",
            ),
            name="fk_candidate_assistant_owner",
        ),
        UniqueConstraint("id", "account_id", "strategy_id", name="uq_candidate_identity_owner"),
        UniqueConstraint("assistant_message_id", name="uq_candidate_assistant"),
        UniqueConstraint("account_id", "proposal_request_id", name="uq_candidate_proposal_request"),
        CheckConstraint(
            "status IN ('PENDING','CONFIRMED','CANCELLED','EXPIRED','STALE')",
            name="ck_candidate_status",
        ),
        Index(
            "uq_candidate_pending_scope",
            "account_id",
            "scope_key",
            "kind",
            unique=True,
            postgresql_where=text("status = 'PENDING'"),
            sqlite_where=text("status = 'PENDING'"),
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    account_id: Mapped[UUID] = mapped_column(nullable=False)
    thread_id: Mapped[UUID] = mapped_column(nullable=False)
    strategy_id: Mapped[UUID] = mapped_column(nullable=False)
    scope_key: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    source_user_message_id: Mapped[UUID] = mapped_column(nullable=False)
    assistant_message_id: Mapped[UUID] = mapped_column(nullable=False)
    proposal_request_id: Mapped[UUID] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    record: Mapped[dict[str, object]] = mapped_column(JSON)


class StrategyVersionModel(Base):
    """历史确认版本，确认替代与新版本写入在同一事务完成。"""

    __tablename__ = "confirmed_strategy_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ("strategy_id", "account_id", "scope_key", "kind"),
            (
                "strategy_identities.id",
                "strategy_identities.account_id",
                "strategy_identities.scope_key",
                "strategy_identities.kind",
            ),
            name="fk_version_scope",
        ),
        ForeignKeyConstraint(
            ("source_candidate_id", "account_id", "strategy_id"),
            (
                "strategy_candidates.id",
                "strategy_candidates.account_id",
                "strategy_candidates.strategy_id",
            ),
            name="fk_version_candidate_owner",
        ),
        UniqueConstraint("strategy_id", "version", name="uq_strategy_version"),
        UniqueConstraint(
            "account_id", "confirmation_request_id", name="uq_strategy_confirmation_request"
        ),
        UniqueConstraint("source_candidate_id", name="uq_strategy_confirmed_candidate"),
        CheckConstraint("version > 0", name="ck_strategy_version_positive"),
        CheckConstraint(
            "status IN ('ACTIVE','SUPERSEDED','INVALIDATED')", name="ck_strategy_version_status"
        ),
        Index(
            "uq_strategy_active_scope",
            "account_id",
            "scope_key",
            "kind",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    strategy_id: Mapped[UUID] = mapped_column(nullable=False)
    account_id: Mapped[UUID] = mapped_column(nullable=False)
    scope_key: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    source_candidate_id: Mapped[UUID] = mapped_column(nullable=False)
    confirmation_request_id: Mapped[UUID] = mapped_column(nullable=False)
    record: Mapped[dict[str, object]] = mapped_column(JSON)
