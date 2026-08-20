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


def test_m1_metadata_contains_only_ledger_source_of_truth_tables() -> None:
    """M1 只能持久化 User 与 Transaction，不建立 Cash / Position 投影表。"""

    assert models.UserModel.__tablename__ == "users"
    assert models.TransactionModel.__tablename__ == "transactions"
    assert set(Base.metadata.tables) == {"users", "transactions"}
