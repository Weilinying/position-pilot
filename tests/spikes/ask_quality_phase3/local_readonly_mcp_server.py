"""供 Framework Spike 使用的本地只读 MCP Server。"""

from mcp.server.fastmcp import FastMCP

server = FastMCP("position-pilot-phase3-readonly")


@server.tool()
def get_indicator_snapshot(ticker: str, indicator: str) -> dict[str, str]:
    """返回固定指标快照；不读取或修改 Portfolio 状态。"""

    return {
        "ticker": ticker.upper(),
        "indicator": indicator.upper(),
        "value": "42.0",
        "source": "LOCAL_READONLY_FIXTURE",
    }


if __name__ == "__main__":
    server.run(transport="stdio")
