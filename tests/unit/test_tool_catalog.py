"""P4-T1 Tool Catalog、授权与 Context Floor 的定向测试。"""

from collections.abc import Mapping
from dataclasses import replace
from uuid import UUID

import pytest

from position_pilot.application.investment_agent import (
    CONTEXT_TOOLS,
    CURRENT_QUOTE_TOOL_NAME,
    MARKET_CONTEXT_TOOL_NAME,
    MAX_TOOL_CALLS_PER_ROUND,
    RECENT_NEWS_TOOL_NAME,
)
from position_pilot.application.llm import LLMToolCall
from position_pilot.application.tool_catalog import (
    CatalogTool,
    StaticToolAccessPolicy,
    StaticToolProvider,
    ToolCatalog,
    ToolCatalogError,
    ToolExecutionResult,
    ToolExposurePlanner,
    ToolRiskClass,
    current_financial_tool_descriptors,
)

ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000001")


def _executor(_arguments: Mapping[str, object]) -> ToolExecutionResult:
    """返回最小成功结果。"""

    return ToolExecutionResult("OK", {"value": "fixture"})


def _catalog() -> ToolCatalog:
    """创建当前四个 Financial Tool 的测试 Catalog。"""

    return ToolCatalog(
        (
            StaticToolProvider(
                CatalogTool(descriptor, _executor)
                for descriptor in current_financial_tool_descriptors(CONTEXT_TOOLS)
            ),
        )
    )


def _planner(*, enabled_names: frozenset[str] | None = None) -> ToolExposurePlanner:
    """创建固定 Account 下的 Tool Exposure Planner。"""

    return ToolExposurePlanner(
        _catalog(),
        StaticToolAccessPolicy(enabled_names=enabled_names),
        account_id=ACCOUNT_ID,
    )


def _quote_call(
    *,
    call_id: str = "quote-1",
    purpose: str = "INFORMATION_RETRIEVAL",
) -> LLMToolCall:
    """创建当前 Quote Tool Call。"""

    return LLMToolCall(
        call_id,
        CURRENT_QUOTE_TOOL_NAME,
        {"ticker": "GOOG", "request_purpose": purpose},
    )


def test_current_financial_contracts_keep_names_order_description_and_schema() -> None:
    """Catalog 不复制或改写既有四个金融 Tool Contract。"""

    descriptors = current_financial_tool_descriptors(CONTEXT_TOOLS)
    assert tuple(descriptor.definition for descriptor in descriptors) == CONTEXT_TOOLS
    assert tuple(descriptor.name for descriptor in descriptors) == tuple(
        tool.name for tool in CONTEXT_TOOLS
    )
    assert (
        tuple(descriptor.risk_class for descriptor in descriptors) == (ToolRiskClass.READ_ONLY,) * 4
    )
    assert tuple(descriptor.version for descriptor in descriptors) == ("v1",) * 4
    assert tuple(descriptor.max_calls_per_run for descriptor in descriptors) == (2, 2, 2, 1)


def test_exposure_budget_follows_authorized_tool_quotas() -> None:
    """工具集合或单工具额度变化时，总额度从 Descriptor 自动求和。"""

    descriptors = current_financial_tool_descriptors(CONTEXT_TOOLS)
    catalog = ToolCatalog(
        (StaticToolProvider(CatalogTool(item, _executor) for item in descriptors),)
    )
    policy = StaticToolAccessPolicy()

    assert catalog.expose((), account_id=ACCOUNT_ID, policy=policy).tool_call_budget == 0
    assert (
        catalog.expose(
            (CURRENT_QUOTE_TOOL_NAME,), account_id=ACCOUNT_ID, policy=policy
        ).tool_call_budget
        == 2
    )
    assert catalog.expose(catalog.names, account_id=ACCOUNT_ID, policy=policy).tool_call_budget == 7

    changed = (replace(descriptors[0], max_calls_per_run=3), *descriptors[1:])
    changed_catalog = ToolCatalog(
        (StaticToolProvider(CatalogTool(item, _executor) for item in changed),)
    )
    assert (
        changed_catalog.expose(
            changed_catalog.names, account_id=ACCOUNT_ID, policy=policy
        ).tool_call_budget
        == 8
    )


@pytest.mark.parametrize("limit", (0, -1, True))
def test_tool_quota_must_be_a_finite_positive_call_count(limit: int) -> None:
    """未定义有效额度的 Tool 不得进入预算派生。"""

    descriptor = current_financial_tool_descriptors(CONTEXT_TOOLS)[0]
    with pytest.raises(ValueError, match="额度必须是正整数"):
        replace(descriptor, max_calls_per_run=limit)


def test_exposure_uses_catalog_order_and_only_requested_enabled_tools() -> None:
    """每轮只暴露请求且启用的 Tool，并保留原有 Catalog 顺序。"""

    planner = _planner(enabled_names=frozenset({RECENT_NEWS_TOOL_NAME, CURRENT_QUOTE_TOOL_NAME}))

    exposure = planner.plan((RECENT_NEWS_TOOL_NAME, CURRENT_QUOTE_TOOL_NAME))

    assert tuple(definition.name for definition in exposure.definitions) == (
        CURRENT_QUOTE_TOOL_NAME,
        RECENT_NEWS_TOOL_NAME,
    )
    assert tuple(exposure.executors) == (
        CURRENT_QUOTE_TOOL_NAME,
        RECENT_NEWS_TOOL_NAME,
    )


def test_exposure_rejects_unknown_duplicate_and_disabled_tools_before_framework() -> None:
    """未知、重复和禁用 Tool 在进入 Framework 前失败。"""

    planner = _planner(enabled_names=frozenset({CURRENT_QUOTE_TOOL_NAME}))

    with pytest.raises(ToolCatalogError, match="UNKNOWN_TOOL"):
        planner.plan(("missing_tool",))
    with pytest.raises(ToolCatalogError, match="DUPLICATE_REQUESTED_TOOL"):
        planner.plan((CURRENT_QUOTE_TOOL_NAME, CURRENT_QUOTE_TOOL_NAME))
    with pytest.raises(ToolCatalogError, match="UNAUTHORIZED_TOOL"):
        planner.plan((RECENT_NEWS_TOOL_NAME,))


def test_required_context_floor_matches_current_discretionary_quote_behavior() -> None:
    """Discretionary Quote 缺少 Market Context 时只追加一次 Required Tool。"""

    plan = _planner().plan_calls((_quote_call(purpose="DISCRETIONARY_CURRENT_RISK_ACTION"),))

    assert tuple(call.name for call in plan.required_tool_calls) == (MARKET_CONTEXT_TOOL_NAME,)
    assert tuple(call.name for call in plan.effective_tool_calls) == (
        CURRENT_QUOTE_TOOL_NAME,
        MARKET_CONTEXT_TOOL_NAME,
    )


def test_required_context_floor_does_not_apply_to_information_or_rule_quote() -> None:
    """事实查询和既定规则检查不会机械追加 Market Context。"""

    for purpose in ("INFORMATION_RETRIEVAL", "RULE_OR_EXECUTION_CHECK"):
        plan = _planner().plan_calls((_quote_call(purpose=purpose),))
        assert plan.required_tool_calls == ()
        assert plan.effective_tool_calls == plan.model_tool_calls


def test_required_context_floor_does_not_duplicate_explicit_market_context() -> None:
    """模型已经选择 Market Context 时，Floor 不产生重复调用。"""

    calls = (
        _quote_call(purpose="DISCRETIONARY_CURRENT_RISK_ACTION"),
        LLMToolCall("market-1", MARKET_CONTEXT_TOOL_NAME, {}),
    )
    plan = _planner().plan_calls(calls)

    assert plan.required_tool_calls == ()
    assert plan.effective_tool_calls == calls


def test_required_context_floor_respects_four_call_budget() -> None:
    """四次模型 Tool Call 后需要 Floor 时不得突破现有上限。"""

    calls = tuple(
        _quote_call(
            call_id=f"quote-{index}",
            purpose="DISCRETIONARY_CURRENT_RISK_ACTION",
        )
        for index in range(MAX_TOOL_CALLS_PER_ROUND)
    )

    with pytest.raises(ToolCatalogError, match="TOOL_CALL_LIMIT_EXCEEDED"):
        _planner().plan_calls(calls)


def test_required_context_floor_avoids_model_call_id_collision() -> None:
    """Required Tool Call ID 与模型 ID 冲突时使用稳定递增后缀。"""

    plan = _planner().plan_calls(
        (
            _quote_call(
                call_id="required-market-context",
                purpose="DISCRETIONARY_CURRENT_RISK_ACTION",
            ),
        )
    )

    assert plan.required_tool_calls[0].id == "required-market-context-1"


def test_mutation_risk_is_denied_by_default_policy() -> None:
    """默认策略只允许当前阶段的只读 Tool。"""

    descriptor = current_financial_tool_descriptors(CONTEXT_TOOLS)[0]
    mutation = descriptor.__class__(
        tool_id="write_test",
        version="v1",
        definition=descriptor.definition.__class__(
            "write_test",
            "测试写入 Tool",
            {"type": "object", "properties": {}, "additionalProperties": False},
        ),
        capability_tags=("test",),
        risk_class=ToolRiskClass.MUTATION,
        source_policy=descriptor.source_policy,
        max_calls_per_run=1,
    )
    provider = StaticToolProvider((CatalogTool(mutation, _executor),))
    catalog = ToolCatalog((provider,))
    planner = ToolExposurePlanner(
        catalog,
        StaticToolAccessPolicy(),
        account_id=ACCOUNT_ID,
    )

    with pytest.raises(ToolCatalogError, match="UNAUTHORIZED_TOOL"):
        planner.plan(("write_test",))
