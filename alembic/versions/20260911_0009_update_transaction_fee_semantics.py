"""支持含费买入成本与实际卖出费用。"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260911_0009"
down_revision: str | Sequence[str] | None = "20260910_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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
    """保留旧记录，同时允许两种券商报告费用口径。"""

    op.drop_constraint("ck_transactions_commission_derived", "transactions", type_="check")
    op.drop_constraint(
        "ck_transactions_fee_schedule_supported",
        "transactions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_transactions_commission_derived",
        "transactions",
        f"""
        (fee_schedule = 'IBKR_PRO_TIERED_US_2026_08'
            AND commission = {COMMISSION_DERIVATION_SQL})
        OR (fee_schedule = 'BUY_COST_INCLUDED' AND action = 'BUY' AND commission = 0)
        OR (fee_schedule = 'SELL_ACTUAL_FEE' AND action = 'SELL')
        """,
    )
    op.create_check_constraint(
        "ck_transactions_fee_schedule_supported",
        "transactions",
        "fee_schedule IN ('IBKR_PRO_TIERED_US_2026_08', 'BUY_COST_INCLUDED', 'SELL_ACTUAL_FEE')",
    )


def downgrade() -> None:
    """恢复旧版自动估算手续费约束；执行前需清理新版交易。"""

    op.drop_constraint(
        "ck_transactions_fee_schedule_supported",
        "transactions",
        type_="check",
    )
    op.drop_constraint("ck_transactions_commission_derived", "transactions", type_="check")
    op.create_check_constraint(
        "ck_transactions_commission_derived",
        "transactions",
        f"commission = {COMMISSION_DERIVATION_SQL}",
    )
    op.create_check_constraint(
        "ck_transactions_fee_schedule_supported",
        "transactions",
        "fee_schedule = 'IBKR_PRO_TIERED_US_2026_08'",
    )
