"""Phase 4 4A Core 固定 Fixture 的显式在线 pytest 入口。"""

import json
import os
from typing import cast

import pytest
from phase4_core_harness import (
    DEFAULT_PROVIDER,
    RUN_PHASE4_EVAL_ENV,
    run_phase4_evaluation,
)


@pytest.mark.online
@pytest.mark.behavioral
@pytest.mark.skipif(
    os.getenv(RUN_PHASE4_EVAL_ENV) != "1",
    reason="需要显式启用 Phase 4 真实模型 Eval",
)
def test_phase4_core_live_fixture_run() -> None:
    """记录完整 4A 证据；质量与 Critical Gate 由后续 Human Review 判定。"""

    provider = os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER).strip().upper()
    if provider not in {DEFAULT_PROVIDER, "AIHUBMIX", "GOOGLE_GEMINI"}:
        pytest.fail(f"Phase 4 Eval 不支持 Provider: {provider}")
    credentials: tuple[str, ...]
    if provider == "GOOGLE_GEMINI":
        credentials = ("GEMINI_API_KEY",)
    else:
        credentials = ("LLM_API_KEY", "LLM_BASE_URL")
    missing = [
        name
        for name in (*credentials, "LLM_MODEL", "EVAL_RUN_ID", "PHASE4_ARTIFACT_DIR")
        if not os.getenv(name)
    ]
    if missing:
        pytest.fail(f"Phase 4 在线 Eval 缺少进程环境变量: {', '.join(missing)}")
    result = run_phase4_evaluation()
    summary = cast(dict[str, object], result["summary"])
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))
