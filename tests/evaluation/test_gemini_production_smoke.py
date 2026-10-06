"""Gemini Production Smoke 的离线 Factory、Budget、Freeze 与安全测试。"""

from __future__ import annotations

import asyncio
import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import gemini_final_candidate
import gemini_production_smoke
import httpx
import pytest
from gemini_final_candidate import candidate_payload, verify_candidate
from gemini_production_smoke import main, make_settings, run_smoke
from pydantic import PostgresDsn
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from position_pilot.integrations.pydantic_ai_runtime import (
    PydanticAIRuntime,
    create_pydantic_ai_runtime,
)


@pytest.fixture(autouse=True)
def deny_live_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """未 Mock 的网络请求必须直接失败，不能被 Runtime 当作预期 Provider Failure。"""

    async def blocked(
        transport: httpx.AsyncHTTPTransport, request: httpx.Request
    ) -> httpx.Response:
        pytest.fail("Gemini Smoke 离线测试禁止真实网络连接")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", blocked)


def _nodes(value: object) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _nodes(child)
    elif isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return
        yield from _nodes(parsed)


def _source_id(payload: dict[str, object]) -> str:
    for node in _nodes(payload):
        if (
            node.get("type") == "CURRENT_QUOTE"
            and node.get("ticker") == "GOOG"
            and node.get("status") == "OK"
            and isinstance(node.get("source_id"), str)
        ):
            return cast(str, node["source_id"])
    raise AssertionError("Tool FunctionResponse 缺少 Quote Source Metadata")


def _response(payload: dict[str, object]) -> httpx.Response:
    return httpx.Response(200, json=payload)


def test_make_settings_uses_only_explicit_gemini_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "must-not-be-used")
    settings = make_settings("fixture-gemini-key")
    assert settings.database_url == PostgresDsn(
        "postgresql+psycopg://unused:unused@localhost/unused"
    )
    assert settings.llm_provider == "GOOGLE_GEMINI"
    assert settings.llm_model == "gemini-3.8-flash"
    assert settings.llm_api_key is None
    assert settings.gemini_api_key is not None
    assert settings.gemini_api_key.get_secret_value() == "fixture-gemini-key"
    assert settings.native_llm_request_timeout_seconds == 60.0


def test_real_factory_mock_transport_runs_quote_then_native_final(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    source_id = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal source_id
        assert request.url.host == "generativelanguage.googleapis.com"
        payload = cast(dict[str, object], json.loads(request.content))
        calls.append(payload)
        assert not any(node.get("googleSearch") for node in _nodes(payload))
        if len(calls) == 1:
            tools = payload.get("tools", [])
            assert isinstance(tools, list)
            declarations = [
                declaration
                for tool in tools
                for declaration in tool.get("functionDeclarations", [])
                if declaration.get("name") == "get_current_quote"
            ]
            assert len(declarations) == 1
            parameters = declarations[0].get(
                "parameters", declarations[0].get("parameters_json_schema", {})
            )
            properties = parameters.get("properties", {})
            arguments: dict[str, object] = {"ticker": "GOOG"}
            if "request_purpose" in properties:
                arguments["request_purpose"] = "INFORMATION_RETRIEVAL"
            return _response(
                {
                    "candidates": [
                        {
                            "content": {
                                "role": "model",
                                "parts": [
                                    {
                                        "functionCall": {
                                            "name": "get_current_quote",
                                            "args": arguments,
                                            "id": "smoke-quote-1",
                                        }
                                    }
                                ],
                            },
                            "finishReason": "STOP",
                        }
                    ],
                    "usageMetadata": {"promptTokenCount": 64, "candidatesTokenCount": 8},
                }
            )

        source_id = _source_id(payload)
        contents = payload.get("contents", [])
        function_responses = [
            node.get("functionResponse") for node in _nodes(contents) if "functionResponse" in node
        ]
        assert any(
            isinstance(item, dict)
            and item.get("name") == "get_current_quote"
            and "210.25" in json.dumps(item)
            for item in function_responses
        )
        generation = cast(dict[str, object], payload["generationConfig"])
        assert generation.get("responseMimeType") == "application/json"
        schema = cast(dict[str, object], generation.get("responseJsonSchema"))
        assert "candidate" in cast(dict[str, object], schema["properties"])
        output = {
            "answer": f"GOOG 固定报价为 210.25 美元。[source:{source_id}]",
            "source_refs": [
                {"type": "PORTFOLIO_SNAPSHOT"},
                {"type": "CURRENT_QUOTE", "ticker": "GOOG"},
            ],
            "candidate": {
                "operation": "UPSERT",
                "scope": {"ticker": "GOOG", "position_type": "LONG_TERM"},
                "kind": "INVESTMENT_THESIS_V1",
                "payload": {"thesis_text": "我看好 Google 搜索与 Cloud 长期竞争力。"},
                "origin": "USER_STATED_INTENT",
                "evidence_quote": "我看好 Google 搜索与 Cloud 长期竞争力。",
                "replaces_candidate_id": None,
                "replaces_candidate_revision": None,
            },
        }
        return _response(
            {
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [{"text": json.dumps(output, ensure_ascii=False)}],
                        },
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {"promptTokenCount": 256, "candidatesTokenCount": 96},
            }
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient

    def mock_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        assert kwargs.get("trust_env") is False
        return original_client(*args, transport=transport, **kwargs)

    monkeypatch.setattr("position_pilot.integrations.gemini_runtime.httpx.AsyncClient", mock_client)
    runtime = create_pydantic_ai_runtime(make_settings("offline-key"))
    assert isinstance(runtime, PydanticAIRuntime)
    model_context_factory = runtime._model_context_factory
    assert model_context_factory is not None

    async def inspect_factory() -> None:
        async with model_context_factory() as model:
            assert isinstance(model, GoogleModel)
            assert isinstance(model._provider, GoogleProvider)

    asyncio.run(inspect_factory())
    calls.clear()
    report = run_smoke(make_settings("offline-key"))
    assert report["status"] == "PASS", json.dumps(report, ensure_ascii=False)
    assert report["behavioral_status"] == "NOT_EVALUATED"
    assert report["evidence_scope"] == "FIXTURE_ONLY_NOT_LIVE_MARKET_ACCEPTANCE"
    assert len(calls) == 2
    assert source_id
    second = calls[1]
    assert any("functionResponse" in node for node in _nodes(second))
    assert "googleSearch" not in json.dumps(calls)


def test_smoke_failure_does_not_attempt_final_repair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if request_count == 1:
            payload = cast(dict[str, Any], json.loads(request.content))
            declarations = [
                declaration
                for tool in payload.get("tools", [])
                for declaration in tool.get("functionDeclarations", [])
                if declaration.get("name") == "get_current_quote"
            ]
            parameters = declarations[0].get(
                "parameters", declarations[0].get("parameters_json_schema", {})
            )
            properties = parameters["properties"]
            arguments: dict[str, object] = {"ticker": "GOOG"}
            if "request_purpose" in properties:
                arguments["request_purpose"] = "INFORMATION_RETRIEVAL"
            part: dict[str, object] = {
                "functionCall": {
                    "name": "get_current_quote",
                    "args": arguments,
                    "id": "smoke-quote-1",
                }
            }
        else:
            part = {
                "text": json.dumps(
                    {
                        "answer": "Quote 210.25.",
                        "source_refs": [
                            {"type": "PORTFOLIO_SNAPSHOT"},
                            {"type": "CURRENT_QUOTE", "ticker": "GOOG"},
                        ],
                        "candidate": None,
                    }
                )
            }
        return _response(
            {
                "candidates": [
                    {"content": {"role": "model", "parts": [part]}, "finishReason": "STOP"}
                ]
            }
        )

    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        "position_pilot.integrations.gemini_runtime.httpx.AsyncClient",
        lambda *args, **kwargs: original_client(
            *args, transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    report = run_smoke(make_settings("offline-key"))
    assert report["status"] == "FAIL"
    assert request_count <= 2
    checks = report["checks"]
    assert isinstance(checks, dict)
    assert checks["application_final_repair_count"] == 1


def test_candidate_manifest_strictly_binds_source_and_allows_artifact_descendant(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hashes = {"backend/fixture.py": "sha256-fixture"}
    blobs = {"backend/fixture.py": "git-blob-fixture"}
    monkeypatch.setattr(gemini_final_candidate, "source_commit", lambda: "source-commit")
    monkeypatch.setattr(gemini_final_candidate, "_source_records", lambda commit: (hashes, blobs))
    monkeypatch.setattr(
        gemini_final_candidate, "strategy_candidate_profile", lambda: {"fixture": True}
    )
    monkeypatch.setattr(
        gemini_final_candidate,
        "version",
        lambda package: {
            "pydantic-ai-slim": "1.107.6",
            "google-genai": "fixture",
            "pydantic": "fixture",
        }[package],
    )
    original_run = subprocess.run
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, **kwargs: (
            type("Result", (), {"returncode": 0})()
            if args[:3] == ["git", "merge-base", "--is-ancestor"]
            else original_run(args, **kwargs)
        ),
    )
    path = tmp_path / "candidate.json"
    record = candidate_payload()
    path.write_text(json.dumps(record, ensure_ascii=False))
    assert verify_candidate(path, current_commit="artifact-only-descendant") == record
    hashes["backend/fixture.py"] = "changed"
    with pytest.raises(ValueError, match="SOURCE_FILE_DRIFT"):
        verify_candidate(path, current_commit="artifact-only-descendant")


def test_cli_preflight_and_online_double_opt_in_are_offline_and_secret_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    candidate = tmp_path / "candidate.json"
    candidate.write_text("{}")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv(gemini_production_smoke.RUN_ENV, raising=False)
    monkeypatch.setattr(
        gemini_production_smoke,
        "verify_candidate",
        lambda path: {"candidate_id": "fixture"},
    )
    monkeypatch.setattr(
        gemini_production_smoke,
        "run_smoke",
        lambda settings: pytest.fail("preflight 或未opt-in不得调用Runtime"),
    )
    assert main(["--preflight", "--candidate", str(candidate)]) == 0
    assert json.loads(capsys.readouterr().out)["online"] is False
    artifact = tmp_path / "no-opt-in-artifact"
    assert main(["--online", "--candidate", str(candidate), "--artifact-dir", str(artifact)]) == 2
    assert not artifact.exists()
    assert json.loads(capsys.readouterr().out)["failure_code"] == "ONLINE_OPT_IN_REQUIRED"


def test_online_requires_explicit_key_and_never_overwrites_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    candidate = tmp_path / "candidate.json"
    candidate.write_text("{}")
    artifact = tmp_path / "existing"
    artifact.mkdir()
    monkeypatch.setenv(gemini_production_smoke.RUN_ENV, "1")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(
        gemini_production_smoke,
        "verify_candidate",
        lambda path: {"candidate_id": "fixture"},
    )
    assert main(["--online", "--candidate", str(candidate), "--artifact-dir", str(artifact)]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["failure_code"] == "GEMINI_API_KEY_REQUIRED"
    assert artifact.is_dir()
    (artifact / "old.json").write_text("keep")
    monkeypatch.setenv("GEMINI_API_KEY", "fixture-key")
    assert main(["--online", "--candidate", str(candidate), "--artifact-dir", str(artifact)]) == 2
    assert (artifact / "old.json").read_text() == "keep"


def test_safe_error_artifact_does_not_include_provider_exception_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_before_runtime(runtime: object) -> None:
        raise RuntimeError("authorization fixture-key must-not-leak")

    monkeypatch.setattr(gemini_production_smoke, "_fixture_agent", fail_before_runtime)
    report = run_smoke(make_settings("fixture-key"))
    assert report["failure_code"] == "SMOKE_EXECUTION_EXCEPTION"
    assert report["failure_type"] == "RuntimeError"
    serialized = json.dumps(report)
    assert "fixture-key" not in serialized
    assert "authorization" not in serialized.lower()


def test_unmocked_network_is_a_test_failure() -> None:
    async def connect() -> None:
        async with httpx.AsyncClient() as client:
            await client.get("https://offline-guard.invalid")

    with pytest.raises(pytest.fail.Exception, match="禁止真实网络连接"):
        asyncio.run(connect())


def test_online_settings_validation_never_serializes_secret_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(gemini_production_smoke.RUN_ENV, "1")
    monkeypatch.setenv("GEMINI_API_KEY", "fixture-secret-key")
    monkeypatch.setenv("VISION_REQUEST_TIMEOUT_SECONDS", "bad-authorization-secret")
    monkeypatch.setattr(gemini_production_smoke, "verify_candidate", lambda path: {})
    monkeypatch.setattr(gemini_production_smoke, "run_smoke", lambda settings: pytest.fail())
    artifact_dir = tmp_path / "settings-failure"
    assert main(["--online", "--artifact-dir", str(artifact_dir)]) == 1
    report = (artifact_dir / "smoke.json").read_text()
    assert json.loads(report)["failure_code"] == "SETTINGS_VALIDATION_FAILED"
    assert "fixture-secret-key" not in report
    assert "bad-authorization-secret" not in report
    assert "secret" not in capsys.readouterr().out
