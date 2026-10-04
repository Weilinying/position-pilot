"""AQ07 的 30/60 秒 Eval-only 在线诊断入口。"""

import json
import os
from pathlib import Path
from typing import cast

import pytest
from phase4_aq07_timeout_diagnostic import run_aq07_timeout_diagnostic
from phase4_core_harness import DEFAULT_MODEL, DEFAULT_PROVIDER


@pytest.mark.online
@pytest.mark.behavioral
@pytest.mark.skipif(
    os.getenv("RUN_PHASE4_AQ07_TIMEOUT_DIAGNOSTIC") != "1",
    reason="需要显式启用 AQ07 Eval-only 耗时诊断",
)
def test_aq07_timeout_diagnostic() -> None:
    """只输出阶段计时与 Case 状态；不把诊断结果计为 4A Primary。"""

    required = (
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "AQ07_DIAGNOSTIC_TIMEOUT_SECONDS",
        "AQ07_DIAGNOSTIC_ARTIFACT_DIR",
    )
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        pytest.fail(f"AQ07 诊断缺少进程环境变量: {', '.join(missing)}")
    if os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER).strip().upper() != DEFAULT_PROVIDER:
        pytest.fail(f"AQ07 诊断 Provider 必须为 {DEFAULT_PROVIDER}")
    if os.getenv("LLM_MODEL") != DEFAULT_MODEL:
        pytest.fail(f"AQ07 诊断固定模型必须为 {DEFAULT_MODEL}")
    raw_timeout = cast(str, os.getenv("AQ07_DIAGNOSTIC_TIMEOUT_SECONDS"))
    if raw_timeout not in {"30", "60"}:
        pytest.fail("AQ07 诊断只允许 30 或 60 秒")
    artifact = run_aq07_timeout_diagnostic(
        api_key=cast(str, os.getenv("LLM_API_KEY")),
        base_url=cast(str, os.getenv("LLM_BASE_URL")),
        model_name=DEFAULT_MODEL,
        timeout_seconds=int(raw_timeout),
        artifact_dir=Path(cast(str, os.getenv("AQ07_DIAGNOSTIC_ARTIFACT_DIR"))),
    )
    case = cast(dict[str, object], artifact["case"])
    print(
        json.dumps(
            {
                "timeout_seconds": artifact["timeout_seconds"],
                "execution_status": case["execution_status"],
                "events": artifact["events"],
                "artifact_dir": os.getenv("AQ07_DIAGNOSTIC_ARTIFACT_DIR"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
