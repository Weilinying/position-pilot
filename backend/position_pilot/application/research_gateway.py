"""Provider-neutral Open Research Boundary。

本模块只定义 Application 使用的公开 Research Contract。
它不选择 Search Provider、不执行网页读取，也不把外部内容提升为业务事实或指令。
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Protocol
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID

from position_pilot.domain.portfolio import normalize_ticker


class ResearchStatus(StrEnum):
    """Research 的成功、空结果与失败状态。"""

    COMPLETED = "COMPLETED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    NO_RESULTS = "NO_RESULTS"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    BLOCKED = "BLOCKED"
    TIMEOUT = "TIMEOUT"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


class ResearchContentScope(StrEnum):
    """一条 Research 来源实际提供的内容范围。"""

    TITLE_SUMMARY = "TITLE_SUMMARY"
    PROVIDER_EXTRACT = "PROVIDER_EXTRACT"
    FULL_TEXT = "FULL_TEXT"


UNTRUSTED_EXTERNAL_CONTENT = "UNTRUSTED_EXTERNAL_CONTENT"
_SENSITIVE_QUERY_KEYS = frozenset(
    {"api_key", "token", "signature", "credential", "password", "secret", "access_token"}
)


@dataclass(frozen=True, slots=True)
class ResearchRequest:
    """只包含公开主体、事件和时间窗的 Research 请求。

    Portfolio shares、成本、Cash、Strategy、Account / Session ID 与 Conversation 内容
    不属于该 Contract，因此不能被 Research Gateway 发送给 Provider。
    """

    ticker: str | None
    event: str
    time_window: str
    company: str | None = None

    def __post_init__(self) -> None:
        if self.ticker is not None:
            try:
                normalized_ticker = normalize_ticker(self.ticker)
            except (AttributeError, ValueError) as error:
                raise ValueError("Research ticker 格式无效") from error
            object.__setattr__(self, "ticker", normalized_ticker)

        for field_name in ("event", "time_window"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Research {field_name} 不能为空")
            object.__setattr__(self, field_name, value.strip())

        if self.company is not None:
            if not isinstance(self.company, str) or not self.company.strip():
                raise ValueError("Research company 必须是非空字符串或 None")
            object.__setattr__(self, "company", self.company.strip())

    @property
    def query(self) -> str:
        """由公开字段构成 Provider Query。"""

        return " ".join(
            term
            for term in (self.ticker, self.company, self.event, self.time_window)
            if term is not None
        )


@dataclass(frozen=True, slots=True)
class ResearchSource:
    """Research 观察到的单一来源及其不可信正文。

    来源元数据允许 UNKNOWN（以 ``None`` 表示）。若提供 URL，必须是经过基本边界校验的
    HTTPS 地址；正文永远按外部数据处理，不包含 Tool、Mutation 或 Confirmation 权限。
    """

    source_id: UUID
    provider: str
    url: str | None = None
    title: str | None = None
    publisher: str | None = None
    provider_reference: str | None = None
    content_scope: ResearchContentScope = ResearchContentScope.TITLE_SUMMARY
    content: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, UUID):
            raise ValueError("Research source_id 必须由 Application 生成为 UUID")
        if not isinstance(self.provider, str) or not self.provider.strip():
            raise ValueError("Research provider 不能为空")
        if not isinstance(self.content_scope, ResearchContentScope):
            raise ValueError("Research content_scope 无效")
        if self.content is not None and (
            not isinstance(self.content, str) or not self.content.strip()
        ):
            raise ValueError("Research content 必须是非空字符串或 None")
        if self.url is not None:
            self._validate_url(self.url)

    @staticmethod
    def _validate_url(url: str) -> None:
        """只接受可作为公开来源身份的 HTTPS URL。"""

        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Research source URL 必须使用 HTTPS 且包含 Host")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("Research source URL 不得包含 Credential")
        if any(key.lower() in _SENSITIVE_QUERY_KEYS for key, _ in parse_qsl(parsed.query)):
            raise ValueError("Research source URL 不得包含敏感 Query 参数")

    def as_untrusted_context(self) -> Mapping[str, object]:
        """将来源映射为只读 Agent Context，并明确标记外部内容不具备指令权限。"""

        return {
            "source_id": str(self.source_id),
            "provider": self.provider,
            "url": self.url,
            "title": self.title,
            "publisher": self.publisher,
            "provider_reference": self.provider_reference,
            "content_scope": self.content_scope.value,
            "content": self.content,
            "authority": UNTRUSTED_EXTERNAL_CONTENT,
        }


@dataclass(frozen=True, slots=True)
class ResearchResult:
    """一次 Research Gateway 观察结果。

    ``NO_RESULTS`` 与 Provider Failure 永远保持不同状态；Partial Result 可以同时携带
    已观察来源和安全的 Failure Code。"""

    request: ResearchRequest
    status: ResearchStatus
    sources: tuple[ResearchSource, ...] = ()
    failure: str | None = None
    search_count: int = 0
    fetch_count: int = 0
    latency_ms: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.request, ResearchRequest):
            raise ValueError("Research request 类型无效")
        if not isinstance(self.status, ResearchStatus):
            raise ValueError("Research status 无效")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in (self.search_count, self.fetch_count)
        ):
            raise ValueError("Research Search / Fetch Count 必须是非负整数")
        if self.latency_ms is not None and (
            isinstance(self.latency_ms, bool)
            or not isinstance(self.latency_ms, (int, float))
            or not isfinite(self.latency_ms)
            or self.latency_ms < 0
        ):
            raise ValueError("Research Latency 必须是非负有限数或 None")
        if len(self.sources) != len({source.source_id for source in self.sources}):
            raise ValueError("Research source_id 不能重复")

        if self.status is ResearchStatus.COMPLETED:
            if not self.sources or self.failure is not None:
                raise ValueError("COMPLETED Research 必须包含来源且不能包含 Failure")
            return
        if self.status is ResearchStatus.PARTIAL_SUCCESS:
            if not self.sources or not self._valid_failure:
                raise ValueError("PARTIAL_SUCCESS 必须同时包含来源与 Failure")
            return
        if self.status is ResearchStatus.NO_RESULTS:
            if self.sources or self.failure is not None:
                raise ValueError("NO_RESULTS 不能包含来源或 Failure")
            return
        if self.sources:
            raise ValueError("失败 Research 不能携带未声明为 Partial 的来源")
        if not self._valid_failure:
            raise ValueError("Research Failure 必须是非空安全错误码")

    @property
    def _valid_failure(self) -> bool:
        return isinstance(self.failure, str) and bool(self.failure.strip())

    def as_untrusted_context(self) -> tuple[Mapping[str, object], ...]:
        """只返回已观察来源，并保留每条来源的外部内容边界。"""

        if self.status not in {ResearchStatus.COMPLETED, ResearchStatus.PARTIAL_SUCCESS}:
            return ()
        return tuple(source.as_untrusted_context() for source in self.sources)


class ResearchGateway(Protocol):
    """PositionPilot 持有的 Provider-neutral Research Port。"""

    def research(self, request: ResearchRequest) -> ResearchResult:
        """按公开 Research Request 返回结构化结果。"""


__all__ = [
    "ResearchContentScope",
    "ResearchGateway",
    "ResearchRequest",
    "ResearchResult",
    "ResearchSource",
    "ResearchStatus",
    "UNTRUSTED_EXTERNAL_CONTENT",
]
