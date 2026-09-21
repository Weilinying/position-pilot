# ADR 0015：Phase 4 使用 PydanticAI Production Runtime

**Status:** Accepted
**Date:** 2026-09-21

## Context

PositionPilot 当前 `InvestmentAgent` 使用自有 LLM / Tool Loop。Phase 3 保留该 Runtime 作为基线，
并对 PydanticAI 与 OpenAI Agents SDK 完成动态 Tool、本地只读 MCP、状态注入、Source Boundary 和
固定 Qwen Endpoint 的 Capability Spike。

Phase 4 需要服务端 Conversation、按请求暴露的 Tool Catalog、后续可插拔 Memory Retrieval，以及
Provider-neutral 的业务状态与安全边界。Framework 可以管理一次 Run 的模型循环，但不能成为
Portfolio、Conversation、Persistent User Intent、Memory、Tool Authorization 或 Source 的事实源。

## Decision

- Phase 4 Production Agent Runtime 采用 PydanticAI，保持 Single Agent。
- Current Runtime 只作为迁移期间的冻结回归基线；不建设长期双 Runtime、请求级 Shadow Run 或双份
  Conversation / Memory State。
- PydanticAI Adapter 只负责一次 Run 的 Message Mapping、Model / Tool Loop、Framework Budget、Usage /
  Latency 与 Provider Failure Mapping。
- PositionPilot 继续拥有 Portfolio Ledger、Transaction、Cash、Conversation Ownership、Persistent User
  Intent、Memory Lifecycle、Tool Authorization、Source Registry、Citation Validation 和 Mutation Boundary。
- Production Model / Provider 配置不因 Framework 迁移而改变。Phase 3 的固定模型结果是兼容性证据，
  正式切换前仍需用部署时实际配置完成最小 Live Smoke。
- Research Provider 与 Runtime 分开决策。Brave `NOT_MEASURED` 不阻塞 Runtime / Conversation；任何
  Production Open Research Adapter 继续经过独立 Human Review Gate。
- Current Runtime 退出 Production 后，回滚使用 Phase 4 前的 Application Artifact；不长期保留
  Runtime 选择开关。Additive Conversation / Strategy 数据不因 Runtime 回滚而删除。

具体执行边界、4A / 4B Checkpoint 与 State Authority 以获批的
[Phase 4 Implementation Plan](../plans/ask-quality-phase-4-implementation.md) 为准。

## Alternatives / Trade-off

- 继续长期维护 Current Runtime 可以避免新增依赖，但需要持续自建 Toolset、MCP、History、Usage 和
  Provider 适配能力，并扩大核心 Agent 的维护面。
- OpenAI Agents SDK 已证明当前 Endpoint 的基础 Tool Calling 兼容，但没有提供足以抵消当前迁移成本的
  OpenAI 专属产品价值，因此不进入 Phase 4 Production 双轨。
- PydanticAI 提供的能力不替代 Application-owned Contract。该边界会保留一定 Adapter 代码，但避免
  Framework State 污染金融事实、用户确认和权限语义。

## Consequences

- Phase 4 需要 Production `AgentRuntime` Port 与 PydanticAI Adapter，并将 PydanticAI 从 Spike-only
  Dependency 移入 Production Dependency。
- Current Runtime Characterization Fixture 和 Phase 3 Artifact 继续保留，但 Production Bootstrap 最终
  只装配 PydanticAI。
- Framework 更换不会要求迁移 Ledger、Conversation、Persistent User Intent、Memory 或 Source 数据。

## Reconsider When

- PydanticAI 在已批准 Contract 下出现无法通过正常 Adapter 修复的真实 Architecture Limit；
- OpenAI 专属能力形成明确且有价值的产品需求；
- 当前模型 / Provider 无法通过独立 Compatibility Eval；
- 产品需要 Multi-Agent 或 Durable Workflow，且 Single Agent + Application-owned State 已证明不足。

任何重新考虑都必须通过新的 ADR / Capability Spike 和 Human Review，不在 Phase 4 内临时扩展。
