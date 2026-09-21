"""两个 Framework 候选的本地只读 MCP Capability 测试。"""

import asyncio
import sys
from pathlib import Path

from agents.mcp import MCPServerStdio as AgentsMCPServerStdio
from fastmcp.client.transports import StdioTransport
from mcp.types import CallToolResult
from pydantic_ai.mcp import MCPToolset

SERVER_MODULE = "tests.spikes.ask_quality_phase3.local_readonly_mcp_server"


def test_frameworks_discover_and_call_the_same_local_readonly_mcp_tool() -> None:
    """两个官方 MCP Client 都能发现并调用同一无副作用 Tool。"""

    async def probe() -> tuple[object, CallToolResult]:
        pydantic_toolset = MCPToolset(
            StdioTransport(
                command=sys.executable,
                args=["-m", SERVER_MODULE],
                cwd=str(Path.cwd()),
            )
        )
        async with pydantic_toolset:
            pydantic_tools = await pydantic_toolset.list_tools()
            assert [tool.name for tool in pydantic_tools] == ["get_indicator_snapshot"]
            pydantic_result = await pydantic_toolset.direct_call_tool(
                "get_indicator_snapshot",
                {"ticker": "goog", "indicator": "rsi"},
            )

        agents_server = AgentsMCPServerStdio(
            {
                "command": sys.executable,
                "args": ["-m", SERVER_MODULE],
                "cwd": str(Path.cwd()),
            },
            cache_tools_list=True,
            use_structured_content=True,
        )
        async with agents_server:
            agents_tools = await agents_server.list_tools()
            assert [tool.name for tool in agents_tools] == ["get_indicator_snapshot"]
            agents_result = await agents_server.call_tool(
                "get_indicator_snapshot",
                {"ticker": "goog", "indicator": "rsi"},
            )
        return pydantic_result, agents_result

    pydantic_result, agents_result = asyncio.run(probe())

    expected = {
        "ticker": "GOOG",
        "indicator": "RSI",
        "value": "42.0",
        "source": "LOCAL_READONLY_FIXTURE",
    }
    assert pydantic_result == expected
    assert agents_result.structuredContent == expected
    assert agents_result.isError is False
