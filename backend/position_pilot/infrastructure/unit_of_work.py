"""Portfolio 的同步 SQLAlchemy Unit of Work。"""

from types import TracebackType
from typing import Self
from uuid import UUID

from sqlalchemy import Select, select, update
from sqlalchemy.orm import Session, sessionmaker

from position_pilot.domain.portfolio import PositionType, Transaction, TransactionAction, User
from position_pilot.infrastructure.models import TransactionModel, UserModel


def _to_user(model: UserModel) -> User:
    """将 ORM User 转换为无基础设施依赖的领域实体。"""

    return User(
        id=model.id,
        display_name=model.display_name,
        initial_cash=model.initial_cash,
        created_at=model.created_at,
    )


def _to_transaction(model: TransactionModel) -> Transaction:
    """将 ORM Transaction 转换为经过领域校验的 Ledger Record。"""

    return Transaction(
        id=model.id,
        user_id=model.user_id,
        sequence=model.sequence,
        ticker=model.ticker,
        action=TransactionAction(model.action),
        price=model.price,
        shares=model.shares,
        amount=model.amount,
        commission=model.commission,
        fee_schedule=model.fee_schedule,
        position_type=PositionType(model.position_type),
        occurred_at=model.occurred_at,
        reason=model.reason,
    )


class SqlAlchemyPortfolioUnitOfWork:
    """把一次 Portfolio 操作限制在单一同步数据库事务中。"""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    def __enter__(self) -> Self:
        self._session = self._session_factory()
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is not None:
            if exception_type is not None:
                self._session.rollback()
            self._session.close()
            self._session = None

    @property
    def session(self) -> Session:
        """返回当前事务 Session，禁止在上下文外使用。"""

        if self._session is None:
            raise RuntimeError("Unit of Work 必须在 with 上下文中使用")
        return self._session

    def get_user(self, user_id: UUID, *, for_update: bool = False) -> User | None:
        """读取 User；写入流程可请求数据库行锁。"""

        statement: Select[tuple[UserModel]] = select(UserModel).where(UserModel.id == user_id)
        if for_update:
            statement = statement.with_for_update()
        model = self.session.scalar(statement)
        return _to_user(model) if model is not None else None

    def add_user(self, user: User) -> None:
        """添加 User 持久化记录。"""

        self.session.add(
            UserModel(
                id=user.id,
                display_name=user.display_name,
                initial_cash=user.initial_cash,
                created_at=user.created_at,
            )
        )

    def list_transactions(self, user_id: UUID) -> list[Transaction]:
        """按稳定 sequence 读取 User 的完整 Ledger。"""

        statement = (
            select(TransactionModel)
            .where(TransactionModel.user_id == user_id)
            .order_by(TransactionModel.sequence)
        )
        return [_to_transaction(model) for model in self.session.scalars(statement)]

    def add_transaction(self, transaction: Transaction) -> None:
        """追加由领域层生成的只读金额与佣金 Ledger Record。"""

        self.session.add(
            TransactionModel(
                id=transaction.id,
                user_id=transaction.user_id,
                sequence=transaction.sequence,
                ticker=transaction.ticker,
                action=transaction.action.value,
                price=transaction.price,
                shares=transaction.shares,
                amount=transaction.amount,
                commission=transaction.commission,
                fee_schedule=transaction.fee_schedule,
                position_type=transaction.position_type.value,
                occurred_at=transaction.occurred_at,
                reason=transaction.reason,
            )
        )

    def synchronize_sequences(self, transactions: list[Transaction]) -> None:
        """两阶段更新经济 sequence，避免重新编号时触发唯一约束。"""

        if not transactions:
            return
        temporary_offset = len(transactions) + max(
            transaction.sequence for transaction in transactions
        )
        for transaction in transactions:
            self.session.execute(
                update(TransactionModel)
                .where(TransactionModel.id == transaction.id)
                .values(sequence=transaction.sequence + temporary_offset)
            )
        self.session.flush()
        for transaction in transactions:
            self.session.execute(
                update(TransactionModel)
                .where(TransactionModel.id == transaction.id)
                .values(sequence=transaction.sequence)
            )
        self.session.flush()

    def commit(self) -> None:
        """提交当前数据库事务。"""

        self.session.commit()


class SqlAlchemyPortfolioUnitOfWorkFactory:
    """为每次 Application 操作创建独立 Unit of Work。"""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> SqlAlchemyPortfolioUnitOfWork:
        return SqlAlchemyPortfolioUnitOfWork(self._session_factory)
