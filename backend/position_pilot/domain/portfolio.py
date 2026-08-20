"""Portfolio Structured State 与确定性计算。"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Decimal, DecimalException
from enum import StrEnum
from typing import Self
from uuid import UUID, uuid4

from position_pilot.domain.errors import (
    InsufficientCash,
    InsufficientShares,
    InvalidLedger,
    InvalidPortfolioValue,
)

DECIMAL_QUANTUM = Decimal("0.00000001")
MAX_PERSISTED_DECIMAL = Decimal("99999999999999999999.99999999")
TICKER_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")
MAX_DISPLAY_NAME_LENGTH = 200
MAX_REASON_LENGTH = 1000


class TransactionAction(StrEnum):
    """Transaction 对 Portfolio 的确定性影响类型。"""

    BUY = "BUY"
    SELL = "SELL"


class PositionType(StrEnum):
    """同一 Ticker 下必须独立维护的持仓意图。"""

    LONG_TERM = "LONG_TERM"
    SWING = "SWING"


def normalize_decimal(value: Decimal, *, field_name: str, allow_zero: bool = False) -> Decimal:
    """校验并规范化需要持久化的 Decimal。

    参数:
        value: 待校验数值。
        field_name: 用于错误说明的字段名。
        allow_zero: 是否允许零值。
    """

    if not isinstance(value, Decimal):
        raise InvalidPortfolioValue(f"{field_name} 必须使用 Decimal")
    if not value.is_finite():
        raise InvalidPortfolioValue(f"{field_name} 必须是有限数值")
    if value < 0 or (value == 0 and not allow_zero):
        qualifier = "非负数" if allow_zero else "正数"
        raise InvalidPortfolioValue(f"{field_name} 必须是{qualifier}")

    try:
        normalized = value.quantize(DECIMAL_QUANTUM, rounding=ROUND_HALF_EVEN)
    except DecimalException as error:
        raise InvalidPortfolioValue(f"{field_name} 超出可支持范围") from error

    if normalized != value:
        raise InvalidPortfolioValue(f"{field_name} 最多支持 8 位小数")
    if normalized > MAX_PERSISTED_DECIMAL:
        raise InvalidPortfolioValue(f"{field_name} 超出 NUMERIC(28, 8) 范围")
    return normalized


def calculate_amount(price: Decimal, shares: Decimal) -> Decimal:
    """由 price 与 shares 生成只读 Transaction amount。"""

    normalized_price = normalize_decimal(price, field_name="price")
    normalized_shares = normalize_decimal(shares, field_name="shares")
    try:
        amount = (normalized_price * normalized_shares).quantize(
            DECIMAL_QUANTUM,
            rounding=ROUND_HALF_EVEN,
        )
    except DecimalException as error:
        raise InvalidPortfolioValue("amount 超出可支持范围") from error
    return normalize_decimal(amount, field_name="amount")


def normalize_ticker(ticker: str) -> str:
    """规范化并校验 V1 美股或美国上市 ETF Ticker。"""

    normalized = ticker.strip().upper()
    if not TICKER_PATTERN.fullmatch(normalized):
        raise InvalidPortfolioValue("ticker 格式无效")
    return normalized


def normalize_timestamp(value: datetime) -> datetime:
    """要求时间包含时区并统一为 UTC。"""

    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidPortfolioValue("timestamp 必须包含时区")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class User:
    """Portfolio Ledger 的所有者及初始现金事实。"""

    id: UUID
    display_name: str
    initial_cash: Decimal
    created_at: datetime

    def __post_init__(self) -> None:
        display_name = self.display_name.strip()
        if not display_name or len(display_name) > MAX_DISPLAY_NAME_LENGTH:
            raise InvalidPortfolioValue("display_name 长度必须在 1 到 200 之间")
        object.__setattr__(self, "display_name", display_name)
        object.__setattr__(
            self,
            "initial_cash",
            normalize_decimal(self.initial_cash, field_name="initial_cash", allow_zero=True),
        )
        object.__setattr__(self, "created_at", normalize_timestamp(self.created_at))

    @classmethod
    def create(
        cls,
        *,
        display_name: str,
        initial_cash: Decimal,
        user_id: UUID | None = None,
        created_at: datetime | None = None,
    ) -> Self:
        """创建经过完整校验的新 User。"""

        return cls(
            id=user_id or uuid4(),
            display_name=display_name,
            initial_cash=initial_cash,
            created_at=created_at or datetime.now(UTC),
        )


@dataclass(frozen=True, slots=True)
class Transaction:
    """不可变 Ledger Record，amount 只能由 price 与 shares 派生。"""

    id: UUID
    user_id: UUID
    sequence: int
    ticker: str
    action: TransactionAction
    price: Decimal
    shares: Decimal
    amount: Decimal
    position_type: PositionType
    occurred_at: datetime
    reason: str | None

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise InvalidLedger("Transaction sequence 必须从 1 开始")
        if not isinstance(self.action, TransactionAction):
            raise InvalidPortfolioValue("action 必须是 BUY 或 SELL")
        if not isinstance(self.position_type, PositionType):
            raise InvalidPortfolioValue("position_type 必须是 LONG_TERM 或 SWING")
        object.__setattr__(self, "ticker", normalize_ticker(self.ticker))
        object.__setattr__(self, "price", normalize_decimal(self.price, field_name="price"))
        object.__setattr__(self, "shares", normalize_decimal(self.shares, field_name="shares"))
        derived_amount = calculate_amount(self.price, self.shares)
        if self.amount != derived_amount:
            raise InvalidPortfolioValue("amount 必须等于 price × shares 的派生结果")
        object.__setattr__(self, "amount", derived_amount)
        object.__setattr__(self, "occurred_at", normalize_timestamp(self.occurred_at))

        if self.reason is not None:
            reason = self.reason.strip()
            if len(reason) > MAX_REASON_LENGTH:
                raise InvalidPortfolioValue("reason 最多支持 1000 个字符")
            object.__setattr__(self, "reason", reason or None)

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        sequence: int,
        ticker: str,
        action: TransactionAction,
        price: Decimal,
        shares: Decimal,
        position_type: PositionType,
        occurred_at: datetime | None = None,
        reason: str | None = None,
        transaction_id: UUID | None = None,
    ) -> Self:
        """从写入字段创建 Transaction，调用方无法传入 amount。"""

        return cls(
            id=transaction_id or uuid4(),
            user_id=user_id,
            sequence=sequence,
            ticker=ticker,
            action=action,
            price=price,
            shares=shares,
            amount=calculate_amount(price, shares),
            position_type=position_type,
            occurred_at=occurred_at or datetime.now(UTC),
            reason=reason,
        )


@dataclass(frozen=True, slots=True)
class CashBalance:
    """从 Initial Cash 与 Ledger 派生的现金状态。"""

    user_id: UUID
    initial_cash: Decimal
    available_cash: Decimal


@dataclass(frozen=True, slots=True)
class Position:
    """单一 Ticker 与 Position Type 的派生持仓。"""

    ticker: str
    position_type: PositionType
    shares: Decimal
    cost_basis: Decimal
    average_cost: Decimal


@dataclass(frozen=True, slots=True)
class PortfolioState:
    """Transaction Ledger 重放后的完整 Structured State。"""

    user_id: UUID
    cash: CashBalance
    positions: tuple[Position, ...]
    transaction_count: int

    def get_position(self, ticker: str, position_type: PositionType) -> Position | None:
        """按规范化 Ticker 与 Position Type 查找持仓。"""

        normalized_ticker = normalize_ticker(ticker)
        return next(
            (
                position
                for position in self.positions
                if position.ticker == normalized_ticker and position.position_type is position_type
            ),
            None,
        )


@dataclass(slots=True)
class _PositionAccumulator:
    shares: Decimal
    cost_basis: Decimal


def rebuild_portfolio(user: User, transactions: list[Transaction]) -> PortfolioState:
    """按 Ledger sequence 重建 Cash、Position 与 Average Cost。

    参数:
        user: Ledger 所有者及 Initial Cash。
        transactions: 该用户的完整 Transaction Ledger。

    异常:
        InvalidLedger: Ledger 所有者或 sequence 不一致。
        InsufficientCash: 历史 BUY 超过当时可用现金。
        InsufficientShares: 历史 SELL 超过对应仓位 Shares。
    """

    ordered_transactions = sorted(transactions, key=lambda transaction: transaction.sequence)
    available_cash = user.initial_cash
    positions: dict[tuple[str, PositionType], _PositionAccumulator] = {}

    for expected_sequence, transaction in enumerate(ordered_transactions, start=1):
        if transaction.user_id != user.id:
            raise InvalidLedger("Ledger 包含其他 User 的 Transaction")
        if transaction.sequence != expected_sequence:
            raise InvalidLedger("Transaction sequence 必须连续且唯一")

        key = (transaction.ticker, transaction.position_type)
        position = positions.get(key)

        if transaction.action is TransactionAction.BUY:
            if transaction.amount > available_cash:
                raise InsufficientCash(available=available_cash, required=transaction.amount)
            available_cash -= transaction.amount
            if position is None:
                positions[key] = _PositionAccumulator(
                    shares=transaction.shares,
                    cost_basis=transaction.amount,
                )
            else:
                position.shares += transaction.shares
                position.cost_basis += transaction.amount
            continue

        available_shares = position.shares if position is not None else Decimal("0")
        if transaction.shares > available_shares:
            raise InsufficientShares(available=available_shares, required=transaction.shares)

        available_cash += transaction.amount
        if transaction.shares == available_shares:
            del positions[key]
            continue

        if position is None:
            raise InvalidLedger("SELL 缺少对应 Position")
        remaining_shares = position.shares - transaction.shares
        position.cost_basis *= remaining_shares / position.shares
        position.shares = remaining_shares

    derived_positions = tuple(
        Position(
            ticker=ticker,
            position_type=position_type,
            shares=accumulator.shares.quantize(DECIMAL_QUANTUM, rounding=ROUND_HALF_EVEN),
            cost_basis=accumulator.cost_basis.quantize(
                DECIMAL_QUANTUM,
                rounding=ROUND_HALF_EVEN,
            ),
            average_cost=(accumulator.cost_basis / accumulator.shares).quantize(
                DECIMAL_QUANTUM,
                rounding=ROUND_HALF_EVEN,
            ),
        )
        for (ticker, position_type), accumulator in sorted(
            positions.items(),
            key=lambda item: (item[0][0], item[0][1].value),
        )
    )

    return PortfolioState(
        user_id=user.id,
        cash=CashBalance(
            user_id=user.id,
            initial_cash=user.initial_cash,
            available_cash=available_cash.quantize(
                DECIMAL_QUANTUM,
                rounding=ROUND_HALF_EVEN,
            ),
        ),
        positions=derived_positions,
        transaction_count=len(ordered_transactions),
    )
