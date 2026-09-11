"""使用调用方提供脱敏截图的 qwen3-vl-flash opt-in Smoke Test。"""

import os
from pathlib import Path

import pytest

from position_pilot.application.recognition_service import RecognitionService, RecognitionStatus
from position_pilot.integrations.aliyun_vision import AliyunVisionProvider

pytestmark = [pytest.mark.integration, pytest.mark.online]

MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def get_online_input() -> tuple[RecognitionService, bytes, str]:
    """只读取显式进程环境与调用方指定文件，不把截图复制到 Repository。"""

    if os.getenv("RUN_M9_ONLINE_TESTS") != "1":
        pytest.skip("需要 RUN_M9_ONLINE_TESTS=1 才执行 M9 真实 Provider Smoke")
    api_key = os.getenv("VISION_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        pytest.skip("需要显式导出 VISION_API_KEY 或 LLM_API_KEY")
    fixture_value = os.getenv("M9_VISION_FIXTURE_PATH")
    if not fixture_value:
        pytest.skip("需要 M9_VISION_FIXTURE_PATH 指向脱敏截图")
    fixture_path = Path(fixture_value)
    if not fixture_path.is_file():
        pytest.skip("M9_VISION_FIXTURE_PATH 不存在或不是文件")
    mime_type = MIME_BY_SUFFIX.get(fixture_path.suffix.lower())
    if mime_type is None:
        pytest.skip("M9 Vision Fixture 必须是 jpeg、png 或 webp")
    provider = AliyunVisionProvider(
        api_key=api_key,
        base_url=os.getenv(
            "VISION_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        model=os.getenv("VISION_MODEL", "qwen3-vl-flash"),
    )
    return RecognitionService(provider), fixture_path.read_bytes(), mime_type


def test_qwen3_vl_returns_structured_opening_draft() -> None:
    """真实 Vision 调用只能产生可审查 Draft，缺失字段仍保持缺失。"""

    service, image_bytes, mime_type = get_online_input()
    result = service.recognize_screenshot(image_bytes, mime_type=mime_type)

    assert result.status is RecognitionStatus.OK
    assert result.draft is not None
    assert result.draft.rows
    expected_symbol = os.getenv("M9_VISION_EXPECTED_SYMBOL")
    if expected_symbol:
        symbols = {
            row.suggested_symbol.value or row.ticker.value
            for row in result.draft.rows
            if row.suggested_symbol.value or row.ticker.value
        }
        assert expected_symbol.strip().upper() in symbols
