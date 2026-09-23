"""Conversation / Thread 的 SQLAlchemy 持久化模型。

这些模型与 Portfolio Ledger 分开定义，避免 Conversation 的生命周期和约束
扩散到现有的 Ledger Unit of Work。所有子记录都同时保存 Account Owner，
并通过复合外键让数据库也能拒绝跨 Account 的引用。
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from position_pilot.database import Base


class ConversationThreadModel(Base):
    """Account-owned Conversation Thread。"""

    __tablename__ = "conversation_threads"
    __table_args__ = (
        UniqueConstraint("id", "account_id", name="uq_conversation_threads_id_account"),
        Index(
            "ix_conversation_threads_account_updated",
            "account_id",
            "updated_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    revision: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    next_sequence: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class ConversationTurnModel(Base):
    """一次 Agent Run 的持久状态与幂等标识。"""

    __tablename__ = "conversation_turns"
    __table_args__ = (
        ForeignKeyConstraint(
            ("thread_id", "account_id"),
            ("conversation_threads.id", "conversation_threads.account_id"),
            name="fk_conversation_turns_thread_owner",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "id",
            "thread_id",
            "account_id",
            name="uq_conversation_turns_owner",
        ),
        UniqueConstraint(
            "thread_id",
            "client_request_id",
            name="uq_conversation_turns_client_request",
        ),
        CheckConstraint(
            "status IN ('RUNNING', 'COMPLETED', 'FAILED')",
            name="ck_conversation_turns_status",
        ),
        Index("ix_conversation_turns_account_status", "account_id", "status"),
        Index(
            "uq_conversation_turns_running_thread",
            "thread_id",
            unique=True,
            postgresql_where=text("status = 'RUNNING'"),
            sqlite_where=text("status = 'RUNNING'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    thread_id: Mapped[UUID] = mapped_column(nullable=False)
    account_id: Mapped[UUID] = mapped_column(nullable=False)
    client_request_id: Mapped[UUID] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    run_deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    warnings: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )


class ConversationMessageModel(Base):
    """用户可见的 append-only User / Assistant Message。"""

    __tablename__ = "conversation_messages"
    __table_args__ = (
        ForeignKeyConstraint(
            ("thread_id", "account_id"),
            ("conversation_threads.id", "conversation_threads.account_id"),
            name="fk_conversation_messages_thread_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ("turn_id", "thread_id", "account_id"),
            (
                "conversation_turns.id",
                "conversation_turns.thread_id",
                "conversation_turns.account_id",
            ),
            name="fk_conversation_messages_turn_owner",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "thread_id",
            "sequence",
            name="uq_conversation_messages_thread_sequence",
        ),
        UniqueConstraint("turn_id", "role", name="uq_conversation_messages_turn_role"),
        CheckConstraint(
            "role IN ('USER', 'ASSISTANT')",
            name="ck_conversation_messages_role",
        ),
        Index("ix_conversation_messages_thread_sequence", "thread_id", "sequence"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    thread_id: Mapped[UUID] = mapped_column(nullable=False)
    account_id: Mapped[UUID] = mapped_column(nullable=False)
    turn_id: Mapped[UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class MessageSourceModel(Base):
    """Assistant Message 实际观察到的 Source Metadata。"""

    __tablename__ = "message_sources"
    __table_args__ = (
        ForeignKeyConstraint(
            ("assistant_message_id",),
            ("conversation_messages.id",),
            name="fk_message_sources_assistant_message",
            ondelete="CASCADE",
        ),
        Index("ix_message_sources_assistant_message", "assistant_message_id"),
    )

    source_id: Mapped[UUID] = mapped_column(primary_key=True)
    assistant_message_id: Mapped[UUID] = mapped_column(nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(200), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    event_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    content_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
