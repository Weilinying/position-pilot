"""Portfolio Structured State 与确定性计算。"""

import re
from dataclasses import dataclass, replace
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
MAX_SOURCE_LENGTH = 100
MAX_SOURCE_INFO_LENGTH = 1000
COMMISSION_SCHEDULE = "IBKR_PRO_TIERED_US_2026_08"
BUY_COST_INCLUDED_FEE_SCHEDULE = "BUY_COST_INCLUDED"
SELL_ACTUAL_FEE_SCHEDULE = "SELL_ACTUAL_FEE"
IBKR_TIERED_PER_SHARE = Decimal("0.0035")
IBKR_TIERED_MINIMUM = Decimal("0.35")
IBKR_TIERED_MAXIMUM_RATE = Decimal("0.01")
IBKR_FRACTIONAL_MINIMUM = Decimal("0.01")


class TransactionAction(StrEnum):
    """Transaction 对 Portfolio 的确定性影响类型。"""

    BUY = "BUY"
    SELL = "SELL"


class CashEventType(StrEnum):
    """Portfolio 创建后的确定性现金调整类型。"""

    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"


class PositionType(StrEnum):
    """同一 Ticker 下必须独立维护的持仓意图。"""

    LONG_TERM = "LONG_TERM"
    SWING = "SWING"
    UNSPECIFIED = "UNSPECIFIED"


class PositionLotSource(StrEnum):
    """当前批次对应的不可变来源事实。"""

    BUY = "BUY"
    OPENING = "OPENING"
    RECONCILIATION = "RECONCILIATION"


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


def calculate_commission(amount: Decimal, shares: Decimal) -> Decimal:
    """按已批准的 IBKR Pro Tiered 第一档计算基础佣金。"""

    normalized_amount = normalize_decimal(amount, field_name="amount")
    normalized_shares = normalize_decimal(shares, field_name="shares")
    if normalized_shares == normalized_shares.to_integral_value():
        per_share_commission = normalized_shares * IBKR_TIERED_PER_SHARE
        raw_commission = min(
            max(per_share_commission, IBKR_TIERED_MINIMUM),
            normalized_amount * IBKR_TIERED_MAXIMUM_RATE,
        )
    else:
        raw_commission = max(
            normalized_amount * IBKR_TIERED_MAXIMUM_RATE,
            IBKR_FRACTIONAL_MINIMUM,
        )

    try:
        commission = raw_commission.quantize(DECIMAL_QUANTUM, rounding=ROUND_HALF_EVEN)
    except DecimalException as error:
        raise InvalidPortfolioValue("commission 超出可支持范围") from error
    return normalize_decimal(commission, field_name="commission", allow_zero=True)


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


def normalize_reason(reason: str | None) -> str | None:
    """规范化可选 Ledger 原因并限制持久化长度。"""

    if reason is None:
        return None
    normalized = reason.strip()
    if len(normalized) > MAX_REASON_LENGTH:
        raise InvalidPortfolioValue("reason 最多支持 1000 个字符")
    return normalized or None


def normalize_source(source: str) -> str:
    """规范化不可变事件来源，并限制持久化长度。"""

    normalized = source.strip()
    if not normalized or len(normalized) > MAX_SOURCE_LENGTH:
        raise InvalidPortfolioValue("source 长度必须在 1 到 100 个字符之间")
    return normalized


def normalize_source_info(source_info: str | None) -> str | None:
    """规范化来源补充信息，并限制持久化长度。"""

    if source_info is None:
        return None
    normalized = source_info.strip()
    if len(normalized) > MAX_SOURCE_INFO_LENGTH:
        raise InvalidPortfolioValue("source_info 最多支持 1000 个字符")
    return normalized or None


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
    """不可变交易记录，保存金额、费用口径与经济顺序。"""

    id: UUID
    user_id: UUID
    sequence: int
    ticker: str
    action: TransactionAction
    price: Decimal
    shares: Decimal
    amount: Decimal
    commission: Decimal
    fee_schedule: str
    position_type: PositionType
    occurred_at: datetime
    reason: str | None

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise InvalidLedger("Transaction sequence 必须从 1 开始")
        if not isinstance(self.action, TransactionAction):
            raise InvalidPortfolioValue("action 必须是 BUY 或 SELL")
        if not isinstance(self.position_type, PositionType):
            raise InvalidPortfolioValue("position_type 必须是 LONG_TERM、SWING 或 UNSPECIFIED")
        object.__setattr__(self, "ticker", normalize_ticker(self.ticker))
        object.__setattr__(self, "price", normalize_decimal(self.price, field_name="price"))
        object.__setattr__(self, "shares", normalize_decimal(self.shares, field_name="shares"))
        derived_amount = calculate_amount(self.price, self.shares)
        if self.amount != derived_amount:
            raise InvalidPortfolioValue("amount 必须等于 price × shares 的派生结果")
        object.__setattr__(self, "amount", derived_amount)
        normalized_commission = normalize_decimal(
            self.commission,
            field_name="commission",
            allow_zero=True,
        )
        if self.fee_schedule == COMMISSION_SCHEDULE:
            derived_commission = calculate_commission(derived_amount, self.shares)
            if normalized_commission != derived_commission:
                raise InvalidPortfolioValue("旧版 commission 必须由已批准费率派生")
            normalized_commission = derived_commission
        elif self.fee_schedule == BUY_COST_INCLUDED_FEE_SCHEDULE:
            if self.action is not TransactionAction.BUY or normalized_commission != 0:
                raise InvalidPortfolioValue("含费买入成本只能用于 commission 为零的 BUY")
        elif self.fee_schedule == SELL_ACTUAL_FEE_SCHEDULE:
            if self.action is not TransactionAction.SELL:
                raise InvalidPortfolioValue("实际卖出费用只能用于 SELL")
        else:
            raise InvalidPortfolioValue("fee_schedule 不受支持")
        object.__setattr__(self, "commission", normalized_commission)
        object.__setattr__(self, "occurred_at", normalize_timestamp(self.occurred_at))

        object.__setattr__(self, "reason", normalize_reason(self.reason))

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
        fee: Decimal | None = Decimal("0"),
        position_type: PositionType | None = None,
        occurred_at: datetime | None = None,
        reason: str | None = None,
        transaction_id: UUID | None = None,
    ) -> Self:
        """创建交易；新录入 BUY 使用含费成本，SELL 保存实际费用。

        `fee=None` 仅用于恢复旧版自动估算手续费的内部调用。
        """

        amount = calculate_amount(price, shares)
        if fee is None:
            commission = calculate_commission(amount, shares)
            fee_schedule = COMMISSION_SCHEDULE
        else:
            commission = normalize_decimal(fee, field_name="fee", allow_zero=True)
            fee_schedule = (
                BUY_COST_INCLUDED_FEE_SCHEDULE
                if action is TransactionAction.BUY
                else SELL_ACTUAL_FEE_SCHEDULE
            )

        return cls(
            id=transaction_id or uuid4(),
            user_id=user_id,
            sequence=sequence,
            ticker=ticker,
            action=action,
            price=price,
            shares=shares,
            amount=amount,
            commission=commission,
            fee_schedule=fee_schedule,
            position_type=(
                position_type if position_type is not None else PositionType.UNSPECIFIED
            ),
            occurred_at=occurred_at or datetime.now(UTC),
            reason=reason,
        )


@dataclass(frozen=True, slots=True)
class OpeningPosition:
    """系统开始跟踪时接收的不可变持仓起始事实。"""

    id: UUID
    user_id: UUID
    ticker: str
    shares: Decimal
    average_cost: Decimal
    position_type: PositionType
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.position_type, PositionType):
            raise InvalidPortfolioValue("position_type 必须是 LONG_TERM、SWING 或 UNSPECIFIED")
        object.__setattr__(self, "ticker", normalize_ticker(self.ticker))
        object.__setattr__(self, "shares", normalize_decimal(self.shares, field_name="shares"))
        object.__setattr__(
            self,
            "average_cost",
            normalize_decimal(self.average_cost, field_name="average_cost"),
        )
        object.__setattr__(self, "recorded_at", normalize_timestamp(self.recorded_at))
        # 起始成本由用户申报的平均成本与股数确定，验证其能安全进入 NUMERIC 边界。
        calculate_amount(self.average_cost, self.shares)

    @property
    def cost_basis(self) -> Decimal:
        """由起始 Shares 与 Average Cost 确定性计算 Cost Basis。"""

        return calculate_amount(self.average_cost, self.shares)

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        ticker: str,
        shares: Decimal,
        average_cost: Decimal,
        position_type: PositionType | None = None,
        recorded_at: datetime | None = None,
        opening_position_id: UUID | None = None,
    ) -> Self:
        """创建不带经济事件顺序的 Opening Position。"""

        return cls(
            id=opening_position_id or uuid4(),
            user_id=user_id,
            ticker=ticker,
            shares=shares,
            average_cost=average_cost,
            position_type=(
                position_type if position_type is not None else PositionType.UNSPECIFIED
            ),
            recorded_at=recorded_at or datetime.now(UTC),
        )


@dataclass(frozen=True, slots=True)
class PositionReconciliation:
    """不可变的外部持仓校准事实，不产生交易或现金影响。"""

    id: UUID
    user_id: UUID
    ticker: str
    target_shares: Decimal
    target_average_cost: Decimal
    position_type: PositionType
    source: str
    confirmed_at: datetime
    broker: str | None = None
    source_info: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.position_type, PositionType):
            raise InvalidPortfolioValue("position_type 必须是 LONG_TERM、SWING 或 UNSPECIFIED")
        object.__setattr__(self, "ticker", normalize_ticker(self.ticker))
        object.__setattr__(
            self,
            "target_shares",
            normalize_decimal(self.target_shares, field_name="target_shares"),
        )
        object.__setattr__(
            self,
            "target_average_cost",
            normalize_decimal(self.target_average_cost, field_name="target_average_cost"),
        )
        # 校准后的成本基数仍必须能安全进入与 Transaction 相同的金额边界。
        calculate_amount(self.target_average_cost, self.target_shares)
        object.__setattr__(self, "source", normalize_source(self.source))
        object.__setattr__(self, "confirmed_at", normalize_timestamp(self.confirmed_at))
        object.__setattr__(
            self,
            "broker",
            normalize_source(self.broker) if self.broker is not None else None,
        )
        object.__setattr__(self, "source_info", normalize_source_info(self.source_info))

    @property
    def target_cost_basis(self) -> Decimal:
        """由目标 Shares 与目标 Average Cost 确定性计算校准成本基数。"""

        return calculate_amount(self.target_average_cost, self.target_shares)

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        ticker: str,
        target_shares: Decimal,
        target_average_cost: Decimal,
        source: str,
        position_type: PositionType | None = None,
        confirmed_at: datetime | None = None,
        broker: str | None = None,
        source_info: str | None = None,
        reconciliation_id: UUID | None = None,
    ) -> Self:
        """创建一次不生成交易与现金变化的持仓校准事件。"""

        return cls(
            id=reconciliation_id or uuid4(),
            user_id=user_id,
            ticker=ticker,
            target_shares=target_shares,
            target_average_cost=target_average_cost,
            position_type=(
                position_type if position_type is not None else PositionType.UNSPECIFIED
            ),
            source=source,
            confirmed_at=confirmed_at or datetime.now(UTC),
            broker=broker,
            source_info=source_info,
        )


@dataclass(frozen=True, slots=True)
class CashEvent:
    """不可变 Cash Event Ledger Record。"""

    id: UUID
    user_id: UUID
    sequence: int
    event_type: CashEventType
    amount: Decimal
    occurred_at: datetime
    reason: str | None

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise InvalidLedger("Cash Event sequence 必须从 1 开始")
        if not isinstance(self.event_type, CashEventType):
            raise InvalidPortfolioValue("event_type 必须是 DEPOSIT 或 WITHDRAWAL")
        object.__setattr__(self, "amount", normalize_decimal(self.amount, field_name="amount"))
        object.__setattr__(self, "occurred_at", normalize_timestamp(self.occurred_at))
        object.__setattr__(self, "reason", normalize_reason(self.reason))

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        sequence: int,
        event_type: CashEventType,
        amount: Decimal,
        occurred_at: datetime,
        reason: str | None = None,
        cash_event_id: UUID | None = None,
    ) -> Self:
        """从显式发生时间与正数金额创建 Cash Event。"""

        return cls(
            id=cash_event_id or uuid4(),
            user_id=user_id,
            sequence=sequence,
            event_type=event_type,
            amount=amount,
            occurred_at=occurred_at,
            reason=reason,
        )


def resequence_transactions(transactions: list[Transaction]) -> list[Transaction]:
    """按交易发生时间派生连续经济顺序，并稳定保留同一时间的原相对顺序。"""

    ordered = sorted(
        transactions, key=lambda transaction: (transaction.occurred_at, transaction.sequence)
    )
    return [
        transaction
        if transaction.sequence == economic_sequence
        else replace(transaction, sequence=economic_sequence)
        for economic_sequence, transaction in enumerate(ordered, start=1)
    ]


def resequence_cash_events(cash_events: list[CashEvent]) -> list[CashEvent]:
    """按事件发生时间派生独立、连续且稳定的 Cash Event sequence。"""

    ordered = sorted(cash_events, key=lambda event: (event.occurred_at, event.sequence))
    return [
        event if event.sequence == economic_sequence else replace(event, sequence=economic_sequence)
        for economic_sequence, event in enumerate(ordered, start=1)
    ]


@dataclass(frozen=True, slots=True)
class CashBalance:
    """从 Initial Cash 与 Ledger 派生的现金状态。"""

    user_id: UUID
    initial_cash: Decimal
    available_cash: Decimal
    total_deposits: Decimal = Decimal("0")
    total_withdrawals: Decimal = Decimal("0")


@dataclass(frozen=True, slots=True)
class LotAllocation:
    """一笔 SELL 对一个来源批次的明确股数分配。"""

    id: UUID
    user_id: UUID
    sell_transaction_id: UUID
    lot_id: UUID
    shares: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "shares", normalize_decimal(self.shares, field_name="shares"))

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        sell_transaction_id: UUID,
        lot_id: UUID,
        shares: Decimal,
        allocation_id: UUID | None = None,
    ) -> "LotAllocation":
        """创建不可变的卖出批次分配。"""

        return cls(
            id=allocation_id or uuid4(),
            user_id=user_id,
            sell_transaction_id=sell_transaction_id,
            lot_id=lot_id,
            shares=shares,
        )


@dataclass(frozen=True, slots=True)
class LotClassificationChange:
    """一个剩余批次的策略类型变更事实。"""

    id: UUID
    user_id: UUID
    lot_id: UUID
    position_type: PositionType
    effective_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.position_type, PositionType):
            raise InvalidPortfolioValue("position_type 无效")
        object.__setattr__(self, "effective_at", normalize_timestamp(self.effective_at))

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        lot_id: UUID,
        position_type: PositionType,
        effective_at: datetime,
        change_id: UUID | None = None,
    ) -> "LotClassificationChange":
        """创建不可变的批次类型变更。"""

        return cls(
            id=change_id or uuid4(),
            user_id=user_id,
            lot_id=lot_id,
            position_type=position_type,
            effective_at=effective_at,
        )


@dataclass(frozen=True, slots=True)
class BuyTransactionCorrection:
    """一笔 BUY 的不可变更正记录，原交易继续保留。"""

    id: UUID
    user_id: UUID
    transaction_id: UUID
    price: Decimal
    shares: Decimal
    occurred_at: datetime
    reason: str | None
    corrected_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "price", normalize_decimal(self.price, field_name="price"))
        object.__setattr__(self, "shares", normalize_decimal(self.shares, field_name="shares"))
        calculate_amount(self.price, self.shares)
        object.__setattr__(self, "occurred_at", normalize_timestamp(self.occurred_at))
        object.__setattr__(self, "reason", normalize_reason(self.reason))
        object.__setattr__(self, "corrected_at", normalize_timestamp(self.corrected_at))

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        transaction_id: UUID,
        price: Decimal,
        shares: Decimal,
        occurred_at: datetime,
        reason: str | None,
        corrected_at: datetime,
        correction_id: UUID | None = None,
    ) -> "BuyTransactionCorrection":
        """创建一版 BUY 有效成交字段的更正事实。"""

        return cls(
            id=correction_id or uuid4(),
            user_id=user_id,
            transaction_id=transaction_id,
            price=price,
            shares=shares,
            occurred_at=occurred_at,
            reason=reason,
            corrected_at=corrected_at,
        )


@dataclass(frozen=True, slots=True)
class PositionLot:
    """由来源事实与后续事件派生的当前剩余批次。"""

    id: UUID
    ticker: str
    position_type: PositionType
    source: PositionLotSource
    acquired_shares: Decimal
    remaining_shares: Decimal
    cost_basis: Decimal
    average_cost: Decimal
    entry_price: Decimal | None
    purchased_at: datetime | None


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
    """Opening State、校准事实与经济 Ledger 重放后的完整 Structured State。"""

    user_id: UUID
    cash: CashBalance
    positions: tuple[Position, ...]
    transaction_count: int
    lots: tuple[PositionLot, ...] = ()
    cash_event_count: int = 0
    reconciliation_count: int = 0

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
    reconciled_average_cost: Decimal | None = None


@dataclass(slots=True)
class _LotAccumulator:
    id: UUID
    ticker: str
    position_type: PositionType
    source: PositionLotSource
    acquired_shares: Decimal
    remaining_shares: Decimal
    cost_basis: Decimal
    average_cost: Decimal
    entry_price: Decimal | None
    purchased_at: datetime | None


def apply_buy_transaction_corrections(
    user: User,
    transactions: list[Transaction],
    corrections: list[BuyTransactionCorrection] | None = None,
) -> list[Transaction]:
    """将每笔 BUY 的最新更正投影为有效交易，并重新派生经济顺序。"""

    transactions_by_id = {transaction.id: transaction for transaction in transactions}
    latest_corrections: dict[UUID, BuyTransactionCorrection] = {}
    for correction_record in sorted(
        corrections or [],
        key=lambda item: (item.corrected_at, item.id.hex),
    ):
        if correction_record.user_id != user.id:
            raise InvalidLedger("BUY Correction 包含其他 User 的记录")
        transaction = transactions_by_id.get(correction_record.transaction_id)
        if transaction is None or transaction.action is not TransactionAction.BUY:
            raise InvalidLedger("BUY Correction 引用了不存在或非 BUY 的 Transaction")
        latest_corrections[correction_record.transaction_id] = correction_record
    effective_transactions = []
    for transaction in transactions:
        effective_correction = latest_corrections.get(transaction.id)
        if effective_correction is None:
            effective_transactions.append(transaction)
            continue
        amount = calculate_amount(effective_correction.price, effective_correction.shares)
        commission = (
            calculate_commission(amount, effective_correction.shares)
            if transaction.fee_schedule == COMMISSION_SCHEDULE
            else Decimal("0")
        )
        effective_transactions.append(
            replace(
                transaction,
                price=effective_correction.price,
                shares=effective_correction.shares,
                amount=amount,
                commission=commission,
                occurred_at=effective_correction.occurred_at,
                reason=effective_correction.reason,
            )
        )
    return resequence_transactions(effective_transactions)


def rebuild_portfolio(
    user: User,
    transactions: list[Transaction],
    cash_events: list[CashEvent] | None = None,
    opening_positions: list[OpeningPosition] | None = None,
    reconciliations: list[PositionReconciliation] | None = None,
    lot_allocations: list[LotAllocation] | None = None,
    lot_classification_changes: list[LotClassificationChange] | None = None,
    buy_transaction_corrections: list[BuyTransactionCorrection] | None = None,
) -> PortfolioState:
    """从 Opening State 开始，按实际发生时间重建当前 Portfolio。

    参数:
        user: Ledger 所有者及 Initial Cash。
        transactions: 该用户的完整 Transaction Ledger。
        cash_events: 该用户的完整 Cash Event Ledger。
        opening_positions: 系统开始跟踪时接收的完整持仓起始事实。
        reconciliations: 该用户按确认时间发生的不可变持仓校准事实。
        lot_allocations: SELL 对来源批次的明确分配。
        lot_classification_changes: 批次策略类型变更事实。
        buy_transaction_corrections: BUY 的不可变更正事实。

    异常:
        InvalidLedger: Ledger 所有者或 sequence 不一致。
        InsufficientCash: 历史 BUY 或 WITHDRAWAL 超过当时可用现金。
        InsufficientShares: 历史 SELL 超过对应仓位 Shares。
    """

    original_transactions = sorted(transactions, key=lambda transaction: transaction.sequence)
    ordered_cash_events = sorted(cash_events or [], key=lambda event: event.sequence)
    ordered_opening_positions = sorted(
        opening_positions or [],
        key=lambda position: (position.ticker, position.position_type.value),
    )
    ordered_reconciliations = sorted(
        reconciliations or [],
        key=lambda reconciliation: (reconciliation.confirmed_at, reconciliation.id.hex),
    )
    ordered_classification_changes = sorted(
        lot_classification_changes or [],
        key=lambda change: (change.effective_at, change.id.hex),
    )
    opening_keys: set[tuple[str, PositionType]] = set()
    for opening_position in ordered_opening_positions:
        if opening_position.user_id != user.id:
            raise InvalidLedger("Opening State 包含其他 User 的 Position")
        key = (opening_position.ticker, opening_position.position_type)
        if key in opening_keys:
            raise InvalidLedger("Opening State 的 ticker 与 position_type 必须唯一")
        opening_keys.add(key)
    for expected_sequence, transaction in enumerate(original_transactions, start=1):
        if transaction.user_id != user.id:
            raise InvalidLedger("Ledger 包含其他 User 的 Transaction")
        if transaction.sequence != expected_sequence:
            raise InvalidLedger("Transaction sequence 必须连续且唯一")
    ordered_transactions = apply_buy_transaction_corrections(
        user,
        original_transactions,
        buy_transaction_corrections,
    )
    transactions_by_id = {transaction.id: transaction for transaction in ordered_transactions}
    if len(transactions_by_id) != len(ordered_transactions):
        raise InvalidLedger("Transaction ID 必须唯一")
    for expected_sequence, cash_event in enumerate(ordered_cash_events, start=1):
        if cash_event.user_id != user.id:
            raise InvalidLedger("Ledger 包含其他 User 的 Cash Event")
        if cash_event.sequence != expected_sequence:
            raise InvalidLedger("Cash Event sequence 必须连续且唯一")
    reconciliation_ids: set[UUID] = set()
    for reconciliation in ordered_reconciliations:
        if reconciliation.user_id != user.id:
            raise InvalidLedger("Reconciliation 包含其他 User 的 Position")
        if reconciliation.id in reconciliation_ids:
            raise InvalidLedger("Reconciliation ID 必须唯一")
        reconciliation_ids.add(reconciliation.id)

    allocations_by_transaction: dict[UUID, list[LotAllocation]] = {}
    allocation_keys: set[tuple[UUID, UUID]] = set()
    for allocation in lot_allocations or []:
        if allocation.user_id != user.id:
            raise InvalidLedger("Lot Allocation 包含其他 User 的记录")
        sell_transaction = transactions_by_id.get(allocation.sell_transaction_id)
        if sell_transaction is None or sell_transaction.action is not TransactionAction.SELL:
            raise InvalidLedger("Lot Allocation 必须引用存在的 SELL Transaction")
        allocation_key = (allocation.sell_transaction_id, allocation.lot_id)
        if allocation_key in allocation_keys:
            raise InvalidLedger("同一 SELL 不能重复分配同一 Lot")
        allocation_keys.add(allocation_key)
        allocations_by_transaction.setdefault(allocation.sell_transaction_id, []).append(allocation)
    for change in ordered_classification_changes:
        if change.user_id != user.id:
            raise InvalidLedger("Lot Classification Change 包含其他 User 的记录")

    # 跨表没有全局 sequence；同一时间固定按现金、校准、交易处理，保证重建结果稳定。
    ledger_records: list[
        Transaction | CashEvent | PositionReconciliation | LotClassificationChange
    ] = sorted(
        [
            *ordered_transactions,
            *ordered_cash_events,
            *ordered_reconciliations,
            *ordered_classification_changes,
        ],
        key=lambda record: (
            (
                record.occurred_at
                if isinstance(record, (Transaction, CashEvent))
                else record.confirmed_at
                if isinstance(record, PositionReconciliation)
                else record.effective_at
            ),
            (
                0
                if isinstance(record, CashEvent)
                else 1
                if isinstance(record, PositionReconciliation)
                else 2
                if isinstance(record, Transaction)
                else 3
            ),
            record.sequence if isinstance(record, (Transaction, CashEvent)) else record.id.hex,
        ),
    )
    available_cash = user.initial_cash
    total_deposits = Decimal("0")
    total_withdrawals = Decimal("0")
    lots: dict[UUID, _LotAccumulator] = {
        position.id: _LotAccumulator(
            id=position.id,
            ticker=position.ticker,
            position_type=position.position_type,
            source=PositionLotSource.OPENING,
            acquired_shares=position.shares,
            remaining_shares=position.shares,
            cost_basis=position.cost_basis,
            average_cost=position.average_cost,
            entry_price=None,
            purchased_at=None,
        )
        for position in ordered_opening_positions
    }

    for record in ledger_records:
        if isinstance(record, CashEvent):
            if record.event_type is CashEventType.DEPOSIT:
                available_cash += record.amount
                total_deposits += record.amount
                continue
            if record.amount > available_cash:
                raise InsufficientCash(available=available_cash, required=record.amount)
            available_cash -= record.amount
            total_withdrawals += record.amount
            continue

        if isinstance(record, PositionReconciliation):
            replaced_lot_ids = [
                lot_id
                for lot_id, lot in lots.items()
                if lot.ticker == record.ticker and lot.position_type is record.position_type
            ]
            for lot_id in replaced_lot_ids:
                del lots[lot_id]
            lots[record.id] = _LotAccumulator(
                id=record.id,
                ticker=record.ticker,
                position_type=record.position_type,
                source=PositionLotSource.RECONCILIATION,
                acquired_shares=record.target_shares,
                remaining_shares=record.target_shares,
                cost_basis=record.target_cost_basis,
                average_cost=record.target_average_cost,
                entry_price=None,
                purchased_at=None,
            )
            continue

        if isinstance(record, LotClassificationChange):
            lot = lots.get(record.lot_id)
            if lot is None:
                raise InvalidLedger("Lot Classification Change 引用了不存在的 Lot")
            lot.position_type = record.position_type
            continue

        transaction = record

        if transaction.action is TransactionAction.BUY:
            cash_required = transaction.amount + transaction.commission
            if cash_required > available_cash:
                raise InsufficientCash(available=available_cash, required=cash_required)
            available_cash -= cash_required
            if transaction.id in lots:
                raise InvalidLedger("BUY Transaction ID 与已有 Lot 重复")
            lots[transaction.id] = _LotAccumulator(
                id=transaction.id,
                ticker=transaction.ticker,
                position_type=transaction.position_type,
                source=PositionLotSource.BUY,
                acquired_shares=transaction.shares,
                remaining_shares=transaction.shares,
                cost_basis=cash_required,
                average_cost=(cash_required / transaction.shares).quantize(
                    DECIMAL_QUANTUM,
                    rounding=ROUND_HALF_EVEN,
                ),
                entry_price=transaction.price,
                purchased_at=transaction.occurred_at,
            )
            continue

        allocations = allocations_by_transaction.get(transaction.id, [])
        allocated_shares = sum((allocation.shares for allocation in allocations), Decimal("0"))
        if allocated_shares != transaction.shares:
            raise InvalidLedger("SELL 的 Lot Allocation 合计必须等于成交股数")
        for allocation in allocations:
            lot = lots.get(allocation.lot_id)
            if lot is None or lot.ticker != transaction.ticker:
                raise InvalidLedger("SELL 引用了不存在或 ticker 不一致的 Lot")
            if allocation.shares > lot.remaining_shares:
                raise InsufficientShares(
                    available=lot.remaining_shares,
                    required=allocation.shares,
                )
            if allocation.shares == lot.remaining_shares:
                del lots[lot.id]
                continue
            remaining_shares = lot.remaining_shares - allocation.shares
            lot.cost_basis = calculate_amount(lot.average_cost, remaining_shares)
            lot.remaining_shares = remaining_shares
        available_cash += transaction.amount - transaction.commission

    derived_lots = tuple(
        PositionLot(
            id=lot.id,
            ticker=lot.ticker,
            position_type=lot.position_type,
            source=lot.source,
            acquired_shares=lot.acquired_shares,
            remaining_shares=lot.remaining_shares.quantize(
                DECIMAL_QUANTUM,
                rounding=ROUND_HALF_EVEN,
            ),
            cost_basis=lot.cost_basis.quantize(
                DECIMAL_QUANTUM,
                rounding=ROUND_HALF_EVEN,
            ),
            average_cost=lot.average_cost,
            entry_price=lot.entry_price,
            purchased_at=lot.purchased_at,
        )
        for lot in sorted(
            lots.values(),
            key=lambda item: (
                item.ticker,
                item.position_type.value,
                item.purchased_at is None,
                item.purchased_at or user.created_at,
                item.id.hex,
            ),
        )
    )

    positions: dict[tuple[str, PositionType], _PositionAccumulator] = {}
    for derived_lot in derived_lots:
        position_key = (derived_lot.ticker, derived_lot.position_type)
        position_accumulator = positions.get(position_key)
        if position_accumulator is None:
            position_accumulator = _PositionAccumulator(
                shares=Decimal("0"),
                cost_basis=Decimal("0"),
                reconciled_average_cost=(
                    derived_lot.average_cost
                    if derived_lot.source is PositionLotSource.RECONCILIATION
                    else None
                ),
            )
            positions[position_key] = position_accumulator
        else:
            position_accumulator.reconciled_average_cost = None
        position_accumulator.shares += derived_lot.remaining_shares
        position_accumulator.cost_basis += derived_lot.cost_basis

    derived_positions = tuple(
        Position(
            ticker=ticker,
            position_type=position_type,
            shares=accumulator.shares.quantize(DECIMAL_QUANTUM, rounding=ROUND_HALF_EVEN),
            cost_basis=accumulator.cost_basis.quantize(
                DECIMAL_QUANTUM,
                rounding=ROUND_HALF_EVEN,
            ),
            average_cost=(
                accumulator.reconciled_average_cost
                if accumulator.reconciled_average_cost is not None
                else (accumulator.cost_basis / accumulator.shares).quantize(
                    DECIMAL_QUANTUM,
                    rounding=ROUND_HALF_EVEN,
                )
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
            total_deposits=total_deposits.quantize(
                DECIMAL_QUANTUM,
                rounding=ROUND_HALF_EVEN,
            ),
            total_withdrawals=total_withdrawals.quantize(
                DECIMAL_QUANTUM,
                rounding=ROUND_HALF_EVEN,
            ),
        ),
        positions=derived_positions,
        lots=derived_lots,
        transaction_count=len(original_transactions),
        cash_event_count=len(ordered_cash_events),
        reconciliation_count=len(ordered_reconciliations),
    )
