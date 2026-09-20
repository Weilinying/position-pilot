"""Provider-neutral Phase 3 Fake Harness 与 Artifact Reporter。"""

import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from .contracts import (
    ArtifactStatus,
    ComparisonArtifact,
    ResearchRequest,
    ResearchResult,
    ResearchStatus,
    RuntimeExecutionStatus,
    RuntimeInput,
    RuntimeResult,
)


class HarnessConfigurationError(ValueError):
    """Harness 配置错误，不得归因于候选架构。"""


class RuntimeCandidate(Protocol):
    """Runtime 候选的最小 Spike 接口。"""

    name: str

    def run(self, runtime_input: RuntimeInput) -> RuntimeResult: ...


class ResearchCandidate(Protocol):
    """Research 候选的最小 Spike 接口。"""

    name: str

    def research(self, request: ResearchRequest) -> ResearchResult: ...


def _candidate_name(candidate: RuntimeCandidate | ResearchCandidate) -> str:
    """在执行前识别 Harness 配置缺陷。"""

    if not isinstance(candidate.name, str) or not candidate.name.strip():
        raise HarnessConfigurationError("Candidate name 不能为空")
    return candidate.name


def _runtime_input_payload(runtime_input: RuntimeInput) -> dict[str, object]:
    """生成稳定且不包含对象身份的输入记录。"""

    return asdict(runtime_input)


def canonical_input_hash(runtime_input: RuntimeInput) -> str:
    """对等价 Application 输入生成稳定 Hash。"""

    try:
        payload = json.dumps(
            _runtime_input_payload(runtime_input),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise HarnessConfigurationError("Runtime Input 必须可规范化为 JSON") from exc
    return sha256(payload.encode("utf-8")).hexdigest()


def _source_integrity_failure(result: RuntimeResult) -> str | None:
    """来源必须来自本轮实际 Search / Fetch Trace。"""

    observed = {
        event.source_id
        for event in result.tool_trace
        if event.source_id is not None and event.status == "OK"
    }
    unobserved = sorted(
        source.source_id for source in result.sources if source.source_id not in observed
    )
    if unobserved:
        return f"UNOBSERVED_SOURCE:{','.join(unobserved)}"
    return None


def run_runtime_fixture(
    candidate: RuntimeCandidate,
    fixture: str,
    runtime_input: RuntimeInput,
    expected_status: RuntimeExecutionStatus,
) -> ComparisonArtifact:
    """执行 Runtime Fixture，并保留 Candidate Failure。"""

    if not fixture.strip():
        raise HarnessConfigurationError("Fixture name 不能为空")
    name = _candidate_name(candidate)
    candidate_input = deepcopy(runtime_input)
    input_hash = canonical_input_hash(candidate_input)
    try:
        result = candidate.run(candidate_input)
    except Exception as exc:  # noqa: BLE001 - Spike 必须把候选异常与 Harness 配置分开记录。
        return ComparisonArtifact(
            category="runtime",
            candidate=name,
            fixture=fixture,
            status=ArtifactStatus.PROTOTYPE_GAP,
            result={
                "execution_status": "CANDIDATE_EXCEPTION",
                "failure_type": type(exc).__name__,
                "input_hash": input_hash,
            },
        )
    if not isinstance(result, RuntimeResult):
        return ComparisonArtifact(
            "runtime",
            name,
            fixture,
            ArtifactStatus.PROTOTYPE_GAP,
            {"execution_status": "INVALID_CANDIDATE_RESULT", "input_hash": input_hash},
        )
    after_hash = canonical_input_hash(candidate_input)
    integrity_failure = _source_integrity_failure(result)
    status = ArtifactStatus.SUPPORTED
    gap: str | None = None
    if after_hash != input_hash:
        status = ArtifactStatus.PROTOTYPE_GAP
        gap = "CANDIDATE_MUTATED_INPUT"
    elif integrity_failure is not None:
        status = ArtifactStatus.PROTOTYPE_GAP
        gap = integrity_failure
    elif result.status is not expected_status:
        status = ArtifactStatus.PROTOTYPE_GAP
        gap = "UNEXPECTED_RUNTIME_STATUS"
    result_payload = asdict(result)
    result_payload["input_hash"] = input_hash
    result_payload["gap"] = gap
    return ComparisonArtifact(
        category="runtime",
        candidate=name,
        fixture=fixture,
        status=status,
        result=result_payload,
    )


def run_research_fixture(
    candidate: ResearchCandidate,
    fixture: str,
    request: ResearchRequest,
    expected_status: ResearchStatus,
) -> ComparisonArtifact:
    """执行 Research Fixture，不把正常空结果标成 Provider Failure。"""

    if not fixture.strip():
        raise HarnessConfigurationError("Fixture name 不能为空")
    name = _candidate_name(candidate)
    try:
        result = candidate.research(request)
    except Exception as exc:  # noqa: BLE001 - Spike 必须记录候选异常类型。
        return ComparisonArtifact(
            category="research",
            candidate=name,
            fixture=fixture,
            status=ArtifactStatus.PROTOTYPE_GAP,
            result={"research_status": "CANDIDATE_EXCEPTION", "failure_type": type(exc).__name__},
        )
    if not isinstance(result, ResearchResult):
        return ComparisonArtifact(
            "research",
            name,
            fixture,
            ArtifactStatus.PROTOTYPE_GAP,
            {"research_status": "INVALID_CANDIDATE_RESULT"},
        )
    status = (
        ArtifactStatus.SUPPORTED
        if result.status is expected_status
        else ArtifactStatus.PROTOTYPE_GAP
    )
    return ComparisonArtifact(
        category="research",
        candidate=name,
        fixture=fixture,
        status=status,
        result=asdict(result),
    )


def not_measured_artifact(
    category: str,
    candidate: str,
    fixture: str,
    reason: str,
) -> ComparisonArtifact:
    """安全能力尚未真实执行时，显式记录为未测量。"""

    if not all(value.strip() for value in (category, candidate, fixture, reason)):
        raise HarnessConfigurationError("NOT_MEASURED Artifact 字段不能为空")
    return ComparisonArtifact(
        category,
        candidate,
        fixture,
        ArtifactStatus.NOT_MEASURED,
        {"reason": reason},
    )


class ArtifactReporter:
    """只向调用方显式提供的目录写入可比较 JSON。"""

    def __init__(self, output_directory: Path) -> None:
        if not output_directory.is_absolute():
            raise HarnessConfigurationError("Artifact 目录必须是绝对路径")
        self._output_directory = output_directory

    def write(
        self,
        filename: str,
        manifest: Mapping[str, object],
        artifacts: tuple[ComparisonArtifact, ...],
    ) -> Path:
        """写入 Manifest 与 Artifact，不补写未知数据。"""

        if not filename.endswith(".json") or Path(filename).name != filename:
            raise HarnessConfigurationError("Artifact 文件名必须是单一 JSON 文件名")
        self._output_directory.mkdir(parents=True, exist_ok=True)
        path = self._output_directory / filename
        payload = {
            "manifest": dict(manifest),
            "artifacts": [asdict(artifact) for artifact in artifacts],
        }
        self._reject_sensitive_keys(payload)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path

    @classmethod
    def _reject_sensitive_keys(cls, value: object) -> None:
        """拒绝已知敏感字段与不必要的网页正文。"""

        forbidden = {
            "api_key",
            "authorization",
            "cookie",
            "credential",
            "page_content",
            "private_context",
            "raw_content",
            "secret",
        }
        if isinstance(value, Mapping):
            for key, item in value.items():
                if isinstance(key, str) and key.lower() in forbidden:
                    raise HarnessConfigurationError(f"Artifact 不得包含敏感字段: {key}")
                cls._reject_sensitive_keys(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                cls._reject_sensitive_keys(item)
