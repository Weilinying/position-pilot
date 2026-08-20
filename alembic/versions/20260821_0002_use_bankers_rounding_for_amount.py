"""让 amount CHECK 使用银行家舍入。"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260821_0002"
down_revision: str | Sequence[str] | None = "20260820_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AMOUNT_DERIVATION_CHECK = """
amount = round(price * shares, 8) -
    CASE
        WHEN price * shares * 100000000 - trunc(price * shares * 100000000) = 0.5
            AND mod(trunc(price * shares * 100000000), 2) = 0
        THEN 0.00000001
        ELSE 0
    END
"""


def upgrade() -> None:
    """修正 PostgreSQL midpoint 舍入与领域规则不一致的问题。"""

    op.drop_constraint(
        "ck_transactions_amount_derived",
        "transactions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_transactions_amount_derived",
        "transactions",
        AMOUNT_DERIVATION_CHECK,
    )


def downgrade() -> None:
    """恢复 PostgreSQL 默认 round 约束。"""

    op.drop_constraint(
        "ck_transactions_amount_derived",
        "transactions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_transactions_amount_derived",
        "transactions",
        "amount = round(price * shares, 8)",
    )
