# Ask Quality Discovery — Phase 3 Agent Framework Capability Report

## 1. 状态与历史关系

**Status:** HUMAN ACCEPTED（2026-09-21）— PYDANTICAI SELECTED FOR PHASE 4

本报告的实验结果保持不变。Human Review 已接受 PydanticAI 作为 Phase 4 Production Agent Framework；
Current Runtime 仅作为迁移回归基线，OpenAI Agents SDK 暂不进入 Production，Phase 3 至此完成。

本报告是 2026-09-21 的追加证据，不覆盖
[Phase 3 Capability Spike Report](ask-quality-phase-3-report.md) 的历史实验、分数或当时暂定结论。
Current Runtime 保留为对照基线；最后两个候选为 PydanticAI 1.107.6 与 OpenAI Agents SDK 0.22.3。

所有实现均位于 `tests/spikes/ask_quality_phase3/`，依赖只加入 `spike` Group。Production Agent、
Portfolio Ledger、API、Schema、Migration 与 Research Provider 均未修改。

## 2. 实际验证结果

| 能力 | PydanticAI | OpenAI Agents SDK | 证据等级 |
|---|---|---|---|
| 动态 Tool Schema | `SUPPORTED`；已移除三 Tool 硬编码 | `SUPPORTED` | 真实框架代码 + Scripted Model |
| 启用 / 禁用 / 按需暴露 | `SUPPORTED`；共享 Application Catalog / RuntimeInput | `SUPPORTED`；模型只看到本轮所选 Tool | 离线确定性测试 |
| 本地只读 MCP | 官方 `MCPToolset` 可发现并调用 | 官方 `MCPServerStdio` 可发现并调用 | 真实本地 stdio Server |
| Usage Mapping | 全零或缺失映射为 `UNKNOWN` | 全零或缺失映射为 `UNKNOWN` | 离线 Adapter 测试 |
| Tool / Provider Failure | 显式 Budget、Tool Warning、Candidate Failure | 同左 | 离线确定性测试 |
| Source Validation | 复用统一 Source Registry；虚构来源被拒绝 | 同左 | 离线确定性测试 |
| Conversation / Strategy | 通过既有 Application State Boundary 注入 | 同左 | 离线框架执行 |
| Long-term Memory | 只读 Retrieval Result 独立注入 | 同左 | Fixture；未实现 Memory 系统 |
| 当前 Qwen Endpoint | No-tool 通过；One-tool / Multi-tool 均实际调用，Multi-tool Final 被 Source Validation 安全拒绝 | No-tool、One-tool 通过；Multi-tool 依次完成 Search / Fetch，Final 被同一 Source Validation 安全拒绝 | 用户本地真实模型 Live |

动态 Tool Catalog 只返回存在、启用且本轮请求的定义和 Executor，因此完整 Tool 目录不需要长期占用
模型 Context。它仍是 PositionPilot-owned Authorization Boundary，不把 Tool 启用状态交给 Framework。

本地 MCP 测试使用同一个无网络、无副作用的 `get_indicator_snapshot` Server。两个候选均真实执行
MCP discovery 和 call；该证据不等同于已实现用户插件生命周期、远程 MCP Trust、OAuth 或 Skills。

PydanticAI 旧的三 Tool Bridge 是 `PROTOTYPE_GAP`，本轮已用框架正常的 schema-based Tool API 修复，
未重写框架内部逻辑，因此不是 `ARCHITECTURE_LIMIT`。Usage 全零不再导致伪造的零 Token 结论，改为
`USAGE_NOT_REPORTED`。旧 Live Run 暴露的零 Usage 与虚构来源分别归类为 Provider Usage 缺失和模型
Grounding 行为，不归类为框架无法执行 Tool。

OpenAI Agents SDK 已通过真实 SDK Runner 的离线 No-tool、One-tool、Multi-tool、Source Failure、Usage
UNKNOWN 和 Provider Failure 路径。真实 Qwen Live 中 No-tool 与 One-tool 完成；Multi-tool 严格按
`search_web → fetch_page` 调用并传递了观察 URL，随后最终回答因引用未观察来源而被拒绝。这证明当前
Endpoint 的多轮 Tool Calling 兼容，不证明模型的最终 Grounding 已达 Production 标准。

## 3. Persistence 与 Memory 边界

三个 Runtime 均消费同一个 `StateContext`：有界 Conversation、仅 Confirmed Strategy，以及独立的
`retrieved_memories`。测试确认 Draft Strategy 不进入 Context。Memory 命中被明确标为 Application
检索结果，不是 Portfolio / Ledger 事实。

现有 PostgreSQL Conversation / Strategy Prototype 和 Owner Boundary 原样保留；本轮没有新增表。
PostgreSQL Integration 未重复执行，因为框架只消费 `inject_state` 后的统一输入，数据库归属和查询
语义没有改变。完整 Memory 写入、确认、版本、失效、删除、向量检索和 Retention 留给后续设计。

## 4. 验证记录与证据边界

本轮新增 / 受影响定向验证结果：`23 passed, 1 skipped`；完整 Phase 3 Spike 回归结果：
`88 passed, 12 skipped`。跳过项包括需要显式 `SPIKE_DATABASE_URL` 的既有 PostgreSQL Integration，
以及未启用的 11 项 Online Smoke；数据库路径在原 Phase 3 已验证，本轮未改变。PydanticAI 仍有一条
第三方 Event Loop Deprecation Warning，不影响测试结果，但正式锁定版本时应复核。

用户在固定 `qwen3.7-max` 与当前 `LLM_BASE_URL` 下执行 OpenAI Agents SDK Live Smoke，结果为
`2 passed, 1 failed in 13.65s`。失败项的 Runtime Artifact 显示 Search / Fetch 均成功，Tool 顺序和 URL
传递正确，Latency 为 `8267.51ms`；失败码是 `UNOBSERVED_SOURCE_REFERENCE`。因此该项按证据拆为：

- Multi-tool Runtime / Provider Compatibility：`SUPPORTED`；
- Source Validation：`SUPPORTED`，正确阻止虚构引用进入回答；
- 固定模型 Multi-tool Final Grounding：`PROTOTYPE_GAP`；
- 该次失败 Run 的 Token Usage：原 Adapter 在 Final Validation Failure 路径中丢失，`NOT_MEASURED`。

本轮已修正最后一项 Adapter Gap：Final Validation Failure 现在仍保留已发生的 Model Trace 与 Usage，
并用离线测试覆盖。没有放宽 Source Gate，也没有为取得绿色结果更换模型或修改历史 Live 结果。

## 5. 当前决策判断

动态工具、MCP 和状态注入没有暴露任一候选的架构硬限制。两者都需要 PositionPilot 保留 Tool Catalog、
业务状态、Source 与 Mutation Boundary；Framework 不能替代这些应用职责。

**建议 Phase 4 选择 PydanticAI，Current Runtime 保留为迁移对照与回退基线。**

理由：

- PydanticAI 已验证当前 Alibaba / Qwen 原生 Provider 接入，动态 Schema Tool Gap 可用公开 Adapter API
  正常修复；不需要改写框架内部逻辑。
- 两个候选都支持动态 Tool、MCP 和 Application-owned State Injection；OpenAI Agents SDK 没有在本轮
  显示足以抵消当前 Qwen Chat Completions 兼容层与 0.x SDK 版本维护成本的独有收益。
- 未来切换 OpenAI 模型时，PydanticAI 仍可通过其 OpenAI Provider 接入；模型切换不要求同时迁移 Agent
  Runtime。正式更换默认模型仍需独立 Eval。
- 两个候选在 Multi-tool 后都暴露相同的固定模型 Grounding Gap，说明问题应由 Answer / Source Contract
  与 Eval 处理，不能作为迁移到 OpenAI Agents SDK 的理由。

该建议不授权 Production Migration。Phase 4 Plan 应先实现 PydanticAI Adapter、动态 Tool Catalog 和
Application-owned Conversation / Strategy Boundary 的最小纵向切片，并保留 Current Runtime 回归对照。
若未来出现 PydanticAI 无法支持的真实 Failure，或 OpenAI 专属能力成为明确产品需求，再重开 ADR，
不在当前 Spike 预建双 Runtime Production Abstraction。
