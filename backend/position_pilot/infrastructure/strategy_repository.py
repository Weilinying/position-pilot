"""共享短事务的 SQLAlchemy Strategy Repository，不拥有提交权限。"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from position_pilot.application.strategy_service import StrategyError
from position_pilot.domain.strategy import (
    CandidateStatus,
    StrategyCandidate,
    StrategyKind,
    StrategyScope,
    StrategyVersion,
)
from position_pilot.infrastructure.conversation_models import (
    ConversationMessageModel,
    ConversationThreadModel,
    ConversationTurnModel,
)
from position_pilot.infrastructure.strategy_models import (
    StrategyCandidateModel,
    StrategyIdentityModel,
    StrategyVersionModel,
)


class SqlAlchemyStrategyRepository:
    """按稳定 scope identity 锁序列化；不同 scope 可以并发。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def lock_thread(self, account_id: UUID, thread_id: UUID) -> None:
        row = self.session.scalar(
            select(ConversationThreadModel)
            .where(
                ConversationThreadModel.id == thread_id,
                ConversationThreadModel.account_id == account_id,
                ConversationThreadModel.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if row is None:
            raise StrategyError("STRATEGY_NOT_FOUND", "来源会话不存在或不可访问")

    def source_content(
        self, account_id: UUID, thread_id: UUID, user_id: UUID, assistant_id: UUID
    ) -> str:
        self.session.flush()
        rows = tuple(
            self.session.scalars(
                select(ConversationMessageModel).where(
                    ConversationMessageModel.id.in_((user_id, assistant_id)),
                    ConversationMessageModel.account_id == account_id,
                    ConversationMessageModel.thread_id == thread_id,
                )
            )
        )
        user = next((r for r in rows if r.id == user_id and r.role == "USER"), None)
        assistant = next((r for r in rows if r.id == assistant_id and r.role == "ASSISTANT"), None)
        if user is None or assistant is None or user.turn_id != assistant.turn_id:
            raise StrategyError(
                "STRATEGY_INVALID", "草案必须绑定本轮同 Owner 的 User 与成功 Assistant"
            )
        completed = self.session.scalar(
            select(ConversationTurnModel.id).where(
                ConversationTurnModel.id == user.turn_id,
                ConversationTurnModel.account_id == account_id,
                ConversationTurnModel.status == "COMPLETED",
            )
        )
        if completed is None:
            raise StrategyError("STRATEGY_INVALID", "草案只能来源于成功完成的 Turn")
        return user.content

    def lock_identity(self, account_id: UUID, scope: StrategyScope, kind: StrategyKind) -> UUID:
        statement = (
            select(StrategyIdentityModel)
            .where(
                StrategyIdentityModel.account_id == account_id,
                StrategyIdentityModel.scope_key == scope.key,
                StrategyIdentityModel.kind == kind.value,
            )
            .with_for_update()
        )
        row = self.session.scalar(statement)
        if row is None:
            try:
                # 唯一冲突等待同 scope 创建提交；Savepoint 不回滚外层 Conversation。
                with self.session.begin_nested():
                    self.session.add(
                        StrategyIdentityModel(
                            id=uuid4(),
                            account_id=account_id,
                            scope_key=scope.key,
                            ticker=scope.ticker,
                            position_type=scope.position_type.value,
                            kind=kind.value,
                        )
                    )
                    self.session.flush()
            except IntegrityError as error:
                constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
                sqlite_unique = (
                    "UNIQUE constraint failed: strategy_identities.account_id, "
                    "strategy_identities.scope_key, strategy_identities.kind"
                )
                if constraint != "uq_strategy_identity_scope" and sqlite_unique not in str(
                    error.orig
                ):
                    raise
            row = self.session.scalar(statement)
        if row is None:
            raise StrategyError("STRATEGY_CONFLICT", "无法取得意图 scope")
        return row.id

    def latest(self, strategy_id: UUID) -> StrategyVersion | None:
        row = self.session.scalar(
            select(StrategyVersionModel)
            .where(StrategyVersionModel.strategy_id == strategy_id)
            .order_by(StrategyVersionModel.version.desc())
            .limit(1)
        )
        return StrategyVersion.model_validate(row.record) if row else None

    def pending(self, strategy_id: UUID) -> StrategyCandidate | None:
        row = self.session.scalar(
            select(StrategyCandidateModel).where(
                StrategyCandidateModel.strategy_id == strategy_id,
                StrategyCandidateModel.status == "PENDING",
            )
        )
        return StrategyCandidate.model_validate(row.record) if row else None

    def get_candidate(self, account_id: UUID, candidate_id: UUID) -> StrategyCandidate | None:
        row = self.session.scalar(
            select(StrategyCandidateModel)
            .where(
                StrategyCandidateModel.id == candidate_id,
                StrategyCandidateModel.account_id == account_id,
            )
            .execution_options(populate_existing=True)
        )
        return StrategyCandidate.model_validate(row.record) if row else None

    def by_message(self, account_id: UUID, message_id: UUID) -> StrategyCandidate | None:
        row = self.session.scalar(
            select(StrategyCandidateModel).where(
                StrategyCandidateModel.account_id == account_id,
                StrategyCandidateModel.assistant_message_id == message_id,
            )
        )
        return StrategyCandidate.model_validate(row.record) if row else None

    def confirmed_request(self, account_id: UUID, request_id: UUID) -> StrategyVersion | None:
        row = self.session.scalar(
            select(StrategyVersionModel).where(
                StrategyVersionModel.account_id == account_id,
                StrategyVersionModel.confirmation_request_id == request_id,
            )
        )
        return StrategyVersion.model_validate(row.record) if row else None

    def save_candidate(self, candidate: StrategyCandidate) -> None:
        row = self.session.get(StrategyCandidateModel, candidate.id)
        if row is None:
            row = StrategyCandidateModel(id=candidate.id)
            self.session.add(row)
        row.account_id, row.thread_id, row.strategy_id = (
            candidate.account_id,
            candidate.thread_id,
            candidate.strategy_id,
        )
        row.scope_key, row.kind, row.status = (
            candidate.scope.key,
            candidate.kind.value,
            candidate.status.value,
        )
        row.source_user_message_id, row.assistant_message_id = (
            candidate.source_user_message_id,
            candidate.assistant_message_id,
        )
        row.proposal_request_id, row.expires_at = (
            candidate.proposal_request_id,
            candidate.expires_at,
        )
        row.record = candidate.model_dump(mode="json")
        self.session.flush()

    def save_version(self, version: StrategyVersion) -> None:
        row = self.session.get(StrategyVersionModel, version.id)
        if row is None:
            row = StrategyVersionModel(id=version.id)
            self.session.add(row)
        row.account_id, row.strategy_id = version.account_id, version.strategy_id
        row.scope_key, row.kind = version.scope.key, version.kind.value
        row.version, row.status = version.version, version.status.value
        row.source_candidate_id, row.confirmation_request_id = (
            version.source_candidate_id,
            version.confirmation_request_id,
        )
        row.record = version.model_dump(mode="json")
        try:
            self.session.flush()
        except IntegrityError as error:
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            sqlite_unique = (
                "UNIQUE constraint failed: confirmed_strategy_versions.account_id, "
                "confirmed_strategy_versions.confirmation_request_id"
            )
            if constraint == "uq_strategy_confirmation_request" or sqlite_unique in str(error.orig):
                raise StrategyError("STRATEGY_CONFLICT", "确认请求 ID 已用于其他意图") from error
            raise

    def list_active(self, account_id: UUID, scope: str | None) -> tuple[StrategyVersion, ...]:
        statement = select(StrategyVersionModel).where(
            StrategyVersionModel.account_id == account_id, StrategyVersionModel.status == "ACTIVE"
        )
        if scope is not None:
            statement = statement.where(StrategyVersionModel.scope_key == scope)
        rows = self.session.scalars(
            statement.order_by(StrategyVersionModel.scope_key, StrategyVersionModel.kind)
        )
        return tuple(StrategyVersion.model_validate(r.record) for r in rows)

    def list_pending(self, account_id: UUID) -> tuple[StrategyCandidate, ...]:
        rows = self.session.scalars(
            select(StrategyCandidateModel)
            .join(
                ConversationThreadModel,
                StrategyCandidateModel.thread_id == ConversationThreadModel.id,
            )
            .where(
                StrategyCandidateModel.account_id == account_id,
                StrategyCandidateModel.status == "PENDING",
                ConversationThreadModel.deleted_at.is_(None),
            )
        )
        return tuple(StrategyCandidate.model_validate(r.record) for r in rows)

    def cancel_thread(self, account_id: UUID, thread_id: UUID, now: datetime) -> None:
        rows = tuple(
            self.session.scalars(
                select(StrategyCandidateModel).where(
                    StrategyCandidateModel.account_id == account_id,
                    StrategyCandidateModel.thread_id == thread_id,
                    StrategyCandidateModel.status == "PENDING",
                )
            )
        )
        for row in rows:
            candidate = StrategyCandidate.model_validate(row.record)
            self.save_candidate(
                candidate.model_copy(
                    update={
                        "status": CandidateStatus.CANCELLED,
                        "resolved_at": now,
                        "candidate_revision": candidate.candidate_revision + 1,
                    }
                )
            )
