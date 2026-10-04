"""持续用户意图的确定性确认与版本生命周期；不访问账本或调用模型。"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID, uuid4

from position_pilot.domain.strategy import (
    CandidateStatus,
    StrategyCandidate,
    StrategyDraft,
    StrategyKind,
    StrategyOperation,
    StrategyScope,
    StrategyVersion,
    StrategyVersionStatus,
)


class StrategyError(ValueError):
    """携带稳定 API Code 的意图边界错误。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class StrategyRepository(Protocol):
    """由外层短事务持有，支持按 scope 锁定的 Repository。"""

    def lock_thread(self, account_id: UUID, thread_id: UUID) -> None: ...
    def source_content(
        self, account_id: UUID, thread_id: UUID, user_id: UUID, assistant_id: UUID
    ) -> str: ...
    def lock_identity(self, account_id: UUID, scope: StrategyScope, kind: StrategyKind) -> UUID: ...
    def latest(self, strategy_id: UUID) -> StrategyVersion | None: ...
    def pending(self, strategy_id: UUID) -> StrategyCandidate | None: ...
    def get_candidate(self, account_id: UUID, candidate_id: UUID) -> StrategyCandidate | None: ...
    def by_message(self, account_id: UUID, message_id: UUID) -> StrategyCandidate | None: ...
    def confirmed_request(self, account_id: UUID, request_id: UUID) -> StrategyVersion | None: ...
    def save_candidate(self, candidate: StrategyCandidate) -> None: ...
    def save_version(self, version: StrategyVersion) -> None: ...
    def list_active(self, account_id: UUID, scope: str | None) -> tuple[StrategyVersion, ...]: ...
    def list_pending(self, account_id: UUID) -> tuple[StrategyCandidate, ...]: ...
    def cancel_thread(self, account_id: UUID, thread_id: UUID, now: datetime) -> None: ...


class StrategyUnitOfWork(Protocol):
    repository: StrategyRepository

    def __enter__(self) -> Self: ...
    def __exit__(
        self, typ: type[BaseException] | None, value: BaseException | None, tb: TracebackType | None
    ) -> None: ...
    def commit(self) -> None: ...


StrategyUnitOfWorkFactory = Callable[[], StrategyUnitOfWork]


class StrategyService:
    """只允许显式确认生效，ACTIVE 与 PENDING 的唯一性互相独立。"""

    def __init__(
        self, factory: StrategyUnitOfWorkFactory, *, clock: Callable[[], datetime] | None = None
    ) -> None:
        self._factory = factory
        self._clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def propose_in_repository(
        repo: StrategyRepository,
        *,
        account_id: UUID,
        thread_id: UUID,
        user_message_id: UUID,
        assistant_message_id: UUID,
        request_id: UUID,
        draft: StrategyDraft,
        now: datetime,
    ) -> StrategyCandidate:
        """与成功 Assistant Message 同事务写入草案，确认前不改变 ACTIVE。"""

        repo.lock_thread(account_id, thread_id)
        content = repo.source_content(account_id, thread_id, user_message_id, assistant_message_id)
        if not draft.evidence_quote.strip() or draft.evidence_quote not in content:
            raise StrategyError("STRATEGY_INVALID", "草案依据必须来自本轮真实 User Message")
        identity = repo.lock_identity(account_id, draft.scope, draft.kind)
        latest = repo.latest(identity)
        base = latest.version if latest else 0
        if draft.operation is StrategyOperation.INVALIDATE and (
            latest is None or latest.status is not StrategyVersionStatus.ACTIVE
        ):
            raise StrategyError("STRATEGY_CONFLICT", "没有可确认失效的 ACTIVE 意图")
        pending = repo.pending(identity)
        if pending is not None and pending.expires_at <= now:
            repo.save_candidate(
                pending.model_copy(
                    update={
                        "status": CandidateStatus.EXPIRED,
                        "resolved_at": now,
                        "candidate_revision": pending.candidate_revision + 1,
                    }
                )
            )
            pending = None
        if pending is not None:
            if (draft.replaces_candidate_id, draft.replaces_candidate_revision) != (
                pending.id,
                pending.candidate_revision,
            ):
                raise StrategyError("STRATEGY_CANDIDATE_CONFLICT", "同 scope / kind 已有待确认草案")
            repo.save_candidate(
                pending.model_copy(
                    update={
                        "status": CandidateStatus.CANCELLED,
                        "resolved_at": now,
                        "candidate_revision": pending.candidate_revision + 1,
                    }
                )
            )
        elif draft.replaces_candidate_id is not None:
            raise StrategyError("STRATEGY_CONFLICT", "要替换的草案不存在或已失效")
        candidate = StrategyCandidate(
            **draft.model_dump(),
            id=uuid4(),
            account_id=account_id,
            thread_id=thread_id,
            source_user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            strategy_id=identity,
            base_version=base,
            candidate_revision=1,
            proposal_request_id=request_id,
            status=CandidateStatus.PENDING,
            created_at=now,
            expires_at=now + timedelta(hours=24),
        )
        repo.save_candidate(candidate)
        return candidate

    def get(self, account_id: UUID, candidate_id: UUID) -> StrategyCandidate:
        """查询同 Owner 草案；到期即不可操作，不等待后台任务。"""

        with self._factory() as uow:
            candidate = self._candidate(uow.repository, account_id, candidate_id)
            uow.repository.lock_thread(account_id, candidate.thread_id)
            return self.visible(candidate, self._clock())

    def active(self, account_id: UUID, scope: str | None = None) -> tuple[StrategyVersion, ...]:
        with self._factory() as uow:
            return uow.repository.list_active(account_id, scope)

    def pending(self, account_id: UUID) -> tuple[StrategyCandidate, ...]:
        with self._factory() as uow:
            now = self._clock()
            return tuple(c for c in uow.repository.list_pending(account_id) if c.expires_at > now)

    def confirm(
        self,
        account_id: UUID,
        candidate_id: UUID,
        *,
        candidate_revision: int,
        base_version: int,
        client_request_id: UUID,
    ) -> StrategyVersion:
        """锁同一 scope，原子替代 ACTIVE；重复确认只返回相同版本。"""

        now = self._clock()
        with self._factory() as uow:
            repo = uow.repository
            candidate = self._candidate(repo, account_id, candidate_id)
            self._lock_for_resolution(repo, account_id, candidate)
            candidate = self._candidate(repo, account_id, candidate_id)
            replay = repo.confirmed_request(account_id, client_request_id)
            if replay is not None:
                if (
                    replay.source_candidate_id != candidate.id
                    or candidate_revision != candidate.candidate_revision - 1
                    or base_version != candidate.base_version
                ):
                    raise StrategyError("STRATEGY_CONFLICT", "确认请求 ID 已用于不同内容")
                return replay
            self._pending(candidate, candidate_revision, now)
            latest = repo.latest(candidate.strategy_id)
            actual = latest.version if latest else 0
            if base_version != candidate.base_version or actual != base_version:
                raise StrategyError("STRATEGY_CONFLICT", "生效版本已改变，请重新核对")
            if latest is not None and latest.status is StrategyVersionStatus.ACTIVE:
                repo.save_version(
                    latest.model_copy(
                        update={
                            "status": StrategyVersionStatus.SUPERSEDED,
                            "superseded_at": now,
                        }
                    )
                )
            invalidation = candidate.operation is StrategyOperation.INVALIDATE
            version = StrategyVersion(
                id=uuid4(),
                strategy_id=candidate.strategy_id,
                account_id=account_id,
                confirmed_by_account_id=account_id,
                scope=candidate.scope,
                kind=candidate.kind,
                payload=candidate.payload,
                version=actual + 1,
                status=StrategyVersionStatus.INVALIDATED
                if invalidation
                else StrategyVersionStatus.ACTIVE,
                previous_version_id=latest.id if latest else None,
                source_candidate_id=candidate.id,
                confirmation_request_id=client_request_id,
                confirmed_at=now,
                invalidated_at=now if invalidation else None,
            )
            repo.save_version(version)
            repo.save_candidate(
                candidate.model_copy(
                    update={
                        "status": CandidateStatus.CONFIRMED,
                        "resolved_at": now,
                        "candidate_revision": candidate.candidate_revision + 1,
                    }
                )
            )
            uow.commit()
            return version

    def cancel(
        self, account_id: UUID, candidate_id: UUID, *, candidate_revision: int
    ) -> StrategyCandidate:
        with self._factory() as uow:
            repo = uow.repository
            candidate = self._candidate(repo, account_id, candidate_id)
            self._lock_for_resolution(repo, account_id, candidate)
            candidate = self._candidate(repo, account_id, candidate_id)
            if candidate.status is CandidateStatus.CANCELLED:
                return candidate
            now = self._clock()
            self._pending(candidate, candidate_revision, now)
            cancelled = candidate.model_copy(
                update={
                    "status": CandidateStatus.CANCELLED,
                    "resolved_at": now,
                    "candidate_revision": candidate.candidate_revision + 1,
                }
            )
            repo.save_candidate(cancelled)
            uow.commit()
            return cancelled

    @staticmethod
    def _lock_for_resolution(
        repo: StrategyRepository, owner: UUID, candidate: StrategyCandidate
    ) -> None:
        # Candidate Owner 已验证；来源 Thread 删除属于确认冲突，不泄漏其他 Owner 的信息。
        try:
            repo.lock_thread(owner, candidate.thread_id)
        except StrategyError as error:
            if error.code == "STRATEGY_NOT_FOUND":
                raise StrategyError(
                    "STRATEGY_CONFLICT", "来源会话已删除，草案不能再确认"
                ) from error
            raise
        repo.lock_identity(owner, candidate.scope, candidate.kind)

    @staticmethod
    def visible(candidate: StrategyCandidate, now: datetime) -> StrategyCandidate:
        if candidate.status is CandidateStatus.PENDING and candidate.expires_at <= now:
            return candidate.model_copy(update={"status": CandidateStatus.EXPIRED})
        return candidate

    @staticmethod
    def _candidate(repo: StrategyRepository, owner: UUID, candidate_id: UUID) -> StrategyCandidate:
        candidate = repo.get_candidate(owner, candidate_id)
        if candidate is None:
            raise StrategyError("STRATEGY_NOT_FOUND", "意图草案不存在或不可访问")
        return candidate

    @staticmethod
    def _pending(candidate: StrategyCandidate, revision: int, now: datetime) -> None:
        if (
            candidate.status is not CandidateStatus.PENDING
            or candidate.expires_at <= now
            or revision != candidate.candidate_revision
        ):
            raise StrategyError("STRATEGY_CONFLICT", "草案已过期、已处理或 revision 改变")
