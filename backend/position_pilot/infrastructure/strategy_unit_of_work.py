"""Strategy Service 的独立短事务，不在锁内等待模型。"""

from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session, sessionmaker

from position_pilot.application.strategy_service import StrategyRepository
from position_pilot.infrastructure.strategy_repository import SqlAlchemyStrategyRepository


class SqlAlchemyStrategyUnitOfWork:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def __enter__(self) -> Self:
        self._session = self._factory()
        self.repository: StrategyRepository = SqlAlchemyStrategyRepository(self._session)
        return self

    def commit(self) -> None:
        self._session.commit()

    def __exit__(
        self, typ: type[BaseException] | None, value: BaseException | None, tb: TracebackType | None
    ) -> None:
        self._session.rollback()
        self._session.close()


class SqlAlchemyStrategyUnitOfWorkFactory:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def __call__(self) -> SqlAlchemyStrategyUnitOfWork:
        return SqlAlchemyStrategyUnitOfWork(self._factory)
