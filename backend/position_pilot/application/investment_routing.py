"""Investment Agent 的 Context Selection 诊断模型。"""

from dataclasses import dataclass
from enum import StrEnum

from position_pilot.application.investment_context import PortfolioSnapshot
from position_pilot.application.llm import LLMToolCall
from position_pilot.domain.portfolio import PositionType


class ContextSelectionMode(StrEnum):
    """首轮 Completion 选择外部 Context 的方式。"""

    NO_EXTERNAL_CONTEXT = "NO_EXTERNAL_CONTEXT"
    NATIVE_TOOL_SELECTION = "NATIVE_TOOL_SELECTION"


@dataclass(frozen=True, slots=True)
class ContextSelectionTrace:
    """不记录问题正文或用户身份的一次 Context Selection 摘要。"""

    mode: ContextSelectionMode
    available_tools: tuple[str, ...]
    selected_tools: tuple[str, ...]
    selected_context_count: int
    selected_existing_position_count: int
    selected_existing_position_types: tuple[PositionType, ...]
    selected_unheld_ticker_count: int

    @classmethod
    def from_tool_calls(
        cls,
        *,
        snapshot: PortfolioSnapshot,
        available_tools: tuple[str, ...],
        tool_calls: tuple[LLMToolCall, ...],
    ) -> "ContextSelectionTrace":
        """从已通过参数校验的 Native Tool Calls 构造稳定 Trace。"""

        unique_contexts = tuple(
            dict.fromkeys(
                (
                    tool_call.name,
                    _validated_ticker(tool_call),
                )
                for tool_call in tool_calls
            )
        )
        selected_tickers = {ticker for _, ticker in unique_contexts}
        matching_positions = tuple(
            position for position in snapshot.positions if position.ticker in selected_tickers
        )
        held_tickers = {position.ticker for position in snapshot.positions}
        return cls(
            mode=(
                ContextSelectionMode.NATIVE_TOOL_SELECTION
                if tool_calls
                else ContextSelectionMode.NO_EXTERNAL_CONTEXT
            ),
            available_tools=available_tools,
            selected_tools=tuple(dict.fromkeys(tool_call.name for tool_call in tool_calls)),
            selected_context_count=len(unique_contexts),
            selected_existing_position_count=len(matching_positions),
            selected_existing_position_types=tuple(
                sorted(
                    {position.position_type for position in matching_positions},
                    key=lambda position_type: position_type.value,
                )
            ),
            selected_unheld_ticker_count=len(selected_tickers - held_tickers),
        )

    def as_log_extra(self, *, routing_latency_ms: float) -> dict[str, object]:
        """转换为结构化日志字段，不暴露问题、User ID 或 ticker。"""

        return {
            "selection_mode": self.mode.value,
            "available_tools": self.available_tools,
            "selected_tools": self.selected_tools,
            "selected_context_count": self.selected_context_count,
            "selected_existing_position_count": self.selected_existing_position_count,
            "selected_existing_position_types": tuple(
                position_type.value for position_type in self.selected_existing_position_types
            ),
            "selected_unheld_ticker_count": self.selected_unheld_ticker_count,
            "routing_latency_ms": routing_latency_ms,
        }


def _validated_ticker(tool_call: LLMToolCall) -> str:
    """读取 Agent 已验证为非空字符串的 ticker。"""

    ticker = tool_call.arguments["ticker"]
    assert isinstance(ticker, str)
    return ticker.strip().upper()
