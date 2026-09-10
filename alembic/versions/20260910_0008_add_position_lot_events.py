"""增加卖出批次分配、批次类型变更与 BUY 更正事实。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0008"
down_revision: str | Sequence[str] | None = "20260909_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """持久化由 Transaction / Opening / Reconciliation 来源 ID 标识的批次事件。"""

    op.create_table(
        "lot_allocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("sell_transaction_id", sa.Uuid(), nullable=False),
        sa.Column("lot_id", sa.Uuid(), nullable=False),
        sa.Column("shares", sa.Numeric(precision=28, scale=8), nullable=False),
        sa.CheckConstraint("shares > 0", name="ck_lot_allocations_shares_positive"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["sell_transaction_id"],
            ["transactions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "sell_transaction_id",
            "lot_id",
            name="uq_lot_allocations_transaction_lot",
        ),
    )
    op.create_index(
        "ix_lot_allocations_user_transaction",
        "lot_allocations",
        ["user_id", "sell_transaction_id"],
    )
    op.create_table(
        "lot_classification_changes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("lot_id", sa.Uuid(), nullable=False),
        sa.Column("position_type", sa.String(length=11), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "position_type IN ('LONG_TERM', 'SWING', 'UNSPECIFIED')",
            name="lot_classification_position_type",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_lot_classification_user_lot_time",
        "lot_classification_changes",
        ["user_id", "lot_id", "effective_at"],
    )
    op.create_table(
        "buy_transaction_corrections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("price", sa.Numeric(precision=28, scale=8), nullable=False),
        sa.Column("shares", sa.Numeric(precision=28, scale=8), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("price > 0", name="ck_buy_corrections_price_positive"),
        sa.CheckConstraint("shares > 0", name="ck_buy_corrections_shares_positive"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_buy_corrections_user_transaction_time",
        "buy_transaction_corrections",
        ["user_id", "transaction_id", "corrected_at"],
    )


def downgrade() -> None:
    """本地开发阶段允许移除批次事件表。"""

    op.drop_index(
        "ix_buy_corrections_user_transaction_time",
        table_name="buy_transaction_corrections",
    )
    op.drop_table("buy_transaction_corrections")
    op.drop_index(
        "ix_lot_classification_user_lot_time",
        table_name="lot_classification_changes",
    )
    op.drop_table("lot_classification_changes")
    op.drop_index("ix_lot_allocations_user_transaction", table_name="lot_allocations")
    op.drop_table("lot_allocations")
