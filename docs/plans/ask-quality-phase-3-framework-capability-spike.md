# Ask Quality Discovery — Phase 3 Agent Framework Capability Spike

## 1. 目标与边界

**Status:** COMPLETE — PYDANTICAI RECOMMENDED / HUMAN REVIEW REQUIRED

本 Spike 在保留原 Phase 3 全部代码、Artifact 与报告的前提下，将 PydanticAI 与 OpenAI Agents SDK
作为最后两个 Framework 候选，Current Runtime 只作为对照基线。它验证框架接入能力，不修改
Production Agent，不迁移现有业务代码，不新增 Production Dependency、Migration、Research Provider
或完整 Memory 系统。

Portfolio Ledger、确定性金融计算、Conversation、Confirmed Strategy、Account Ownership、Tool
Authorization、Source Validation 与 Long-term Memory Retrieval 继续由 PositionPilot 拥有。Framework
只负责单次 Run 的模型循环、Tool 调用和 Message 映射。本轮继续使用 Single Agent。

## 2. 分阶段执行计划与验收标准

### P3-F1 — 基线与隔离

- 复用 Phase 3 的 `RuntimeInput`、Budget、Tool / Source Contract、Prompt 语义和固定模型。
- 保留历史 Report，不把离线 Fixture 解释为真实模型质量证据。

验收：三条 Runtime 路径使用等价 Application Input；新增依赖仅属于 `spike` Group；Production Code
与数据库 Schema 无修改。

### P3-F2 — 动态 Tool 与本地 MCP

- 使用 Application-owned Tool Catalog 验证启用、禁用、未知 Tool 拒绝和按需暴露。
- 两个候选连接同一个本地 stdio、只读、固定输出的 MCP Tool，验证 `tools/list` 与 `tools/call`。

验收：禁用或未选择 Tool 不进入本轮模型 Tool 集合；本地 MCP Tool 可被两个官方 Client 发现并
调用；实验不提供任何 Portfolio、Strategy、Conversation 或文件写入能力。

### P3-F3 — PydanticAI Prototype Gap

- 将硬编码三 Tool Bridge 改为基于现有 JSON Schema Contract 的动态 Toolset。
- Usage 缺失或全零时保持 `UNKNOWN`，Provider / Tool / Budget Failure 显式分类。
- 继续复用统一 Source Registry，拒绝未观察 Source ID / URL。

验收：任意代表性只读 Tool 可由普通 Adapter 接入；Usage 不被伪造成零成本；已有异常和 Source
Validation 测试通过。Adapter Bug 不得归类为 `ARCHITECTURE_LIMIT`。

### P3-F4 — OpenAI Agents SDK + Qwen

- 在 Spike 内实现 Provider-neutral Input、Tool Observation、Budget、Source 与 Failure 的薄 Adapter。
- 离线验证 No-tool、动态 One-tool、Multi-tool、Usage UNKNOWN 和 Provider Failure。
- 为固定 `qwen3.7-max`、同一 Region / Endpoint 提供显式 Opt-in No-tool、One-tool、Multi-tool Live
  Smoke；由用户本地执行。

验收：离线路径可重复；Live Run 记录 Tool Selection、Arguments、Latency、Usage 或
`USAGE_NOT_REPORTED`。若 Endpoint 不兼容，记录实际限制，不更换模型。

### P3-F5 — Application State 与决策

- 复用现有 Conversation / Confirmed Strategy / Ownership Persistence Prototype。
- 用只读 Retrieval Fixture 把 Long-term Memory 命中作为独立 Context 注入三个 Runtime。
- 基于实际证据、依赖与 Bridge 成本给出 Framework 推荐。

验收：有界 History、Confirmed Strategy 和 Memory Retrieval 可通过同一 Application Boundary 注入；
Draft Strategy 不进入 Context；不新增 Memory 表、写入、确认、失效或向量检索。最终选型必须等待
OpenAI Agents SDK 的 Qwen Live Smoke，且仍需 Human Review。

## 3. 执行顺序与停止条件

执行顺序为 F1 → F2 / F3 → F4 Offline → F5 Offline → F4 Live → Decision。Security、Ownership、
Mutation Boundary 或 Source Integrity 失败是硬停止条件；正常 Adapter 缺口、Provider 未回传 Usage 或
尚未执行 Live Smoke 分别记录为 `PROTOTYPE_GAP`、`UNKNOWN`、`NOT_MEASURED`，不伪装成架构失败。
