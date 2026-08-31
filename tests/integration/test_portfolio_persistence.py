"""Portfolio PostgreSQL 持久化集成测试。"""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from threading import Event
from typing import Self
from uuid import UUID

import pytest
from sqlalchemy import delete, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from position_pilot.application.errors import OpeningStateSealed
from position_pilot.application.portfolio_service import (
    CreateUserCommand,
    InitializeOpeningPositionsCommand,
    OpeningPositionInput,
    PortfolioService,
    RecordCashEventCommand,
    RecordTransactionCommand,
)
from position_pilot.database import create_database_engine, create_session_factory
from position_pilot.domain.errors import InsufficientCash
from position_pilot.domain.portfolio import (
    COMMISSION_SCHEDULE,
    CashEventType,
    PositionType,
    TransactionAction,
    User,
)
from position_pilot.infrastructure.models import (
    CashEventModel,
    OpeningPositionModel,
    TransactionModel,
    UserModel,
)
from position_pilot.infrastructure.unit_of_work import (
    SqlAlchemyPortfolioUnitOfWork,
    SqlAlchemyPortfolioUnitOfWorkFactory,
)

pytestmark = pytest.mark.integration


class BlockingCommitUnitOfWork(SqlAlchemyPortfolioUnitOfWork):
    """测试专用 UoW：持有 User 行锁直到主线程允许提交。"""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        lock_acquired: Event,
        release_commit: Event,
    ) -> None:
        super().__init__(session_factory)
        self._lock_acquired = lock_acquired
        self._release_commit = release_commit

    def get_user(self, user_id: UUID, *, for_update: bool = False) -> User | None:
        user = super().get_user(user_id, for_update=for_update)
        if for_update:
            self._lock_acquired.set()
        return user

    def commit(self) -> None:
        if not self._release_commit.wait(timeout=10):
            raise TimeoutError("测试未及时释放第一笔 Portfolio Mutation")
        super().commit()


class ObservableUnitOfWork(SqlAlchemyPortfolioUnitOfWork):
    """测试专用 UoW：在请求行锁前暴露 PostgreSQL backend PID。"""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        backend_ready: Event,
        backend_pid: list[int],
    ) -> None:
        super().__init__(session_factory)
        self._backend_ready = backend_ready
        self._backend_pid = backend_pid

    def __enter__(self) -> Self:
        super().__enter__()
        pid = self.session.scalar(text("SELECT pg_backend_pid()"))
        if not isinstance(pid, int):
            raise RuntimeError("无法读取 PostgreSQL backend PID")
        self._backend_pid.append(pid)
        self._backend_ready.set()
        return self


def get_test_database_url() -> str:
    """要求调用方显式提供可清理的 PostgreSQL 测试数据库。"""

    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("需要 TEST_DATABASE_URL 才能运行 PostgreSQL 集成测试")
    return database_url


def test_persists_and_recovers_portfolio_from_transaction_ledger() -> None:
    """新 Service 实例应从 PostgreSQL Ledger 恢复 Cash 与独立 Position。"""

    engine = create_database_engine(get_test_database_url())
    session_factory = create_session_factory(engine)
    service = PortfolioService(SqlAlchemyPortfolioUnitOfWorkFactory(session_factory))
    user = service.create_user(
        CreateUserCommand(display_name="Integration User", initial_cash=Decimal("1000"))
    )

    try:
        first = service.record_transaction(
            RecordTransactionCommand(
                user_id=user.id,
                ticker="GOOG",
                action=TransactionAction.BUY,
                price=Decimal("220.5"),
                shares=Decimal("0.45"),
                position_type=PositionType.LONG_TERM,
                reason="首次建立长期仓",
            )
        )
        service.record_transaction(
            RecordTransactionCommand(
                user_id=user.id,
                ticker="GOOG",
                action=TransactionAction.BUY,
                price=Decimal("100"),
                shares=Decimal("1"),
                position_type=PositionType.SWING,
            )
        )
        service.record_transaction(
            RecordTransactionCommand(
                user_id=user.id,
                ticker="GOOG",
                action=TransactionAction.SELL,
                price=Decimal("250"),
                shares=Decimal("0.2"),
                position_type=PositionType.LONG_TERM,
            )
        )

        recovered_service = PortfolioService(
            SqlAlchemyPortfolioUnitOfWorkFactory(create_session_factory(engine))
        )
        state = recovered_service.get_portfolio(user.id)
        transactions = recovered_service.list_transactions(user.id)

        assert first.amount == Decimal("99.22500000")
        assert first.commission == Decimal("0.99225000")
        assert state.cash.available_cash == Decimal("848.93275000")
        long_term = state.get_position("GOOG", PositionType.LONG_TERM)
        assert long_term is not None
        assert long_term.shares == Decimal("0.25000000")
        assert long_term.average_cost == Decimal("222.70500000")
        assert state.get_position("GOOG", PositionType.SWING) is not None
        assert [transaction.sequence for transaction in transactions] == [1, 2, 3]
        assert [transaction.amount for transaction in transactions] == [
            Decimal("99.22500000"),
            Decimal("100.00000000"),
            Decimal("50.00000000"),
        ]
        assert [transaction.commission for transaction in transactions] == [
            Decimal("0.99225000"),
            Decimal("0.35000000"),
            Decimal("0.50000000"),
        ]
    finally:
        with engine.begin() as connection:
            connection.execute(delete(TransactionModel).where(TransactionModel.user_id == user.id))
            connection.execute(delete(UserModel).where(UserModel.id == user.id))
        engine.dispose()


def test_persists_and_recovers_combined_cash_and_transaction_ledgers() -> None:
    """新 Service 应从两类不可变 Ledger 恢复同一 Cash 与 Position Snapshot。"""

    engine = create_database_engine(get_test_database_url())
    session_factory = create_session_factory(engine)
    service = PortfolioService(SqlAlchemyPortfolioUnitOfWorkFactory(session_factory))
    user = service.create_user(
        CreateUserCommand(display_name="Cash Event User", initial_cash=Decimal("1000"))
    )

    try:
        service.record_cash_event(
            RecordCashEventCommand(
                user_id=user.id,
                event_type=CashEventType.DEPOSIT,
                amount=Decimal("500"),
                occurred_at=datetime(2026, 8, 20, 8, 0, tzinfo=UTC),
            )
        )
        service.record_transaction(
            RecordTransactionCommand(
                user_id=user.id,
                ticker="GOOG",
                action=TransactionAction.BUY,
                price=Decimal("594.05940594"),
                shares=Decimal("0.5"),
                position_type=PositionType.LONG_TERM,
                occurred_at=datetime(2026, 8, 21, 8, 0, tzinfo=UTC),
            )
        )
        service.record_transaction(
            RecordTransactionCommand(
                user_id=user.id,
                ticker="GOOG",
                action=TransactionAction.SELL,
                price=Decimal("404.04040404"),
                shares=Decimal("0.25"),
                position_type=PositionType.LONG_TERM,
                occurred_at=datetime(2026, 8, 22, 8, 0, tzinfo=UTC),
            )
        )
        service.record_cash_event(
            RecordCashEventCommand(
                user_id=user.id,
                event_type=CashEventType.WITHDRAWAL,
                amount=Decimal("200"),
                occurred_at=datetime(2026, 8, 23, 8, 0, tzinfo=UTC),
            )
        )

        recovered_service = PortfolioService(
            SqlAlchemyPortfolioUnitOfWorkFactory(create_session_factory(engine))
        )
        state = recovered_service.get_portfolio(user.id)
        cash_events = recovered_service.list_cash_events(user.id)
        position = state.get_position("GOOG", PositionType.LONG_TERM)

        assert state.cash.initial_cash == Decimal("1000.00000000")
        assert state.cash.total_deposits == Decimal("500.00000000")
        assert state.cash.total_withdrawals == Decimal("200.00000000")
        assert state.cash.available_cash == Decimal("1100.00000000")
        assert state.transaction_count == 2
        assert state.cash_event_count == 2
        assert position is not None and position.shares == Decimal("0.25000000")
        assert [event.event_type for event in cash_events] == [
            CashEventType.DEPOSIT,
            CashEventType.WITHDRAWAL,
        ]
    finally:
        with engine.begin() as connection:
            connection.execute(delete(CashEventModel).where(CashEventModel.user_id == user.id))
            connection.execute(delete(TransactionModel).where(TransactionModel.user_id == user.id))
            connection.execute(delete(UserModel).where(UserModel.id == user.id))
        engine.dispose()


def test_persists_opening_state_and_seals_after_first_economic_mutation() -> None:
    """Opening State 应独立持久化、参与 Replay，并在经济写入后保持封闭。"""

    engine = create_database_engine(get_test_database_url())
    session_factory = create_session_factory(engine)
    application_now = datetime(2026, 8, 26, 9, 30, tzinfo=UTC)
    service = PortfolioService(
        SqlAlchemyPortfolioUnitOfWorkFactory(session_factory),
        clock=lambda: application_now,
    )
    user = service.create_user(
        CreateUserCommand(display_name="Opening State User", initial_cash=Decimal("500"))
    )

    try:
        service.initialize_opening_positions(
            InitializeOpeningPositionsCommand(
                user_id=user.id,
                positions=(
                    OpeningPositionInput(
                        ticker="GOOG",
                        shares=Decimal("2"),
                        average_cost=Decimal("100"),
                    ),
                    OpeningPositionInput(
                        ticker="GOOG",
                        shares=Decimal("1"),
                        average_cost=Decimal("120"),
                        position_type=PositionType.SWING,
                    ),
                ),
            )
        )
        service.record_transaction(
            RecordTransactionCommand(
                user_id=user.id,
                ticker="GOOG",
                action=TransactionAction.SELL,
                price=Decimal("110"),
                shares=Decimal("0.5"),
            )
        )
        service.record_cash_event(
            RecordCashEventCommand(
                user_id=user.id,
                event_type=CashEventType.DEPOSIT,
                amount=Decimal("100"),
            )
        )

        recovered_service = PortfolioService(
            SqlAlchemyPortfolioUnitOfWorkFactory(create_session_factory(engine))
        )
        opening_positions = recovered_service.list_opening_positions(user.id)
        state = recovered_service.get_portfolio(user.id)

        assert [(item.ticker, item.position_type) for item in opening_positions] == [
            ("GOOG", PositionType.SWING),
            ("GOOG", PositionType.UNSPECIFIED),
        ]
        assert all(item.recorded_at == application_now for item in opening_positions)
        # 0.5 股属于小数股，手续费按成交金额 1% 计算为 0.55。
        assert state.cash.available_cash == Decimal("654.45000000")
        unspecified = state.get_position("GOOG", PositionType.UNSPECIFIED)
        assert unspecified is not None
        assert unspecified.shares == Decimal("1.50000000")
        assert state.get_position("GOOG", PositionType.SWING) is not None
        with pytest.raises(OpeningStateSealed):
            recovered_service.initialize_opening_positions(
                InitializeOpeningPositionsCommand(
                    user_id=user.id,
                    positions=(
                        OpeningPositionInput(
                            ticker="MSFT",
                            shares=Decimal("1"),
                            average_cost=Decimal("400"),
                        ),
                    ),
                )
            )
    finally:
        with engine.begin() as connection:
            connection.execute(delete(CashEventModel).where(CashEventModel.user_id == user.id))
            connection.execute(delete(TransactionModel).where(TransactionModel.user_id == user.id))
            connection.execute(
                delete(OpeningPositionModel).where(OpeningPositionModel.user_id == user.id)
            )
            connection.execute(delete(UserModel).where(UserModel.id == user.id))
        engine.dispose()


def test_persists_application_clock_for_omitted_ledger_timestamps() -> None:
    """两类 Public Write 省略时间时应持久化同一个 Application Clock。"""

    engine = create_database_engine(get_test_database_url())
    session_factory = create_session_factory(engine)
    application_now = datetime(2026, 8, 26, 9, 30, tzinfo=UTC)
    service = PortfolioService(
        SqlAlchemyPortfolioUnitOfWorkFactory(session_factory),
        clock=lambda: application_now,
    )
    user = service.create_user(
        CreateUserCommand(display_name="Clock User", initial_cash=Decimal("100"))
    )

    try:
        cash_result = service.record_cash_event(
            RecordCashEventCommand(
                user_id=user.id,
                event_type=CashEventType.DEPOSIT,
                amount=Decimal("100"),
            )
        )
        transaction = service.record_transaction(
            RecordTransactionCommand(
                user_id=user.id,
                ticker="GOOG",
                action=TransactionAction.BUY,
                price=Decimal("10"),
                shares=Decimal("1"),
                position_type=PositionType.LONG_TERM,
            )
        )

        recovered_transaction = service.list_transactions(user.id)[0]
        recovered_cash_event = service.list_cash_events(user.id)[0]

        assert cash_result.cash_event.occurred_at == application_now
        assert transaction.occurred_at == application_now
        assert recovered_cash_event.occurred_at == application_now
        assert recovered_transaction.occurred_at == application_now
    finally:
        with engine.begin() as connection:
            connection.execute(delete(CashEventModel).where(CashEventModel.user_id == user.id))
            connection.execute(delete(TransactionModel).where(TransactionModel.user_id == user.id))
            connection.execute(delete(UserModel).where(UserModel.id == user.id))
        engine.dispose()


def test_failed_withdrawal_does_not_persist_cash_event() -> None:
    """不足现金失败后数据库不得出现无效 Cash Event。"""

    engine = create_database_engine(get_test_database_url())
    session_factory = create_session_factory(engine)
    service = PortfolioService(SqlAlchemyPortfolioUnitOfWorkFactory(session_factory))
    user = service.create_user(
        CreateUserCommand(display_name="Withdrawal User", initial_cash=Decimal("100"))
    )

    try:
        with pytest.raises(InsufficientCash):
            service.record_cash_event(
                RecordCashEventCommand(
                    user_id=user.id,
                    event_type=CashEventType.WITHDRAWAL,
                    amount=Decimal("101"),
                    occurred_at=datetime(2026, 8, 25, 8, 0, tzinfo=UTC),
                )
            )

        assert service.list_cash_events(user.id) == ()
    finally:
        with engine.begin() as connection:
            connection.execute(delete(CashEventModel).where(CashEventModel.user_id == user.id))
            connection.execute(delete(UserModel).where(UserModel.id == user.id))
        engine.dispose()


@pytest.mark.parametrize(
    ("event_type", "amount"),
    [("DIVIDEND", Decimal("1")), (CashEventType.DEPOSIT.value, Decimal("0"))],
)
def test_database_rejects_invalid_cash_event_fields(
    event_type: str,
    amount: Decimal,
) -> None:
    """绕过 Application 时，数据库仍应拒绝未来类型与非正金额。"""

    engine = create_database_engine(get_test_database_url())
    session_factory = create_session_factory(engine)
    service = PortfolioService(SqlAlchemyPortfolioUnitOfWorkFactory(session_factory))
    user = service.create_user(
        CreateUserCommand(display_name="Cash Constraint User", initial_cash=Decimal("100"))
    )

    try:
        with session_factory() as session:
            session.add(
                CashEventModel(
                    id=user.id,
                    user_id=user.id,
                    sequence=1,
                    event_type=event_type,
                    amount=amount,
                    occurred_at=datetime(2026, 8, 25, 8, 0, tzinfo=UTC),
                    reason=None,
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        with engine.begin() as connection:
            connection.execute(delete(CashEventModel).where(CashEventModel.user_id == user.id))
            connection.execute(delete(UserModel).where(UserModel.id == user.id))
        engine.dispose()


@pytest.mark.parametrize(
    ("amount", "commission"),
    [
        (Decimal("999"), Decimal("0.35")),
        (Decimal("20"), Decimal("999")),
    ],
)
def test_database_rejects_non_derived_financial_fields(
    amount: Decimal,
    commission: Decimal,
) -> None:
    """绕过 Application 写入不一致派生金额时，数据库约束仍应拒绝。"""

    engine = create_database_engine(get_test_database_url())
    session_factory = create_session_factory(engine)
    service = PortfolioService(SqlAlchemyPortfolioUnitOfWorkFactory(session_factory))
    user = service.create_user(
        CreateUserCommand(display_name="Constraint User", initial_cash=Decimal("1000"))
    )

    try:
        with session_factory() as session:
            session.add(
                TransactionModel(
                    id=user.id,
                    user_id=user.id,
                    sequence=1,
                    ticker="GOOG",
                    action=TransactionAction.BUY.value,
                    price=Decimal("10"),
                    shares=Decimal("2"),
                    amount=amount,
                    commission=commission,
                    fee_schedule=COMMISSION_SCHEDULE,
                    position_type=PositionType.LONG_TERM.value,
                    occurred_at=user.created_at,
                    reason=None,
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        with engine.begin() as connection:
            connection.execute(delete(TransactionModel).where(TransactionModel.user_id == user.id))
            connection.execute(delete(UserModel).where(UserModel.id == user.id))
        engine.dispose()


def test_database_accepts_domain_bankers_rounding_at_midpoint() -> None:
    """数据库约束必须接受领域层在 midpoint 产生的银行家舍入结果。"""

    engine = create_database_engine(get_test_database_url())
    session_factory = create_session_factory(engine)
    service = PortfolioService(SqlAlchemyPortfolioUnitOfWorkFactory(session_factory))
    user = service.create_user(
        CreateUserCommand(display_name="Rounding User", initial_cash=Decimal("1000"))
    )

    try:
        transaction = service.record_transaction(
            RecordTransactionCommand(
                user_id=user.id,
                ticker="GOOG",
                action=TransactionAction.BUY,
                price=Decimal("1.00000001"),
                shares=Decimal("0.5"),
                position_type=PositionType.LONG_TERM,
            )
        )

        assert transaction.amount == Decimal("0.50000000")
        assert transaction.commission == Decimal("0.01000000")
        assert service.list_transactions(user.id)[0].amount == Decimal("0.50000000")
    finally:
        with engine.begin() as connection:
            connection.execute(delete(TransactionModel).where(TransactionModel.user_id == user.id))
            connection.execute(delete(UserModel).where(UserModel.id == user.id))
        engine.dispose()


def test_backdated_transaction_persists_economic_sequence() -> None:
    """历史补录后，数据库应保存按 occurred_at 重新派生的连续顺序。"""

    engine = create_database_engine(get_test_database_url())
    session_factory = create_session_factory(engine)
    service = PortfolioService(SqlAlchemyPortfolioUnitOfWorkFactory(session_factory))
    user = service.create_user(
        CreateUserCommand(display_name="Sequence User", initial_cash=Decimal("1000"))
    )

    try:
        later = service.record_transaction(
            RecordTransactionCommand(
                user_id=user.id,
                ticker="GOOG",
                action=TransactionAction.BUY,
                price=Decimal("10"),
                shares=Decimal("1"),
                position_type=PositionType.LONG_TERM,
                occurred_at=datetime(2026, 8, 21, 12, 0, tzinfo=UTC),
            )
        )
        earlier = service.record_transaction(
            RecordTransactionCommand(
                user_id=user.id,
                ticker="GOOG",
                action=TransactionAction.BUY,
                price=Decimal("20"),
                shares=Decimal("1"),
                position_type=PositionType.LONG_TERM,
                occurred_at=datetime(2026, 8, 20, 12, 0, tzinfo=UTC),
            )
        )

        recovered = service.list_transactions(user.id)

        assert earlier.sequence == 1
        assert [(transaction.id, transaction.sequence) for transaction in recovered] == [
            (earlier.id, 1),
            (later.id, 2),
        ]
    finally:
        with engine.begin() as connection:
            connection.execute(delete(TransactionModel).where(TransactionModel.user_id == user.id))
            connection.execute(delete(UserModel).where(UserModel.id == user.id))
        engine.dispose()


def test_concurrent_buys_wait_for_lock_and_revalidate_cash() -> None:
    """第二笔并发 BUY 必须等待第一笔提交，并基于最新 Cash 明确失败。"""

    engine = create_database_engine(get_test_database_url())
    session_factory = create_session_factory(engine)
    setup_service = PortfolioService(SqlAlchemyPortfolioUnitOfWorkFactory(session_factory))
    user = setup_service.create_user(
        CreateUserCommand(display_name="Concurrent User", initial_cash=Decimal("100"))
    )
    lock_acquired = Event()
    release_commit = Event()
    backend_ready = Event()
    backend_pid: list[int] = []
    command = RecordTransactionCommand(
        user_id=user.id,
        ticker="GOOG",
        action=TransactionAction.BUY,
        price=Decimal("79"),
        shares=Decimal("1"),
        position_type=PositionType.LONG_TERM,
    )
    first_service = PortfolioService(
        lambda: BlockingCommitUnitOfWork(
            session_factory,
            lock_acquired=lock_acquired,
            release_commit=release_commit,
        )
    )
    second_service = PortfolioService(
        lambda: ObservableUnitOfWork(
            session_factory,
            backend_ready=backend_ready,
            backend_pid=backend_pid,
        )
    )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first_future = executor.submit(first_service.record_transaction, command)
            assert lock_acquired.wait(timeout=5), "第一笔 Transaction 未获取 User 行锁"
            second_future = executor.submit(second_service.record_transaction, command)
            try:
                assert backend_ready.wait(timeout=5), "第二笔 Transaction 未建立数据库连接"
                deadline = time.monotonic() + 5
                waiting_for_lock = False
                while time.monotonic() < deadline:
                    with engine.connect() as connection:
                        wait_event_type = connection.scalar(
                            text(
                                "SELECT wait_event_type FROM pg_stat_activity "
                                "WHERE pid = :backend_pid"
                            ),
                            {"backend_pid": backend_pid[0]},
                        )
                    if wait_event_type == "Lock":
                        waiting_for_lock = True
                        break
                    time.sleep(0.05)
                assert waiting_for_lock, "第二笔 Transaction 未在 PostgreSQL User 行锁上等待"
            finally:
                release_commit.set()

            first = first_future.result(timeout=5)
            with pytest.raises(InsufficientCash) as error:
                second_future.result(timeout=5)

        assert first.amount == Decimal("79.00000000")
        assert error.value.available == Decimal("20.65000000")
        assert error.value.required == Decimal("79.35000000")
        assert len(setup_service.list_transactions(user.id)) == 1
    finally:
        release_commit.set()
        with engine.begin() as connection:
            connection.execute(delete(TransactionModel).where(TransactionModel.user_id == user.id))
            connection.execute(delete(UserModel).where(UserModel.id == user.id))
        engine.dispose()


def test_concurrent_opening_state_initialization_allows_only_first_writer() -> None:
    """并发 Opening State 必须由 User 行锁串行化，第二个写入明确封闭。"""

    engine = create_database_engine(get_test_database_url())
    session_factory = create_session_factory(engine)
    setup_service = PortfolioService(SqlAlchemyPortfolioUnitOfWorkFactory(session_factory))
    user = setup_service.create_user(
        CreateUserCommand(display_name="Concurrent Opening", initial_cash=Decimal("0"))
    )
    lock_acquired = Event()
    release_commit = Event()
    backend_ready = Event()
    backend_pid: list[int] = []
    command = InitializeOpeningPositionsCommand(
        user_id=user.id,
        positions=(
            OpeningPositionInput(
                ticker="GOOG",
                shares=Decimal("1"),
                average_cost=Decimal("100"),
            ),
        ),
    )
    first_service = PortfolioService(
        lambda: BlockingCommitUnitOfWork(
            session_factory,
            lock_acquired=lock_acquired,
            release_commit=release_commit,
        )
    )
    second_service = PortfolioService(
        lambda: ObservableUnitOfWork(
            session_factory,
            backend_ready=backend_ready,
            backend_pid=backend_pid,
        )
    )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first_future = executor.submit(first_service.initialize_opening_positions, command)
            assert lock_acquired.wait(timeout=5), "第一批 Opening State 未获取 User 行锁"
            second_future = executor.submit(second_service.initialize_opening_positions, command)
            try:
                assert backend_ready.wait(timeout=5), "第二批 Opening State 未建立数据库连接"
                deadline = time.monotonic() + 5
                waiting_for_lock = False
                while time.monotonic() < deadline:
                    with engine.connect() as connection:
                        wait_event_type = connection.scalar(
                            text(
                                "SELECT wait_event_type FROM pg_stat_activity "
                                "WHERE pid = :backend_pid"
                            ),
                            {"backend_pid": backend_pid[0]},
                        )
                    if wait_event_type == "Lock":
                        waiting_for_lock = True
                        break
                    time.sleep(0.05)
                assert waiting_for_lock, "第二批 Opening State 未等待 User 行锁"
            finally:
                release_commit.set()

            first = first_future.result(timeout=5)
            with pytest.raises(OpeningStateSealed):
                second_future.result(timeout=5)

        assert len(first) == 1
        assert len(setup_service.list_opening_positions(user.id)) == 1
    finally:
        release_commit.set()
        with engine.begin() as connection:
            connection.execute(
                delete(OpeningPositionModel).where(OpeningPositionModel.user_id == user.id)
            )
            connection.execute(delete(UserModel).where(UserModel.id == user.id))
        engine.dispose()
