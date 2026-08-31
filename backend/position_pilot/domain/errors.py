"""Portfolio 领域错误。"""

from decimal import Decimal


class PortfolioError(Exception):
    """所有 Portfolio 领域错误的基类。"""


class InvalidPortfolioValue(PortfolioError, ValueError):
    """输入或持久化状态不满足领域约束。"""


class FutureTimestamp(InvalidPortfolioValue):
    """Ledger 记录时间晚于 Application Clock。"""


class InvalidLedger(PortfolioError):
    """Transaction Ledger 无法按可靠顺序重放。"""


class InsufficientCash(PortfolioError):
    """BUY 或 WITHDRAWAL 所需现金超过当前可用现金。"""

    def __init__(self, *, available: Decimal, required: Decimal) -> None:
        self.available = available
        self.required = required
        super().__init__(f"可用现金 {available} 少于所需金额 {required}")


class InsufficientShares(PortfolioError):
    """SELL 数量超过指定仓位的可用 Shares。"""

    def __init__(self, *, available: Decimal, required: Decimal) -> None:
        self.available = available
        self.required = required
        super().__init__(f"可用股数 {available} 少于卖出股数 {required}")
