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

### 2026-09-24 Final Output 补充决定

AQ07 在线证据显示 Prompt-only JSON 候选格式错误后，一次 Repair 会耗尽剩余 30 秒预算。
独立固定 Quote Spike 中，当前 Qwen Endpoint 能先调用金融工具，再通过 PydanticAI
`ToolOutput` 返回合法候选。Human Review 因此批准仅将 PydanticAI Adapter 的 `JSON_OBJECT`
最终输出改为 Final Output Tool；`TEXT` 请求不变。不对含工具的请求强制 Provider-native
`response_format=json_object`。

Output Tool 只约束候选基本形状；对已返回的候选，PositionPilot 的 Structured Answer、Source
Identity、Citation 与一次无 Tool Repair 仍是 Application-owned Gate。Framework 隐式 Output Retry 保持关闭，
Model / Tool Budget、30 秒总上限及 Public API 均不变。独立 Spike 不是完整 AQ07 验收，
Production Adapter 仍须通过真实 AQ07 回归与 4A Human Review。
若模型连 Output Tool 的基本参数形状都未提供，Framework 不会产出候选，Adapter 将其标为
`INVALID_PROVIDER_RESPONSE`；这种失败无法进入 Application 的候选 Repair。暂不增加隐藏 Framework
Retry 或兜底文本路径，先由完整 AQ07 在线回归判断其实际发生情况。

### 2026-09-24 Native Timeout 补充决定

完整 AQ07 的 30 秒在线运行重复在工具返回后的第二次模型请求期间耗尽预算。配对诊断中
首次模型请求分别为 `6.17s` / `17.53s`，Fixture Tool 均在毫秒内返回；60 秒臂在
`29.01s` 完成，30 秒臂未返回 Final Candidate。Human Review 批准仅把 PydanticAI
Production Native 的总 Wall-clock 与单次 Provider Request Timeout 调整至 60 秒。
Current Runtime 的 `LLM_REQUEST_TIMEOUT_SECONDS=30` 回归基线保持不变；新增独立的
`NATIVE_LLM_REQUEST_TIMEOUT_SECONDS=60`。Model / Tool 次数、无隐式 Retry、Source / Citation
校验与公共 API 均不变。一次 60 秒成功不证明稳定性，AQ07 回答质量和完整 4A Gate 仍需另行验证。

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

### 2026-10-05 实施与回退证据

4A 已获 Human Acceptance；4B 仅保存显式确认、按仓位 scope 隔离的持续意图，Primary / Repeat
已获有限接受，AQ12 r1 语言概括偏强保留为例外。PydanticAI 为唯一 Production Bootstrap Runtime，
Gemini 官方接线仍只在 Eval；NoOp Memory、Research 延期等边界未扩大。
T8 真实浏览器 / SQL 及应用 Artifact 回退演练完成，保留 additive Schema 与所有业务数据，
[最终报告](../evaluation/reports/2026-10-05-phase4-t8-final.md)等待 Final Human Acceptance；未 merge / push。
该记录是已批准方案的实施证据，不引入新框架、Provider、Migration 回退或发布承诺。
