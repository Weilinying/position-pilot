"""Application-owned Tool Catalog、授权策略与本轮 Tool 暴露规划。"""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from position_pilot.application.llm import LLMToolCall, LLMToolDefinition

CURRENT_QUOTE_TOOL_NAME = "get_current_quote"
MARKET_CONTEXT_TOOL_NAME = "get_market_context"
MAX_TOOL_CALLS_PER_ROUND = 4


class ToolCatalogError(ValueError):
    """Tool Catalog、授权或暴露请求无效。"""


class ToolRiskClass(StrEnum):
    """Tool 对业务状态的影响级别。"""

    READ_ONLY = "READ_ONLY"
    MUTATION = "MUTATION"


class ToolSourcePolicy(StrEnum):
    """Tool 返回的数据来源约束。"""

    FINANCIAL_DATA = "FINANCIAL_DATA"
    OPEN_RESEARCH = "OPEN_RESEARCH"
    APPLICATION_STATE = "APPLICATION_STATE"


@dataclass(frozen=True, slots=True)
class ToolDescriptor:
    """由 Application 持有的稳定 Tool Contract 与安全元数据。"""

    tool_id: str
    version: str
    definition: LLMToolDefinition
    capability_tags: tuple[str, ...]
    risk_class: ToolRiskClass
    source_policy: ToolSourcePolicy

    def __post_init__(self) -> None:
        if not self.tool_id.strip():
            raise ValueError("Tool id 不能为空")
        if not self.version.strip():
            raise ValueError("Tool version 不能为空")
        if self.tool_id != self.definition.name:
            raise ValueError("Tool id 必须与 Tool name 一致")
        if len(self.capability_tags) != len(set(self.capability_tags)):
            raise ValueError("Tool capability tags 不能重复")

    @property
    def name(self) -> str:
        """返回 Provider-neutral Tool 名称。"""

        return self.definition.name


@dataclass(frozen=True, slots=True)
class ToolExecutionResult:
    """Tool Executor 返回的最小结构化结果边界。"""

    status: str
    data: Mapping[str, object] | None = None
    error_code: str | None = None
    sources: tuple[Mapping[str, object], ...] = ()

    def __post_init__(self) -> None:
        if not self.status.strip():
            raise ValueError("Tool Result status 不能为空")
        if self.error_code is not None and not self.error_code.strip():
            raise ValueError("Tool Result error_code 必须是非空字符串或 None")


ToolExecutor = Callable[[Mapping[str, object]], ToolExecutionResult]


class ToolProvider(Protocol):
    """列出 Application Tool Contract 并解析对应 Executor 的 Provider。"""

    def list_descriptors(self) -> tuple[ToolDescriptor, ...]: ...

    def resolve(self, tool_name: str) -> ToolExecutor | None: ...


@dataclass(frozen=True, slots=True)
class CatalogTool:
    """Catalog 中的一条 Descriptor 与 Executor 绑定。"""

    descriptor: ToolDescriptor
    executor: ToolExecutor


class StaticToolProvider:
    """用于当前进程 Tool 注册的静态 Provider；不负责用户配置持久化。"""

    def __init__(self, tools: Iterable[CatalogTool]) -> None:
        entries = tuple(tools)
        descriptors = tuple(entry.descriptor for entry in entries)
        names = tuple(descriptor.name for descriptor in descriptors)
        if len(names) != len(set(names)):
            raise ToolCatalogError("DUPLICATE_TOOL_NAME")
        self._descriptors = descriptors
        self._executors = {entry.descriptor.name: entry.executor for entry in entries}

    def list_descriptors(self) -> tuple[ToolDescriptor, ...]:
        """按注册顺序返回 Descriptor。"""

        return self._descriptors

    def resolve(self, tool_name: str) -> ToolExecutor:
        """解析已注册 Tool 的 Executor。"""

        try:
            return self._executors[tool_name]
        except KeyError as error:
            raise ToolCatalogError(f"UNKNOWN_TOOL:{tool_name}") from error


class DescriptorToolProvider:
    """只提供 Contract 的 Provider；Tool 执行由独立 Application Executor 负责。"""

    def __init__(self, descriptors: Iterable[ToolDescriptor]) -> None:
        self._descriptors = tuple(descriptors)

    def list_descriptors(self) -> tuple[ToolDescriptor, ...]:
        """按注册顺序返回 Descriptor。"""

        return self._descriptors

    def resolve(self, tool_name: str) -> ToolExecutor | None:
        """Descriptor-only Provider 不承担执行。"""

        del tool_name
        return None


class ToolAccessPolicy(Protocol):
    """根据 Account 与风险级别判断 Tool 是否可以进入本轮。"""

    def is_allowed(self, account_id: UUID, descriptor: ToolDescriptor) -> bool: ...


@dataclass(frozen=True, slots=True)
class StaticToolAccessPolicy:
    """当前阶段的最小只读授权策略。"""

    enabled_names: frozenset[str] | None = None
    allowed_risk_classes: frozenset[ToolRiskClass] = frozenset({ToolRiskClass.READ_ONLY})

    def is_allowed(self, account_id: UUID, descriptor: ToolDescriptor) -> bool:
        """按启用清单与风险级别判断；当前不将 Account ID 写入 Tool Contract。"""

        del account_id
        return descriptor.risk_class in self.allowed_risk_classes and (
            self.enabled_names is None or descriptor.name in self.enabled_names
        )


@dataclass(frozen=True, slots=True)
class ToolExposure:
    """一次 Run 实际交给 Framework 的最小 Tool 集合。"""

    descriptors: tuple[ToolDescriptor, ...]
    definitions: tuple[LLMToolDefinition, ...]
    executors: Mapping[str, ToolExecutor]


@dataclass(frozen=True, slots=True)
class ToolCallExposure:
    """模型首轮 Tool Calls 加上 Application Required Context Floor 的结果。"""

    model_tool_calls: tuple[LLMToolCall, ...]
    required_tool_calls: tuple[LLMToolCall, ...]
    effective_tool_calls: tuple[LLMToolCall, ...]
    tools: ToolExposure


class ToolCatalog:
    """按 Provider 注册顺序保存 Tool，并在 Framework 前执行边界校验。"""

    def __init__(self, providers: Iterable[ToolProvider]) -> None:
        descriptors: list[ToolDescriptor] = []
        executors: dict[str, ToolExecutor] = {}
        for provider in providers:
            for descriptor in provider.list_descriptors():
                if any(item.name == descriptor.name for item in descriptors):
                    raise ToolCatalogError("DUPLICATE_TOOL_NAME")
                descriptors.append(descriptor)
                executor = provider.resolve(descriptor.name)
                if executor is not None:
                    executors[descriptor.name] = executor
        self._descriptors = tuple(descriptors)
        self._by_name = {descriptor.name: descriptor for descriptor in self._descriptors}
        self._executors = executors

    @property
    def descriptors(self) -> tuple[ToolDescriptor, ...]:
        """返回稳定注册顺序的全部 Descriptor。"""

        return self._descriptors

    @property
    def names(self) -> tuple[str, ...]:
        """返回稳定注册顺序的 Tool 名称。"""

        return tuple(descriptor.name for descriptor in self._descriptors)

    def expose(
        self,
        requested_names: Iterable[str],
        *,
        account_id: UUID,
        policy: ToolAccessPolicy,
    ) -> ToolExposure:
        """返回存在、授权且按 Catalog 顺序排列的本轮 Tool。"""

        requested = tuple(requested_names)
        if len(requested) != len(set(requested)):
            raise ToolCatalogError("DUPLICATE_REQUESTED_TOOL")
        unknown = tuple(name for name in requested if name not in self._by_name)
        if unknown:
            raise ToolCatalogError(f"UNKNOWN_TOOL:{','.join(unknown)}")
        unauthorized = tuple(
            name for name in requested if not policy.is_allowed(account_id, self._by_name[name])
        )
        if unauthorized:
            raise ToolCatalogError(f"UNAUTHORIZED_TOOL:{','.join(unauthorized)}")
        requested_set = set(requested)
        selected = tuple(
            descriptor for descriptor in self._descriptors if descriptor.name in requested_set
        )
        return ToolExposure(
            descriptors=selected,
            definitions=tuple(descriptor.definition for descriptor in selected),
            executors={
                descriptor.name: self._executors[descriptor.name]
                for descriptor in selected
                if descriptor.name in self._executors
            },
        )

    def validate_call_names(self, tool_calls: tuple[LLMToolCall, ...]) -> None:
        """在执行前拒绝超预算或未注册的 Tool Call。"""

        if len(tool_calls) > MAX_TOOL_CALLS_PER_ROUND:
            raise ToolCatalogError(f"TOOL_CALL_LIMIT_EXCEEDED:{MAX_TOOL_CALLS_PER_ROUND}")
        unknown = tuple(call.name for call in tool_calls if call.name not in self._by_name)
        if unknown:
            raise ToolCatalogError(f"UNKNOWN_TOOL:{','.join(dict.fromkeys(unknown))}")


class ToolExposurePlanner:
    """结合授权策略与 Context Floor 计算本轮最小 Tool 暴露集合。"""

    def __init__(
        self,
        catalog: ToolCatalog,
        policy: ToolAccessPolicy,
        *,
        account_id: UUID,
    ) -> None:
        self._catalog = catalog
        self._policy = policy
        self._account_id = account_id

    def plan(self, requested_names: Iterable[str]) -> ToolExposure:
        """为显式请求选择最小、授权且稳定排序的 Tool 集合。"""

        return self._catalog.expose(
            requested_names,
            account_id=self._account_id,
            policy=self._policy,
        )

    def plan_calls(self, model_tool_calls: tuple[LLMToolCall, ...]) -> ToolCallExposure:
        """复现当前 Runtime 的 Required Context Floor 与四次调用上限。"""

        self._catalog.validate_call_names(model_tool_calls)
        required = self.required_context_floor(model_tool_calls)
        effective = (*model_tool_calls, *required)
        self._catalog.validate_call_names(effective)
        names = tuple(dict.fromkeys(call.name for call in effective))
        return ToolCallExposure(
            model_tool_calls=model_tool_calls,
            required_tool_calls=required,
            effective_tool_calls=effective,
            tools=self.plan(names),
        )

    @staticmethod
    def required_context_floor(
        model_tool_calls: tuple[LLMToolCall, ...],
    ) -> tuple[LLMToolCall, ...]:
        """只为 Discretionary Quote 补足一个 Market Context。"""

        if any(call.name == MARKET_CONTEXT_TOOL_NAME for call in model_tool_calls):
            return ()
        requires_market_context = any(
            call.name == CURRENT_QUOTE_TOOL_NAME
            and call.arguments.get("request_purpose") == "DISCRETIONARY_CURRENT_RISK_ACTION"
            for call in model_tool_calls
        )
        if not requires_market_context:
            return ()
        existing_ids = {call.id for call in model_tool_calls}
        call_id = "required-market-context"
        suffix = 1
        while call_id in existing_ids:
            call_id = f"required-market-context-{suffix}"
            suffix += 1
        return (LLMToolCall(call_id, MARKET_CONTEXT_TOOL_NAME, {}),)


def current_financial_tool_descriptors(
    definitions: tuple[LLMToolDefinition, ...],
) -> tuple[ToolDescriptor, ...]:
    """将现有金融 Tool 映射为 Catalog Descriptor，不复制其 Contract。"""

    return tuple(
        ToolDescriptor(
            tool_id=definition.name,
            version="v1",
            definition=definition,
            capability_tags=(definition.name.removeprefix("get_"), "financial_data"),
            risk_class=ToolRiskClass.READ_ONLY,
            source_policy=ToolSourcePolicy.FINANCIAL_DATA,
        )
        for definition in definitions
    )
