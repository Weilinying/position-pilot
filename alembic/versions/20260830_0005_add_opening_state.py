"""增加不可变 Opening State 与未分类仓位类型。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_0005"
down_revision: str | Sequence[str] | None = "20260825_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建 Opening Position Starting Facts，并允许 UNSPECIFIED。"""

    op.drop_constraint("position_type", "transactions", type_="check")
    op.alter_column(
        "transactions",
        "position_type",
        existing_type=sa.String(length=9),
        type_=sa.String(length=11),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "position_type",
        "transactions",
        "position_type IN ('LONG_TERM', 'SWING', 'UNSPECIFIED')",
    )

    op.create_table(
        "opening_positions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("shares", sa.Numeric(precision=28, scale=8), nullable=False),
        sa.Column("average_cost", sa.Numeric(precision=28, scale=8), nullable=False),
        sa.Column("position_type", sa.String(length=11), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "shares > 0",
            name="ck_opening_positions_shares_positive",
        ),
        sa.CheckConstraint(
            "average_cost > 0",
            name="ck_opening_positions_average_cost_positive",
        ),
        sa.CheckConstraint(
            "position_type IN ('LONG_TERM', 'SWING', 'UNSPECIFIED')",
            name="opening_position_type",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "ticker",
            "position_type",
            name="uq_opening_positions_user_position",
        ),
    )
    op.create_index(
        "ix_opening_positions_user_position",
        "opening_positions",
        ["user_id", "ticker", "position_type"],
    )


def downgrade() -> None:
    """只在没有新语义数据时移除 Opening State 与 UNSPECIFIED。"""

    connection = op.get_bind()
    opening_position_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM opening_positions")
    ).scalar_one()
    unspecified_transaction_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM transactions WHERE position_type = 'UNSPECIFIED'")
    ).scalar_one()
    if opening_position_count or unspecified_transaction_count:
        raise RuntimeError("存在 Opening Position 或 UNSPECIFIED Transaction，拒绝有损 downgrade")

    op.drop_index(
        "ix_opening_positions_user_position",
        table_name="opening_positions",
    )
    op.drop_table("opening_positions")

    op.drop_constraint("position_type", "transactions", type_="check")
    op.alter_column(
        "transactions",
        "position_type",
        existing_type=sa.String(length=11),
        type_=sa.String(length=9),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "position_type",
        "transactions",
        "position_type IN ('LONG_TERM', 'SWING')",
    )
