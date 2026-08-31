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


class AccountModel(Base):
    """最小本地登录身份及其可选单一 Portfolio Ownership。"""

    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("email", name="uq_accounts_email"),
        UniqueConstraint("portfolio_user_id", name="uq_accounts_portfolio_user"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320))
    display_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(Text)
    portfolio_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuthSessionModel(Base):
    """可撤销且只保存 Token Digest 的本地 Session。"""

    __tablename__ = "auth_sessions"
    __table_args__ = (
        UniqueConstraint("token_digest", name="uq_auth_sessions_token_digest"),
        Index("ix_auth_sessions_account_expires", "account_id", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_digest: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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
            "position_type IN ('LONG_TERM', 'SWING', 'UNSPECIFIED')",
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
    position_type: Mapped[str] = mapped_column(String(11))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text)


class OpeningPositionModel(Base):
    """系统开始跟踪时接收的不可变持仓起始事实。"""

    __tablename__ = "opening_positions"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "ticker",
            "position_type",
            name="uq_opening_positions_user_position",
        ),
        CheckConstraint("shares > 0", name="ck_opening_positions_shares_positive"),
        CheckConstraint(
            "average_cost > 0",
            name="ck_opening_positions_average_cost_positive",
        ),
        CheckConstraint(
            "position_type IN ('LONG_TERM', 'SWING', 'UNSPECIFIED')",
            name="opening_position_type",
        ),
        Index(
            "ix_opening_positions_user_position",
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
    ticker: Mapped[str] = mapped_column(String(10))
    shares: Mapped[Decimal] = mapped_column(Numeric(28, 8))
    average_cost: Mapped[Decimal] = mapped_column(Numeric(28, 8))
    position_type: Mapped[str] = mapped_column(String(11))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CashEventModel(Base):
    """Portfolio 创建后的不可变 Cash Event Ledger。"""

    __tablename__ = "cash_events"
    __table_args__ = (
        UniqueConstraint("user_id", "sequence", name="uq_cash_events_user_sequence"),
        CheckConstraint("sequence > 0", name="ck_cash_events_sequence_positive"),
        CheckConstraint("amount > 0", name="ck_cash_events_amount_positive"),
        CheckConstraint(
            "event_type IN ('DEPOSIT', 'WITHDRAWAL')",
            name="cash_event_type",
        ),
        Index("ix_cash_events_user_occurred_at", "user_id", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(BigInteger)
    event_type: Mapped[str] = mapped_column(String(10))
    amount: Mapped[Decimal] = mapped_column(Numeric(28, 8))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text)
