"""数据库基础设施与 M1 元数据测试。"""

from position_pilot.database import Base, create_database_engine
from position_pilot.infrastructure import models


def test_create_database_engine_uses_psycopg_postgresql_dialect() -> None:
    """引擎应使用已批准的同步 PostgreSQL psycopg 方言，且不建立网络连接。"""

    engine = create_database_engine(
        "postgresql+psycopg://position_pilot:secret@localhost:5432/position_pilot"
    )

    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "psycopg"
    engine.dispose()


def test_metadata_contains_only_portfolio_source_of_truth_tables() -> None:
    """只持久化 User、Opening State 与经济 Ledger，不建立状态投影表。"""

    assert models.UserModel.__tablename__ == "users"
    assert models.TransactionModel.__tablename__ == "transactions"
    assert models.CashEventModel.__tablename__ == "cash_events"
    assert models.OpeningPositionModel.__tablename__ == "opening_positions"
    assert set(Base.metadata.tables) == {
        "users",
        "opening_positions",
        "transactions",
        "cash_events",
    }
