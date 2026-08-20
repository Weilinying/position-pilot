"""创建 User 与 Transaction Ledger。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建 M1 Structured State 的持久化事实表。"""

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("initial_cash", sa.Numeric(precision=28, scale=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "initial_cash >= 0",
            name="ck_users_initial_cash_non_negative",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column(
            "action",
            sa.Enum(
                "BUY",
                "SELL",
                name="transaction_action",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("price", sa.Numeric(precision=28, scale=8), nullable=False),
        sa.Column("shares", sa.Numeric(precision=28, scale=8), nullable=False),
        sa.Column("amount", sa.Numeric(precision=28, scale=8), nullable=False),
        sa.Column(
            "position_type",
            sa.Enum(
                "LONG_TERM",
                "SWING",
                name="position_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        sa.CheckConstraint(
            "amount = round(price * shares, 8)",
            name="ck_transactions_amount_derived",
        ),
        sa.CheckConstraint("price > 0", name="ck_transactions_price_positive"),
        sa.CheckConstraint("sequence > 0", name="ck_transactions_sequence_positive"),
        sa.CheckConstraint("shares > 0", name="ck_transactions_shares_positive"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "sequence", name="uq_transactions_user_sequence"),
    )
    op.create_index(
        "ix_transactions_user_ticker_position_type",
        "transactions",
        ["user_id", "ticker", "position_type"],
    )


def downgrade() -> None:
    """仅供本地回滚 M1 Schema；正常开发不得手工删除表。"""

    op.drop_index(
        "ix_transactions_user_ticker_position_type",
        table_name="transactions",
    )
    op.drop_table("transactions")
    op.drop_table("users")
