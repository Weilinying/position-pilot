"""Portfolio SQLAlchemy 持久化模型。"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from position_pilot.database import Base

AMOUNT_DERIVATION_CHECK = """
amount = round(price * shares, 8) -
    CASE
        WHEN price * shares * 100000000 - trunc(price * shares * 100000000) = 0.5
            AND mod(trunc(price * shares * 100000000), 2) = 0
        THEN 0.00000001
        ELSE 0
    END
"""
COMMISSION_RAW_SQL = """
CASE
    WHEN shares = trunc(shares)
    THEN LEAST(GREATEST(shares * 0.0035, 0.35), amount * 0.01)
    ELSE GREATEST(amount * 0.01, 0.01)
END
"""
COMMISSION_DERIVATION_CHECK = f"""
commission = round(({COMMISSION_RAW_SQL}), 8) -
    CASE
        WHEN ({COMMISSION_RAW_SQL}) * 100000000
            - trunc(({COMMISSION_RAW_SQL}) * 100000000) = 0.5
            AND mod(trunc(({COMMISSION_RAW_SQL}) * 100000000), 2) = 0
        THEN 0.00000001
        ELSE 0
    END
"""


class UserModel(Base):
    """User 与 Initial Cash 的持久化记录。"""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("initial_cash >= 0", name="ck_users_initial_cash_non_negative"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(200))
    initial_cash: Mapped[Decimal] = mapped_column(Numeric(28, 8))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TransactionModel(Base):
    """不可变 Transaction Ledger 的持久化记录。"""

    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("user_id", "sequence", name="uq_transactions_user_sequence"),
        CheckConstraint("sequence > 0", name="ck_transactions_sequence_positive"),
        CheckConstraint("price > 0", name="ck_transactions_price_positive"),
        CheckConstraint("shares > 0", name="ck_transactions_shares_positive"),
        CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        CheckConstraint("commission >= 0", name="ck_transactions_commission_non_negative"),
        CheckConstraint("action IN ('BUY', 'SELL')", name="transaction_action"),
        CheckConstraint(
            "position_type IN ('LONG_TERM', 'SWING')",
            name="position_type",
        ),
        CheckConstraint(
            AMOUNT_DERIVATION_CHECK,
            name="ck_transactions_amount_derived",
        ),
        CheckConstraint(
            COMMISSION_DERIVATION_CHECK,
            name="ck_transactions_commission_derived",
        ),
        CheckConstraint(
            "fee_schedule = 'IBKR_PRO_TIERED_US_2026_08'",
            name="ck_transactions_fee_schedule_supported",
        ),
        Index(
            "ix_transactions_user_ticker_position_type",
            "user_id",
            "ticker",
            "position_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(BigInteger)
    ticker: Mapped[str] = mapped_column(String(10))
    action: Mapped[str] = mapped_column(String(4))
    price: Mapped[Decimal] = mapped_column(Numeric(28, 8))
    shares: Mapped[Decimal] = mapped_column(Numeric(28, 8))
    amount: Mapped[Decimal] = mapped_column(Numeric(28, 8))
    commission: Mapped[Decimal] = mapped_column(Numeric(28, 8))
    fee_schedule: Mapped[str] = mapped_column(String(40))
    position_type: Mapped[str] = mapped_column(String(9))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text)
