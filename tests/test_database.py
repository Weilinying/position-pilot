"""数据库基础设施与 M1 元数据测试。"""

from position_pilot.database import Base, create_database_engine
from position_pilot.infrastructure import models
from position_pilot.infrastructure.conversation_models import (
    ConversationMessageModel,
    ConversationThreadModel,
    ConversationTurnModel,
    MessageSourceModel,
)


def test_create_database_engine_uses_psycopg_postgresql_dialect() -> None:
    """引擎应使用已批准的同步 PostgreSQL psycopg 方言，且不建立网络连接。"""

    engine = create_database_engine(
        "postgresql+psycopg://position_pilot:secret@localhost:5432/position_pilot"
    )

    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "psycopg"
    engine.dispose()


def test_metadata_contains_only_approved_source_of_truth_tables() -> None:
    """只持久化 Account、Session、Opening State、校准事实与经济 Ledger。"""

    assert models.UserModel.__tablename__ == "users"
    assert models.TransactionModel.__tablename__ == "transactions"
    assert models.CashEventModel.__tablename__ == "cash_events"
    assert models.OpeningPositionModel.__tablename__ == "opening_positions"
    assert models.PositionReconciliationModel.__tablename__ == "position_reconciliations"
    assert models.LotAllocationModel.__tablename__ == "lot_allocations"
    assert models.LotClassificationChangeModel.__tablename__ == "lot_classification_changes"
    assert models.BuyTransactionCorrectionModel.__tablename__ == "buy_transaction_corrections"
    assert models.AccountModel.__tablename__ == "accounts"
    assert models.AuthSessionModel.__tablename__ == "auth_sessions"
    assert ConversationThreadModel.__tablename__ == "conversation_threads"
    assert ConversationTurnModel.__tablename__ == "conversation_turns"
    assert ConversationMessageModel.__tablename__ == "conversation_messages"
    assert MessageSourceModel.__tablename__ == "message_sources"
    assert set(Base.metadata.tables) == {
        "users",
        "accounts",
        "auth_sessions",
        "conversation_threads",
        "conversation_turns",
        "conversation_messages",
        "message_sources",
        "opening_positions",
        "position_reconciliations",
        "lot_allocations",
        "lot_classification_changes",
        "buy_transaction_corrections",
        "transactions",
        "cash_events",
    }
