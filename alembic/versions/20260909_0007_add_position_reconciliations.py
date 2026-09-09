"""创建不可变 Position Reconciliation 事实表。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_0007"
down_revision: str | Sequence[str] | None = "20260830_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """保存外部持仓截图确认后的目标状态，不复制交易或现金事件。"""

    op.create_table(
        "position_reconciliations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("target_shares", sa.Numeric(precision=28, scale=8), nullable=False),
        sa.Column(
            "target_average_cost",
            sa.Numeric(precision=28, scale=8),
            nullable=False,
        ),
        sa.Column("position_type", sa.String(length=11), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("broker", sa.String(length=100), nullable=True),
        sa.Column("source_info", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "target_shares > 0",
            name="ck_position_reconciliations_target_shares_positive",
        ),
        sa.CheckConstraint(
            "target_average_cost > 0",
            name="ck_position_reconciliations_target_average_cost_positive",
        ),
        sa.CheckConstraint(
            "position_type IN ('LONG_TERM', 'SWING', 'UNSPECIFIED')",
            name="position_reconciliation_type",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_position_reconciliations_user_confirmed_at",
        "position_reconciliations",
        ["user_id", "confirmed_at"],
    )
    op.create_index(
        "ix_position_reconciliations_user_position",
        "position_reconciliations",
        ["user_id", "ticker", "position_type"],
    )


def downgrade() -> None:
    """仅在没有 Reconciliation 数据时允许移除该事实表。"""

    connection = op.get_bind()
    reconciliation_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM position_reconciliations")
    ).scalar_one()
    if reconciliation_count:
        raise RuntimeError("存在 Position Reconciliation 数据，拒绝有损 downgrade")

    op.drop_index(
        "ix_position_reconciliations_user_position",
        table_name="position_reconciliations",
    )
    op.drop_index(
        "ix_position_reconciliations_user_confirmed_at",
        table_name="position_reconciliations",
    )
    op.drop_table("position_reconciliations")
