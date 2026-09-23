"""Conversation Schema 的离线约束测试。"""

from typing import cast

from sqlalchemy import Table, UniqueConstraint

from position_pilot.infrastructure.conversation_models import (
    ConversationMessageModel,
    ConversationThreadModel,
    ConversationTurnModel,
    MessageSourceModel,
)


def _constraint_names(model: type[object]) -> set[str]:
    """返回 Model Table 上显式命名的约束。"""

    table = cast(Table, model.__table__)  # type: ignore[attr-defined]
    return {constraint.name for constraint in table.constraints if isinstance(constraint.name, str)}


def test_conversation_models_define_account_owned_schema() -> None:
    """每个 Conversation 子表应持有 Account Owner 与必要的唯一约束。"""

    assert ConversationThreadModel.__tablename__ == "conversation_threads"
    assert ConversationTurnModel.__tablename__ == "conversation_turns"
    assert ConversationMessageModel.__tablename__ == "conversation_messages"
    assert MessageSourceModel.__tablename__ == "message_sources"

    turn_table = cast(Table, ConversationTurnModel.__table__)
    message_table = cast(Table, ConversationMessageModel.__table__)
    turn_foreign_keys = {
        tuple(column.name for column in foreign_key.columns)
        for foreign_key in turn_table.foreign_key_constraints
    }
    message_foreign_keys = {
        tuple(column.name for column in foreign_key.columns)
        for foreign_key in message_table.foreign_key_constraints
    }
    assert ("thread_id", "account_id") in turn_foreign_keys
    assert ("thread_id", "account_id") in message_foreign_keys
    assert ("turn_id", "thread_id", "account_id") in message_foreign_keys

    assert {
        "uq_conversation_threads_id_account",
    }.issubset(_constraint_names(ConversationThreadModel))
    assert {
        "uq_conversation_turns_owner",
        "uq_conversation_turns_client_request",
        "ck_conversation_turns_status",
    }.issubset(_constraint_names(ConversationTurnModel))
    assert {
        "uq_conversation_messages_thread_sequence",
        "uq_conversation_messages_turn_role",
        "ck_conversation_messages_role",
    }.issubset(_constraint_names(ConversationMessageModel))


def test_turn_running_index_is_partial_and_message_role_is_unique_per_turn() -> None:
    """并发保护必须只限制 RUNNING Turn，消息按 Turn / Role 各一条。"""

    turn_table = cast(Table, ConversationTurnModel.__table__)
    message_table = cast(Table, ConversationMessageModel.__table__)
    running_indexes = [
        index
        for index in turn_table.indexes
        if index.name == "uq_conversation_turns_running_thread"
    ]
    assert len(running_indexes) == 1
    assert running_indexes[0].unique is True
    assert str(running_indexes[0].dialect_options["postgresql"]["where"]) == ("status = 'RUNNING'")

    role_constraints = [
        constraint
        for constraint in message_table.constraints
        if isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_conversation_messages_turn_role"
    ]
    assert len(role_constraints) == 1
    assert [column.name for column in role_constraints[0].columns] == ["turn_id", "role"]
    assert "warnings" in turn_table.columns


def test_message_source_stores_metadata_without_raw_payload_column() -> None:
    """Source 表只保存可展示的 Metadata，不保存 Provider Raw Payload。"""

    source_table = cast(Table, MessageSourceModel.__table__)
    columns = set(source_table.columns.keys())
    assert {
        "source_id",
        "assistant_message_id",
        "source_type",
        "provider",
        "provider_reference",
        "url",
        "title",
        "publisher",
        "published_at",
        "event_time",
        "fetched_at",
        "content_scope",
        "status",
    }.issubset(columns)
    assert "raw_payload" not in columns
    assert "query" not in columns
