"""Phase 3 最小 Conversation / Confirmed Strategy Persistence Prototype。"""

import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from typing import Protocol

from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    insert,
    select,
)
from sqlalchemy.engine import Connection
from sqlalchemy.schema import CreateSchema

from position_pilot.application.llm import LLMMessage, LLMRole

from .contracts import RuntimeInput


class OwnershipViolation(PermissionError):
    """请求 Account 不是 Thread Owner。"""


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    """Account-owned Thread 内的有序消息。"""

    account_id: str
    thread_id: str
    sequence: int
    role: LLMRole
    content: str


@dataclass(frozen=True, slots=True)
class StrategyRecord:
    """Prototype 只保留读取所需的 Strategy 字段。"""

    strategy_id: str
    account_id: str
    scope: str
    source: str
    plan: str
    confirmed: bool


@dataclass(frozen=True, slots=True)
class StateContext:
    """注入两个 Runtime 的同一 Application-owned State。"""

    conversation: tuple[LLMMessage, ...]
    confirmed_strategy: tuple[Mapping[str, object], ...]


class StateStore(Protocol):
    """Runtime 不直接拥有 Persistence 语义。"""

    def load_context(
        self,
        *,
        account_id: str,
        thread_id: str,
        scope: str,
        message_limit: int,
    ) -> StateContext: ...


class InMemoryStateStore:
    """离线 Prototype Store；用于验证 Ownership 与 Context Boundary。"""

    def __init__(
        self,
        *,
        thread_owners: Mapping[str, str],
        messages: tuple[ConversationMessage, ...],
        strategies: tuple[StrategyRecord, ...],
    ) -> None:
        self._thread_owners = dict(thread_owners)
        self._messages = messages
        self._strategies = strategies

    def load_context(
        self,
        *,
        account_id: str,
        thread_id: str,
        scope: str,
        message_limit: int,
    ) -> StateContext:
        """按 Owner 读取有界消息，并只选择已确认 Strategy。"""

        if message_limit <= 0:
            raise ValueError("Message Limit 必须为正整数")
        owner = self._thread_owners.get(thread_id)
        if owner is None or owner != account_id:
            raise OwnershipViolation("THREAD_NOT_OWNED_BY_ACCOUNT")
        ordered = sorted(
            (
                message
                for message in self._messages
                if message.account_id == account_id and message.thread_id == thread_id
            ),
            key=lambda message: message.sequence,
        )[-message_limit:]
        strategies = tuple(
            asdict(strategy)
            for strategy in self._strategies
            if strategy.account_id == account_id and strategy.scope == scope and strategy.confirmed
        )
        return StateContext(
            tuple(LLMMessage(message.role, message.content) for message in ordered),
            strategies,
        )


def inject_state(runtime_input: RuntimeInput, context: StateContext) -> RuntimeInput:
    """通过共同 Application Boundary 替换 Runtime 的 History 与 Strategy。"""

    return replace(
        runtime_input,
        conversation=context.conversation,
        confirmed_strategy=context.confirmed_strategy,
    )


def spike_database_url(environment: Mapping[str, str]) -> str:
    """只接受显式 SPIKE_DATABASE_URL，禁止回退 Production DATABASE_URL。"""

    value = environment.get("SPIKE_DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("SPIKE_DATABASE_URL_REQUIRED")
    if not value.startswith("postgresql+psycopg://"):
        raise ValueError("SPIKE_DATABASE_URL 必须使用 postgresql+psycopg")
    return value


class PostgresSpikeStateStore:
    """临时 Schema 内的最小 PostgreSQL Prototype，不创建 Production Migration。"""

    def __init__(self, connection: Connection, *, schema: str) -> None:
        if re.fullmatch(r"phase3_[a-z0-9_]+", schema) is None:
            raise ValueError("Spike Schema 必须使用 phase3_ 前缀")
        self._connection = connection
        metadata = MetaData(schema=schema)
        self._threads = Table(
            "threads",
            metadata,
            Column("thread_id", String(64), primary_key=True),
            Column("account_id", String(64), nullable=False),
        )
        self._messages = Table(
            "messages",
            metadata,
            Column("thread_id", String(64), nullable=False),
            Column("account_id", String(64), nullable=False),
            Column("sequence", Integer, nullable=False),
            Column("role", String(16), nullable=False),
            Column("content", Text, nullable=False),
        )
        self._strategies = Table(
            "strategies",
            metadata,
            Column("strategy_id", String(64), primary_key=True),
            Column("account_id", String(64), nullable=False),
            Column("scope", String(32), nullable=False),
            Column("source", String(128), nullable=False),
            Column("plan", Text, nullable=False),
            Column("confirmed", Boolean, nullable=False),
        )
        connection.execute(CreateSchema(schema))
        metadata.create_all(connection)

    def add_thread(self, *, thread_id: str, account_id: str) -> None:
        """写入测试 Thread Owner。"""

        self._connection.execute(
            insert(self._threads).values(thread_id=thread_id, account_id=account_id)
        )

    def add_message(self, message: ConversationMessage) -> None:
        """写入测试消息。"""

        self._connection.execute(
            insert(self._messages).values(
                thread_id=message.thread_id,
                account_id=message.account_id,
                sequence=message.sequence,
                role=message.role.value,
                content=message.content,
            )
        )

    def add_strategy(self, strategy: StrategyRecord) -> None:
        """写入测试 Strategy Fixture。"""

        self._connection.execute(insert(self._strategies).values(**asdict(strategy)))

    def load_context(
        self,
        *,
        account_id: str,
        thread_id: str,
        scope: str,
        message_limit: int,
    ) -> StateContext:
        """在数据库查询前验证 Owner，并过滤未确认 Strategy。"""

        if message_limit <= 0:
            raise ValueError("Message Limit 必须为正整数")
        owner = self._connection.execute(
            select(self._threads.c.account_id).where(self._threads.c.thread_id == thread_id)
        ).scalar_one_or_none()
        if owner != account_id:
            raise OwnershipViolation("THREAD_NOT_OWNED_BY_ACCOUNT")
        rows = list(
            self._connection.execute(
                select(
                    self._messages.c.role,
                    self._messages.c.content,
                )
                .where(
                    self._messages.c.thread_id == thread_id,
                    self._messages.c.account_id == account_id,
                )
                .order_by(self._messages.c.sequence.desc())
                .limit(message_limit)
            ).all()
        )
        rows.reverse()
        strategy_rows = self._connection.execute(
            select(
                self._strategies.c.strategy_id,
                self._strategies.c.account_id,
                self._strategies.c.scope,
                self._strategies.c.source,
                self._strategies.c.plan,
                self._strategies.c.confirmed,
            ).where(
                self._strategies.c.account_id == account_id,
                self._strategies.c.scope == scope,
                self._strategies.c.confirmed.is_(True),
            )
        ).mappings()
        return StateContext(
            tuple(LLMMessage(LLMRole(row.role), row.content) for row in rows),
            tuple(dict(row) for row in strategy_rows),
        )
