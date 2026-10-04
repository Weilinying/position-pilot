"""新增 Account-owned Conversation Thread、Turn、Message 与 Source。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260922_0010"
down_revision: str | Sequence[str] | None = "20260911_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TIMESTAMPTZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    """以 Additive Migration 建立 Conversation 持久化边界。"""

    op.create_table(
        "conversation_threads",
        sa.Column("id", UUID, nullable=False),
        sa.Column("account_id", UUID, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("revision", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("next_sequence", sa.BigInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at",
            TIMESTAMPTZ,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            TIMESTAMPTZ,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("deleted_at", TIMESTAMPTZ, nullable=True),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_conversation_threads_account",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "account_id", name="uq_conversation_threads_id_account"),
    )
    op.create_index(
        "ix_conversation_threads_account_updated",
        "conversation_threads",
        ["account_id", "updated_at"],
    )

    op.create_table(
        "conversation_turns",
        sa.Column("id", UUID, nullable=False),
        sa.Column("thread_id", UUID, nullable=False),
        sa.Column("account_id", UUID, nullable=False),
        sa.Column("client_request_id", UUID, nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("run_deadline_at", TIMESTAMPTZ, nullable=True),
        sa.Column(
            "created_at",
            TIMESTAMPTZ,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("completed_at", TIMESTAMPTZ, nullable=True),
        sa.Column(
            "warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'COMPLETED', 'FAILED')",
            name="ck_conversation_turns_status",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id", "account_id"],
            ["conversation_threads.id", "conversation_threads.account_id"],
            name="fk_conversation_turns_thread_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "thread_id", "account_id", name="uq_conversation_turns_owner"),
        sa.UniqueConstraint(
            "thread_id",
            "client_request_id",
            name="uq_conversation_turns_client_request",
        ),
    )
    op.create_index(
        "ix_conversation_turns_account_status",
        "conversation_turns",
        ["account_id", "status"],
    )
    op.create_index(
        "uq_conversation_turns_running_thread",
        "conversation_turns",
        ["thread_id"],
        unique=True,
        postgresql_where=sa.text("status = 'RUNNING'"),
    )

    op.create_table(
        "conversation_messages",
        sa.Column("id", UUID, nullable=False),
        sa.Column("thread_id", UUID, nullable=False),
        sa.Column("account_id", UUID, nullable=False),
        sa.Column("turn_id", UUID, nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            TIMESTAMPTZ,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('USER', 'ASSISTANT')",
            name="ck_conversation_messages_role",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id", "account_id"],
            ["conversation_threads.id", "conversation_threads.account_id"],
            name="fk_conversation_messages_thread_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["turn_id", "thread_id", "account_id"],
            [
                "conversation_turns.id",
                "conversation_turns.thread_id",
                "conversation_turns.account_id",
            ],
            name="fk_conversation_messages_turn_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "thread_id",
            "sequence",
            name="uq_conversation_messages_thread_sequence",
        ),
        sa.UniqueConstraint("turn_id", "role", name="uq_conversation_messages_turn_role"),
    )
    op.create_index(
        "ix_conversation_messages_thread_sequence",
        "conversation_messages",
        ["thread_id", "sequence"],
    )

    op.create_table(
        "message_sources",
        sa.Column("source_id", UUID, nullable=False),
        sa.Column("assistant_message_id", UUID, nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("provider_reference", sa.String(length=500), nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("publisher", sa.String(length=200), nullable=True),
        sa.Column("published_at", TIMESTAMPTZ, nullable=True),
        sa.Column("event_time", TIMESTAMPTZ, nullable=True),
        sa.Column("fetched_at", TIMESTAMPTZ, nullable=True),
        sa.Column("content_scope", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["assistant_message_id"],
            ["conversation_messages.id"],
            name="fk_message_sources_assistant_message",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("source_id"),
    )
    op.create_index(
        "ix_message_sources_assistant_message",
        "message_sources",
        ["assistant_message_id"],
    )


def downgrade() -> None:
    """按子表到父表的顺序移除本次 Additive Migration。"""

    op.drop_index("ix_message_sources_assistant_message", table_name="message_sources")
    op.drop_table("message_sources")

    op.drop_index("ix_conversation_messages_thread_sequence", table_name="conversation_messages")
    op.drop_table("conversation_messages")

    op.drop_index(
        "uq_conversation_turns_running_thread",
        table_name="conversation_turns",
    )
    op.drop_index("ix_conversation_turns_account_status", table_name="conversation_turns")
    op.drop_table("conversation_turns")

    op.drop_index(
        "ix_conversation_threads_account_updated",
        table_name="conversation_threads",
    )
    op.drop_table("conversation_threads")
