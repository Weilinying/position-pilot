"""Portfolio 的同步 SQLAlchemy Unit of Work。"""

from types import TracebackType
from typing import Self
from uuid import UUID

from sqlalchemy import Select, delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from position_pilot.application.auth_service import Account, AuthSession
from position_pilot.application.errors import EmailAlreadyRegistered
from position_pilot.domain.portfolio import (
    CashEvent,
    CashEventType,
    OpeningPosition,
    PositionType,
    Transaction,
    TransactionAction,
    User,
)
from position_pilot.infrastructure.models import (
    AccountModel,
    AuthSessionModel,
    CashEventModel,
    OpeningPositionModel,
    TransactionModel,
    UserModel,
)


def _to_account(model: AccountModel) -> Account:
    """将 ORM Account 转换为 Application Auth Entity。"""

    return Account(
        id=model.id,
        email=model.email,
        display_name=model.display_name,
        password_hash=model.password_hash,
        portfolio_user_id=model.portfolio_user_id,
        created_at=model.created_at,
    )


def _to_auth_session(model: AuthSessionModel) -> AuthSession:
    """将 ORM Session 转换为不暴露 Raw Token 的 Application Entity。"""

    return AuthSession(
        id=model.id,
        account_id=model.account_id,
        token_digest=model.token_digest,
        created_at=model.created_at,
        expires_at=model.expires_at,
    )


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


def _to_opening_position(model: OpeningPositionModel) -> OpeningPosition:
    """将 ORM Starting Fact 转换为经过领域校验的 Opening Position。"""

    return OpeningPosition(
        id=model.id,
        user_id=model.user_id,
        ticker=model.ticker,
        shares=model.shares,
        average_cost=model.average_cost,
        position_type=PositionType(model.position_type),
        recorded_at=model.recorded_at,
    )


def _to_cash_event(model: CashEventModel) -> CashEvent:
    """将 ORM Cash Event 转换为经过领域校验的 Ledger Record。"""

    return CashEvent(
        id=model.id,
        user_id=model.user_id,
        sequence=model.sequence,
        event_type=CashEventType(model.event_type),
        amount=model.amount,
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

    def get_account_by_email(
        self,
        email: str,
        *,
        for_update: bool = False,
    ) -> Account | None:
        """按规范化 Email 读取 Account。"""

        statement: Select[tuple[AccountModel]] = select(AccountModel).where(
            AccountModel.email == email
        )
        if for_update:
            statement = statement.with_for_update()
        model = self.session.scalar(statement)
        return _to_account(model) if model is not None else None

    def get_account_by_id(
        self,
        account_id: UUID,
        *,
        for_update: bool = False,
    ) -> Account | None:
        """按稳定 ID 读取 Account，Portfolio Setup 可请求行锁。"""

        statement: Select[tuple[AccountModel]] = select(AccountModel).where(
            AccountModel.id == account_id
        )
        if for_update:
            statement = statement.with_for_update()
        model = self.session.scalar(statement)
        return _to_account(model) if model is not None else None

    def add_account(self, account: Account) -> None:
        """添加不暴露 Password 明文的本地 Account。"""

        self.session.add(
            AccountModel(
                id=account.id,
                email=account.email,
                display_name=account.display_name,
                password_hash=account.password_hash,
                portfolio_user_id=account.portfolio_user_id,
                created_at=account.created_at,
            )
        )

    def set_account_portfolio(self, account_id: UUID, user_id: UUID) -> None:
        """把 Account 原子绑定到唯一现有 Portfolio User。"""

        self.session.execute(
            update(AccountModel)
            .where(AccountModel.id == account_id, AccountModel.portfolio_user_id.is_(None))
            .values(portfolio_user_id=user_id)
        )

    def get_auth_session(self, token_digest: str) -> AuthSession | None:
        """按不可逆 Token Digest 读取 Session。"""

        model = self.session.scalar(
            select(AuthSessionModel).where(AuthSessionModel.token_digest == token_digest)
        )
        return _to_auth_session(model) if model is not None else None

    def add_auth_session(self, auth_session: AuthSession) -> None:
        """保存不包含 Raw Cookie Token 的 Session。"""

        self.session.add(
            AuthSessionModel(
                id=auth_session.id,
                account_id=auth_session.account_id,
                token_digest=auth_session.token_digest,
                created_at=auth_session.created_at,
                expires_at=auth_session.expires_at,
            )
        )

    def delete_auth_session(self, token_digest: str) -> None:
        """幂等撤销指定 Session。"""

        self.session.execute(
            delete(AuthSessionModel).where(AuthSessionModel.token_digest == token_digest)
        )

    def list_opening_positions(self, user_id: UUID) -> list[OpeningPosition]:
        """按稳定 Position Key 读取完整 Opening State。"""

        statement = (
            select(OpeningPositionModel)
            .where(OpeningPositionModel.user_id == user_id)
            .order_by(OpeningPositionModel.ticker, OpeningPositionModel.position_type)
        )
        return [_to_opening_position(model) for model in self.session.scalars(statement)]

    def add_opening_positions(self, opening_positions: list[OpeningPosition]) -> None:
        """在同一事务中添加完整的 immutable Opening State。"""

        self.session.add_all(
            [
                OpeningPositionModel(
                    id=position.id,
                    user_id=position.user_id,
                    ticker=position.ticker,
                    shares=position.shares,
                    average_cost=position.average_cost,
                    position_type=position.position_type.value,
                    recorded_at=position.recorded_at,
                )
                for position in opening_positions
            ]
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

    def list_cash_events(self, user_id: UUID) -> list[CashEvent]:
        """按稳定 sequence 读取 User 的完整 Cash Event Ledger。"""

        statement = (
            select(CashEventModel)
            .where(CashEventModel.user_id == user_id)
            .order_by(CashEventModel.sequence)
        )
        return [_to_cash_event(model) for model in self.session.scalars(statement)]

    def add_cash_event(self, cash_event: CashEvent) -> None:
        """追加领域层已校验的不可变 Cash Event。"""

        self.session.add(
            CashEventModel(
                id=cash_event.id,
                user_id=cash_event.user_id,
                sequence=cash_event.sequence,
                event_type=cash_event.event_type.value,
                amount=cash_event.amount,
                occurred_at=cash_event.occurred_at,
                reason=cash_event.reason,
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

    def synchronize_cash_event_sequences(self, cash_events: list[CashEvent]) -> None:
        """两阶段更新 Cash Event sequence，避免历史补录触发唯一约束。"""

        if not cash_events:
            return
        temporary_offset = len(cash_events) + max(event.sequence for event in cash_events)
        for cash_event in cash_events:
            self.session.execute(
                update(CashEventModel)
                .where(CashEventModel.id == cash_event.id)
                .values(sequence=cash_event.sequence + temporary_offset)
            )
        self.session.flush()
        for cash_event in cash_events:
            self.session.execute(
                update(CashEventModel)
                .where(CashEventModel.id == cash_event.id)
                .values(sequence=cash_event.sequence)
            )
        self.session.flush()

    def commit(self) -> None:
        """提交当前数据库事务。"""

        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            if "uq_accounts_email" in str(error.orig):
                raise EmailAlreadyRegistered() from error
            raise


class SqlAlchemyPortfolioUnitOfWorkFactory:
    """为每次 Application 操作创建独立 Unit of Work。"""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> SqlAlchemyPortfolioUnitOfWork:
        return SqlAlchemyPortfolioUnitOfWork(self._session_factory)
