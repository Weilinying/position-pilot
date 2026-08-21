"""为 Transaction 增加版本化 IBKR 基础佣金。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0003"
down_revision: str | Sequence[str] | None = "20260821_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COMMISSION_SCHEDULE = "IBKR_PRO_TIERED_US_2026_08"
COMMISSION_RAW_SQL = """
CASE
    WHEN shares = trunc(shares)
    THEN LEAST(GREATEST(shares * 0.0035, 0.35), amount * 0.01)
    ELSE GREATEST(amount * 0.01, 0.01)
END
"""
COMMISSION_DERIVATION_SQL = f"""
round(({COMMISSION_RAW_SQL}), 8) -
    CASE
        WHEN ({COMMISSION_RAW_SQL}) * 100000000
            - trunc(({COMMISSION_RAW_SQL}) * 100000000) = 0.5
            AND mod(trunc(({COMMISSION_RAW_SQL}) * 100000000), 2) = 0
        THEN 0.00000001
        ELSE 0
    END
"""


def upgrade() -> None:
    """回填现有 Ledger，并约束手续费只能由批准费率派生。"""

    op.add_column(
        "transactions",
        sa.Column("commission", sa.Numeric(precision=28, scale=8), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("fee_schedule", sa.String(length=40), nullable=True),
    )
    op.execute(
        sa.text(
            f"""
            UPDATE transactions
            SET commission = {COMMISSION_DERIVATION_SQL},
                fee_schedule = :fee_schedule
            """
        ).bindparams(fee_schedule=COMMISSION_SCHEDULE)
    )
    op.alter_column("transactions", "commission", nullable=False)
    op.alter_column("transactions", "fee_schedule", nullable=False)
    op.create_check_constraint(
        "ck_transactions_commission_non_negative",
        "transactions",
        "commission >= 0",
    )
    op.create_check_constraint(
        "ck_transactions_commission_derived",
        "transactions",
        f"commission = {COMMISSION_DERIVATION_SQL}",
    )
    op.create_check_constraint(
        "ck_transactions_fee_schedule_supported",
        "transactions",
        f"fee_schedule = '{COMMISSION_SCHEDULE}'",
    )


def downgrade() -> None:
    """移除手续费派生字段，不改变原 Transaction Ledger。"""

    op.drop_constraint(
        "ck_transactions_fee_schedule_supported",
        "transactions",
        type_="check",
    )
    op.drop_constraint(
        "ck_transactions_commission_derived",
        "transactions",
        type_="check",
    )
    op.drop_constraint(
        "ck_transactions_commission_non_negative",
        "transactions",
        type_="check",
    )
    op.drop_column("transactions", "fee_schedule")
    op.drop_column("transactions", "commission")
