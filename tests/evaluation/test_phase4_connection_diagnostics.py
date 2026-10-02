"""连接失败只补充安全诊断，不改变 Runtime 重试、失败状态或 Provider 归因。"""

import asyncio
import json
import socket
import ssl
from typing import Any

import httpx
import pytest
from phase4_provider_support import (
    _exception_diagnostics,
    _GeminiRequestTraceModel,
    classify_failure,
)
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models.function import AgentInfo, FunctionModel

SECRET = "offline-secret-key-and-header"


@pytest.mark.parametrize(
    ("cause", "category"),
    (
        (socket.gaierror(socket.EAI_NONAME, SECRET), "DNS_RESOLUTION"),
        (ssl.SSLCertVerificationError(SECRET), "TLS_CERTIFICATE"),
        (ssl.SSLError(SECRET), "TLS"),
        (ConnectionRefusedError(SECRET), "CONNECTION_REFUSED"),
        (ConnectionResetError(SECRET), "CONNECTION_RESET"),
        (httpx.ConnectTimeout(SECRET), "CONNECT_TIMEOUT"),
        (RuntimeError(SECRET), "UNKNOWN"),
    ),
)
def test_request_failure_records_safe_cause_without_retry_or_secret(
    cause: Exception, category: str
) -> None:
    """经真实模型 Wrapper 传播同一个异常，Artifact 不持久化正文、URL 或 headers。"""

    request = httpx.Request(
        "GET",
        f"https://example.invalid/?key={SECRET}",
        headers={"Authorization": SECRET},
    )
    error = httpx.ConnectError(SECRET, request=request)
    error.__cause__ = cause
    count = 0

    def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal count
        count += 1
        raise error

    trace: list[dict[str, object]] = []
    model = _GeminiRequestTraceModel(FunctionModel(reply), trace)
    with pytest.raises(httpx.ConnectError) as caught:
        asyncio.run(Agent(model, retries=0).run(SECRET))

    assert caught.value is error
    assert count == 1 and len(trace) == 1
    entry: dict[str, Any] = trace[0]
    assert entry["error_type"] == "ConnectError"
    assert entry["error_cause_chain"] == [type(cause).__name__]
    assert entry["transport_error_category"] == category
    assert entry["request_index"] == 1
    assert entry["execution_phase"] == "MODEL_REQUEST"
    assert entry["provider"] == "GOOGLE_GEMINI"
    assert entry["model"] == model.wrapped.model_name
    assert entry["latency_ms"] >= 0
    assert entry["status"] == "ERROR"
    assert SECRET not in json.dumps(entry)
    assert "example.invalid" not in json.dumps(entry)
    assert "Authorization" not in json.dumps(entry)
    assert classify_failure(code="PYDANTIC_AI_RUNTIME_FAILURE") == (
        "UNCLASSIFIED",
        "PYDANTIC_AI_RUNTIME_FAILURE",
    )


def test_nested_and_implicit_causes_do_not_expose_exception_text() -> None:
    """明确 cause 优先；没有显式 cause 时保留未抑制 context 的类型。"""

    inner = socket.gaierror(socket.EAI_AGAIN, SECRET)
    middle = OSError(SECRET)
    middle.__cause__ = inner
    outer = httpx.ConnectError(SECRET)
    outer.__context__ = middle
    assert _exception_diagnostics(outer) == {
        "error_cause_chain": ["OSError", "gaierror"],
        "transport_error_category": "DNS_RESOLUTION",
    }
    outer.__suppress_context__ = True
    assert _exception_diagnostics(outer) == {
        "error_cause_chain": [],
        "transport_error_category": "UNKNOWN",
    }


def test_cancellation_is_rethrown_and_not_classified_as_connection_timeout() -> None:
    """wall-clock 取消不被 Trace 吞掉或改写为网络连接错误。"""

    cancelled = asyncio.CancelledError(SECRET)

    def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise cancelled

    trace: list[dict[str, object]] = []
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(Agent(_GeminiRequestTraceModel(FunctionModel(reply), trace)).run(SECRET))
    assert len(trace) == 1
    assert trace[0]["error_type"] == "CancelledError"
    assert trace[0]["transport_error_category"] == "UNKNOWN"
    assert SECRET not in json.dumps(trace)
