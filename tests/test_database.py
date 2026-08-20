"""数据库基础设施测试。"""

from position_pilot.database import Base, create_database_engine


def test_create_database_engine_uses_psycopg_postgresql_dialect() -> None:
    """引擎应使用已批准的同步 PostgreSQL psycopg 方言，且不建立网络连接。"""

    engine = create_database_engine(
        "postgresql+psycopg://position_pilot:secret@localhost:5432/position_pilot"
    )

    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "psycopg"
    engine.dispose()


def test_m0_metadata_contains_no_business_tables() -> None:
    """M0 只能提供空的 Migration 元数据基线。"""

    assert Base.metadata.tables == {}
