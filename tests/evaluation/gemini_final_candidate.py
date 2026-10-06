"""Gemini Production Final Smoke 的冻结与离线 Candidate 校验。"""

from __future__ import annotations

import hashlib
import json
import subprocess
from importlib.metadata import version
from pathlib import Path
from typing import cast

from phase4_strategy_freeze import candidate_profile as strategy_candidate_profile

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_PATH = ROOT / "docs/evaluation/reports/2026-10-05-gemini-production-smoke-candidate.json"
SOURCE_PATHS = tuple(
    sorted(
        {
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "backend/position_pilot").rglob("*.py")
        }
        | {
            ".env.example",
            "pyproject.toml",
            "uv.lock",
            "tests/evaluation/ask_quality_cases.py",
            "tests/evaluation/ask_quality_phase4_manifest.py",
            "tests/evaluation/behavioral_harness.py",
            "tests/evaluation/phase4_core_harness.py",
            "tests/evaluation/phase4_strategy_freeze.py",
            "tests/evaluation/phase4_strategy_manifest.py",
            "tests/evaluation/gemini_final_candidate.py",
            "tests/evaluation/gemini_production_smoke.py",
            "tests/evaluation/test_gemini_production_smoke.py",
        }
    )
)
SMOKE_BUDGET = {
    "model_requests": 2,
    "quote_tool_attempts": 1,
    "application_final_repairs": 0,
    "framework_retries": 0,
    "provider_retries": 0,
    "wall_clock_seconds": 60.0,
}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _git_output(arguments: list[str]) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError("SOURCE_REVISION_UNAVAILABLE")
    return result.stdout.strip()


def source_commit() -> str:
    """返回用于冻结 Smoke 源文件的 HEAD commit。"""

    return _git_output(["rev-parse", "HEAD"])


def _committed_blob(commit: str, relative_path: str) -> str:
    return _git_output(["rev-parse", f"{commit}:{relative_path}"])


def _working_blob(relative_path: str) -> str:
    return _git_output(["hash-object", "--", relative_path])


def _source_records(commit: str) -> tuple[dict[str, str], dict[str, str]]:
    current_hashes: dict[str, str] = {}
    committed_blobs: dict[str, str] = {}
    for relative_path in SOURCE_PATHS:
        path = ROOT / relative_path
        if not path.is_file():
            raise ValueError("SOURCE_FILE_MISSING")
        current_hashes[relative_path] = _sha256_bytes(path.read_bytes())
        committed = _committed_blob(commit, relative_path)
        working = _working_blob(relative_path)
        if working != committed:
            raise ValueError("SOURCE_NOT_COMMITTED")
        committed_blobs[relative_path] = committed
    return dict(sorted(current_hashes.items())), dict(sorted(committed_blobs.items()))


def candidate_payload(commit: str | None = None) -> dict[str, object]:
    """建立固定预算、Runtime、版本与源文件绑定的 Candidate。"""

    frozen_commit = commit or source_commit()
    file_hashes, git_blobs = _source_records(frozen_commit)
    return {
        "candidate_id": "gemini-production-final-smoke-2026-10-05-v1",
        "status": "PREPARED_OFFLINE_AWAITING_USER_EXECUTION",
        "source_commit": frozen_commit,
        "source_git_blobs": git_blobs,
        "source_files_sha256": file_hashes,
        "production_runtime": {
            "provider": "GOOGLE_GEMINI",
            "model": "gemini-3.8-flash",
            "output_mechanism": "NATIVE",
            "pydantic_ai_slim_version": version("pydantic-ai-slim"),
            "google_genai_version": version("google-genai"),
            "pydantic_version": version("pydantic"),
        },
        "phase4b_profile": strategy_candidate_profile(),
        "smoke_profile": {
            "budget": SMOKE_BUDGET,
            "market_data": "FIXED_QUOTE_FIXTURE_NOT_LIVE_ACCEPTANCE",
            "portfolio": "FIXED_PORTFOLIO_FIXTURE",
            "search": "NOT_EXPOSED",
            "database": "UNUSED_FIXED_DSN",
        },
    }


def verify_candidate(path: Path, *, current_commit: str | None = None) -> dict[str, object]:
    """拒绝 Candidate 后的相关源码漂移，允许仅增加 Artifact 的后续提交。"""

    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("CANDIDATE_INVALID")
    record = cast(dict[str, object], value)
    commit = record.get("source_commit")
    if not isinstance(commit, str) or not commit:
        raise ValueError("CANDIDATE_SOURCE_COMMIT_INVALID")
    head = current_commit or source_commit()
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, head],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    if ancestor.returncode != 0:
        raise ValueError("CANDIDATE_SOURCE_COMMIT_NOT_ANCESTOR")
    expected_hashes, expected_blobs = _source_records(commit)
    if record.get("source_files_sha256") != expected_hashes:
        raise ValueError("CANDIDATE_SOURCE_FILE_DRIFT")
    if record.get("source_git_blobs") != expected_blobs:
        raise ValueError("CANDIDATE_GIT_BLOB_DRIFT")
    expected = candidate_payload(commit)
    if record != expected:
        raise ValueError("CANDIDATE_PROFILE_DRIFT")
    return record
