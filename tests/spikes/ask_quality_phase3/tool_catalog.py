"""Phase 3 Framework Spike 的最小动态 Tool Catalog。"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from position_pilot.application.llm import LLMToolDefinition

from .current_runtime import ToolExecutor


class ToolCatalogError(ValueError):
    """Tool 启用或暴露请求无效。"""


@dataclass(frozen=True, slots=True)
class CatalogTool:
    """Application-owned Tool 定义与执行器。"""

    definition: LLMToolDefinition
    executor: ToolExecutor
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class ExposedTools:
    """一次 Run 真正暴露给 Framework 的最小 Tool 集合。"""

    definitions: tuple[LLMToolDefinition, ...]
    executors: Mapping[str, ToolExecutor]


class ToolCatalog:
    """按启用状态与本轮需求筛选 Tool，不把完整目录长期暴露给模型。"""

    def __init__(self, tools: Iterable[CatalogTool]) -> None:
        entries = tuple(tools)
        names = [entry.definition.name for entry in entries]
        if len(names) != len(set(names)):
            raise ToolCatalogError("DUPLICATE_TOOL_NAME")
        self._tools = {entry.definition.name: entry for entry in entries}

    def expose(self, requested_names: Iterable[str]) -> ExposedTools:
        """只返回存在、启用且本轮请求的 Tool。"""

        requested = tuple(requested_names)
        if len(requested) != len(set(requested)):
            raise ToolCatalogError("DUPLICATE_REQUESTED_TOOL")
        unknown = [name for name in requested if name not in self._tools]
        if unknown:
            raise ToolCatalogError(f"UNKNOWN_TOOL:{','.join(unknown)}")
        disabled = [name for name in requested if not self._tools[name].enabled]
        if disabled:
            raise ToolCatalogError(f"DISABLED_TOOL:{','.join(disabled)}")
        selected = tuple(self._tools[name] for name in requested)
        return ExposedTools(
            tuple(entry.definition for entry in selected),
            {entry.definition.name: entry.executor for entry in selected},
        )
