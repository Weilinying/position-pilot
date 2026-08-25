"""创建 Portfolio Cash Event Ledger。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260825_0004"
down_revision: str | Sequence[str] | None = "20260821_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建只支持 DEPOSIT 与 WITHDRAWAL 的不可变事实表。"""

    op.create_table(
        "cash_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=10), nullable=False),
        sa.Column("amount", sa.Numeric(precision=28, scale=8), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.CheckConstraint("sequence > 0", name="ck_cash_events_sequence_positive"),
        sa.CheckConstraint("amount > 0", name="ck_cash_events_amount_positive"),
        sa.CheckConstraint(
            "event_type IN ('DEPOSIT', 'WITHDRAWAL')",
            name="cash_event_type",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "sequence", name="uq_cash_events_user_sequence"),
    )
    op.create_index(
        "ix_cash_events_user_occurred_at",
        "cash_events",
        ["user_id", "occurred_at"],
    )


def downgrade() -> None:
    """仅供本地回滚 Cash Event Schema。"""

    op.drop_index("ix_cash_events_user_occurred_at", table_name="cash_events")
    op.drop_table("cash_events")
