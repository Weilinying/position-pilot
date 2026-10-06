"""Gemini Production Regression 的独立源码 Candidate 冻结。"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import cast

from gemini_final_candidate import CANDIDATE_PATH, verify_candidate

ROOT = Path(__file__).resolve().parents[2]
REGRESSION_CANDIDATE_PATH = (
    ROOT / "docs/evaluation/reports/2026-10-06-gemini-production-regression-candidate.json"
)
SOURCE_PATHS = (
    "tests/evaluation/gemini_production_regression.py",
    "tests/evaluation/test_gemini_production_regression.py",
    "tests/evaluation/gemini_regression_candidate.py",
    "tests/evaluation/ask_quality_cases.py",
    "tests/evaluation/ask_quality_phase4_manifest.py",
    "tests/evaluation/behavioral_harness.py",
    "tests/evaluation/phase4_core_harness.py",
    "tests/evaluation/phase4_strategy_fixture.py",
    "tests/evaluation/phase4_strategy_harness.py",
    "tests/evaluation/phase4_strategy_manifest.py",
    "tests/evaluation/phase4_strategy_freeze.py",
    "tests/evaluation/gemini_final_candidate.py",
    "tests/evaluation/gemini_production_smoke.py",
    "tests/evaluation/test_gemini_production_smoke.py",
)
CASE_IDS = ("AQ06", "AQ12", "AQ13", "AQ14", "AQ15", "AQ16", "AQ17a", "AQ17b")
EXPECTED_TURN_COUNT = 12


def stable_json(value: object) -> str:
    """生成用于 Candidate 指纹的稳定 JSON。"""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))


def candidate_sha256(candidate: object) -> str:
    """计算 Candidate 完整稳定 JSON 的 SHA-256。"""

    return hashlib.sha256(stable_json(candidate).encode()).hexdigest()


def _git(arguments: list[str]) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, capture_output=True, check=False, text=True
    )
    if result.returncode != 0:
        raise ValueError("SOURCE_REVISION_UNAVAILABLE")
    return result.stdout.strip()


def run_profile() -> dict[str, object]:
    """描述固定预算与审批边界，不把既有 Application Repair 误记为 Retry。"""

    return {
        "provider": "GOOGLE_GEMINI",
        "model": "gemini-3.8-flash",
        "output_mechanism": "NATIVE",
        "case_ids": list(CASE_IDS),
        "expected_turn_count": EXPECTED_TURN_COUNT,
        "initial_native_budget_per_turn": {
            "model_requests": 8,
            "tool_attempts": 7,
            "wall_clock_seconds": 60.0,
        },
        "existing_source_repair_per_turn": {
            "max_additional_model_requests": 1,
            "tool_attempts": 0,
            "shares_wall_clock_budget": True,
        },
        "conservative_model_request_upper_bound": 108,
        "framework_retry_count": 0,
        "provider_http_attempts": 1,
        "research": "DEFERRED",
        "earnings_diagnostic": "NOT_TESTED",
        "repeat": "NOT_RUN",
        "behavioral_status": "PENDING_HUMAN_REVIEW",
        "production_database_access": False,
        "strategy_database": "ISOLATED_SQLITE_IN_MEMORY",
    }


def _source_records(commit: str, *, require_clean: bool) -> tuple[dict[str, str], dict[str, str]]:
    if require_clean:
        changed = subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", *SOURCE_PATHS],
            cwd=ROOT,
            capture_output=True,
            check=False,
            text=True,
        )
        if changed.returncode != 0:
            raise ValueError("SOURCE_NOT_COMMITTED")
    hashes: dict[str, str] = {}
    blobs: dict[str, str] = {}
    for relative in SOURCE_PATHS:
        path = ROOT / relative
        if not path.is_file():
            raise ValueError("SOURCE_FILE_MISSING")
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        blob = _git(["rev-parse", f"{commit}:{relative}"])
        working_blob = _git(["hash-object", "--", relative])
        if blob != working_blob:
            raise ValueError("REGRESSION_WORKTREE_SOURCE_DRIFT")
        blobs[relative] = blob
    return dict(sorted(hashes.items())), dict(sorted(blobs.items()))


def candidate_payload() -> dict[str, object]:
    """创建关联既有 Smoke Candidate 的独立 Regression 冻结记录。"""

    smoke = verify_candidate(CANDIDATE_PATH)
    commit = _git(["rev-parse", "HEAD"])
    hashes, blobs = _source_records(commit, require_clean=True)
    return {
        "candidate_id": "gemini-production-regression-2026-10-06-v1",
        "status": "PREPARED_OFFLINE_AWAITING_USER_EXECUTION",
        "source_commit": commit,
        "source_files_sha256": hashes,
        "source_git_blobs": blobs,
        "parent_smoke_candidate": {
            "candidate_id": smoke["candidate_id"],
            "source_commit": smoke["source_commit"],
            "candidate_sha256": candidate_sha256(smoke),
        },
        "run_profile": run_profile(),
    }


def verify_candidate_file(path: Path = REGRESSION_CANDIDATE_PATH) -> dict[str, object]:
    """拒绝回归源码漂移，并确认其父 Smoke Candidate 仍有效。"""

    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("REGRESSION_CANDIDATE_INVALID")
    record = cast(dict[str, object], value)
    commit = record.get("source_commit")
    if not isinstance(commit, str):
        raise ValueError("REGRESSION_SOURCE_COMMIT_INVALID")
    head = _git(["rev-parse", "HEAD"])
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, head],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    if ancestor.returncode != 0:
        raise ValueError("REGRESSION_SOURCE_COMMIT_NOT_ANCESTOR")
    hashes, blobs = _source_records(commit, require_clean=False)
    if record.get("source_files_sha256") != hashes:
        raise ValueError("REGRESSION_SOURCE_FILE_DRIFT")
    if record.get("source_git_blobs") != blobs:
        raise ValueError("REGRESSION_SOURCE_BLOB_DRIFT")
    smoke = verify_candidate(CANDIDATE_PATH)
    expected = {
        "candidate_id": "gemini-production-regression-2026-10-06-v1",
        "status": "PREPARED_OFFLINE_AWAITING_USER_EXECUTION",
        "source_commit": commit,
        "source_files_sha256": hashes,
        "source_git_blobs": blobs,
        "parent_smoke_candidate": {
            "candidate_id": smoke["candidate_id"],
            "source_commit": smoke["source_commit"],
            "candidate_sha256": candidate_sha256(smoke),
        },
        "run_profile": run_profile(),
    }
    if record != expected:
        raise ValueError("REGRESSION_CANDIDATE_PROFILE_DRIFT")
    return record
