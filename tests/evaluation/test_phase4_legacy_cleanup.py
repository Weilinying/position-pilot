"""Legacy 清理不能改变已验收 Candidate 的运行语义。"""

import json
from pathlib import Path

from phase4_strategy_freeze import candidate_profile


def test_accepted_candidate_profile_survives_legacy_cleanup() -> None:
    """由真实离线 Request 重算 Prompt、Schema、Budget 和 Fixture，核对冻结记录。"""
    repository = Path(__file__).resolve().parents[2]
    record = json.loads(
        (
            repository / "docs/evaluation/reports/2026-10-04-phase4b-candidate-v1-config.json"
        ).read_text()
    )
    assert candidate_profile() == record["profile"]
