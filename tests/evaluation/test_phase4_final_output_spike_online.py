"""Final Output Tool 与现有 JSON 文本机制的独立在线能力入口。"""

import json
import os
from typing import cast

import pytest
from phase4_final_output_spike import run_spike


@pytest.mark.online
@pytest.mark.behavioral
@pytest.mark.skipif(
    os.getenv("RUN_PHASE4_FINAL_OUTPUT_SPIKE") != "1",
    reason="需要显式启用 Final Output Tool 在线实验",
)
def test_final_output_tool_paired_live_fixture() -> None:
    """配对记录两个候选路径；测试通过不代表 AQ07 或 4A Gate 通过。"""

    required = ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "FINAL_OUTPUT_ARTIFACT_DIR")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        pytest.fail(f"在线实验缺少进程环境变量: {', '.join(missing)}")
    if os.getenv("LLM_PROVIDER", "ALIYUN_MODEL_STUDIO").strip().upper() != "ALIYUN_MODEL_STUDIO":
        pytest.fail("固定 Provider 必须为 ALIYUN_MODEL_STUDIO")
    if os.getenv("LLM_MODEL") != "qwen3.7-max":
        pytest.fail("固定实验模型必须为 qwen3.7-max")
    report = run_spike(cast(dict[str, str], dict(os.environ)))
    arms = cast(list[dict[str, object]], report["arms"])
    summary = {
        "scenario": report["scenario"],
        "production_changed": False,
        "arms": [
            {
                key: arm[key]
                for key in (
                    "mode",
                    "first_output_valid",
                    "first_output_error",
                    "repair_triggered",
                    "final_valid",
                    "framework_output_retry_count",
                    "request_count",
                    "usage",
                    "cost",
                    "total_ms",
                )
            }
            | {
                "first_output_ms": arm.get("first_output_ms", "NOT_PRODUCED"),
                "repair_ms": arm.get("repair_ms", "NOT_TRIGGERED"),
                "model_request_latencies_ms": [
                    request["latency_ms"]
                    for request in cast(list[dict[str, object]], arm["requests"])
                ],
                "tool_names": [
                    tool["name"] for tool in cast(list[dict[str, object]], arm["tools"])
                ],
            }
            for arm in arms
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))
