"""4B 专用临时 SQL Fixture；生命周期操作复用真实 Application Service。"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from uuid import uuid4

from behavioral_harness import NOW, USER_ID
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from position_pilot.application.conversation_agent import ConversationInvestmentAgent
from position_pilot.application.conversation_service import (
    ConversationCompletion,
    ConversationService,
    ConversationThread,
)
from position_pilot.application.native_investment_agent import NativeInvestmentAgent
from position_pilot.application.strategy_service import StrategyService
from position_pilot.database import Base, create_session_factory
from position_pilot.domain.strategy import (
    StrategyCandidate,
    StrategyDraft,
    StrategyKind,
    StrategyOperation,
    StrategyVersion,
)
from position_pilot.infrastructure.conversation_unit_of_work import (
    SqlAlchemyConversationUnitOfWorkFactory,
    conversation_strategy_repository,
)
from position_pilot.infrastructure.models import AccountModel
from position_pilot.infrastructure.strategy_unit_of_work import SqlAlchemyStrategyUnitOfWorkFactory

FIXTURE_NOW = NOW + timedelta(minutes=30)
SCOPE = {"ticker": "GOOG", "position_type": "LONG_TERM"}


class StrategyFixture:
    """每个 Case 独立数据库与 Owner，重建 Adapter 模拟跨 Thread / Service Session。"""

    def __init__(self, agent: NativeInvestmentAgent) -> None:
        self.engine = create_engine("sqlite:///:memory:", poolclass=StaticPool)

        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection: object, record: object) -> None:
            from sqlite3 import Connection

            assert isinstance(connection, Connection)
            connection.execute("PRAGMA foreign_keys=ON")

        names = (
            "users",
            "accounts",
            "conversation_threads",
            "conversation_turns",
            "conversation_messages",
            "message_sources",
            "strategy_identities",
            "strategy_candidates",
            "confirmed_strategy_versions",
        )
        Base.metadata.create_all(self.engine, tables=[Base.metadata.tables[n] for n in names])
        self.factory = create_session_factory(self.engine)
        self.owner = uuid4()
        self.now = FIXTURE_NOW
        self.agent = agent
        self.events: list[dict[str, object]] = []
        with self.factory() as session:
            session.add(
                AccountModel(
                    id=self.owner,
                    email=f"{self.owner}@example.test",
                    display_name="4B Fixture",
                    password_hash="non-secret-fixture-hash",
                    created_at=self.now,
                )
            )
            session.commit()
        self.reconnect()

    def reconnect(self) -> None:
        """共享数据库但重新创建短事务服务，不把状态保存在模型或 Adapter。"""
        self.strategies = StrategyService(
            SqlAlchemyStrategyUnitOfWorkFactory(self.factory),
            clock=lambda: self.now,
        )
        self.conversations = ConversationService(
            SqlAlchemyConversationUnitOfWorkFactory(self.factory),
            clock=lambda: self.now,
            agent=ConversationInvestmentAgent(self.agent, self.strategies),
            strategy_repository_factory=conversation_strategy_repository,
        )

    def seed(
        self,
        kind: StrategyKind,
        payload: dict[str, object] | None,
        *,
        operation: StrategyOperation = StrategyOperation.UPSERT,
        confirm: bool = True,
    ) -> StrategyCandidate:
        """固定 User/Assistant Fixture 只用于建库前置条件，不算在线 Ask 或模型证据。"""
        thread = self.conversations.start_thread(self.owner)
        question = f"请持续记住 GOOG LONG_TERM 的 {kind.value}：{payload}，操作 {operation.value}。"
        started = self.conversations.start_turn(
            self.owner,
            thread.id,
            portfolio_user_id=USER_ID,
            question=question,
            client_request_id=uuid4(),
            expected_thread_revision=thread.revision,
        )
        draft = StrategyDraft.model_validate(
            {
                "operation": operation,
                "scope": SCOPE,
                "kind": kind,
                "payload": payload,
                "origin": "USER_STATED_INTENT",
                "evidence_quote": question,
            }
        )
        completed = self.conversations.complete_turn(
            self.owner,
            thread.id,
            started.turn.id,
            answer="固定前置草案，未确认不生效。",
            strategy_draft=draft,
        )
        assert completed.candidate is not None
        candidate = completed.candidate
        self.events.append(
            {
                "phase": "FIXTURE_SETUP",
                "action": "PROPOSE",
                "candidate": candidate.model_dump(mode="json"),
            }
        )
        if confirm:
            self.confirm(candidate, phase="FIXTURE_SETUP")
        return candidate

    def confirm(self, candidate: StrategyCandidate, *, phase: str) -> StrategyVersion:
        version = self.strategies.confirm(
            self.owner,
            candidate.id,
            candidate_revision=candidate.candidate_revision,
            base_version=candidate.base_version,
            client_request_id=uuid4(),
        )
        self.events.append(
            {
                "phase": phase,
                "action": "EXPLICIT_CONFIRM",
                "version": version.model_dump(mode="json"),
            }
        )
        return version

    def ask(self, thread: ConversationThread, question: str) -> ConversationCompletion:
        snapshot = self.conversations.get_thread(self.owner, thread.id)
        return self.conversations.ask(
            self.owner,
            thread.id,
            portfolio_user_id=USER_ID,
            question=question,
            client_request_id=uuid4(),
            expected_thread_revision=snapshot.thread.revision,
        )

    def active(self) -> list[dict[str, object]]:
        return [v.model_dump(mode="json") for v in self.strategies.active(self.owner)]


@contextmanager
def strategy_fixture(agent: NativeInvestmentAgent) -> Iterator[StrategyFixture]:
    """关闭每个 Case 的临时数据库，不访问仓库配置或正式数据库。"""
    store = StrategyFixture(agent)
    try:
        yield store
    finally:
        store.engine.dispose()
