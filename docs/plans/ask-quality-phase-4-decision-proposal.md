# Ask Quality Discovery — Phase 4 Decision Proposal

## 1. 决策状态

**Current Status (2026-09-21):** FRAMEWORK RECOMMENDATION READY — HUMAN REVIEW REQUIRED

**Historical Status (2026-09-20):** PROPOSED — NO-GO PENDING LIVE EVIDENCE

Phase 3 已证明两个 Runtime、两条 Research Contract 和最小 Persistence Boundary 在架构上可支持。
但固定模型 Runtime 与两条 Research 路径均缺少受控 Live Evidence，因此本提案不请求立即开始
Phase 4 Production Implementation。PostgreSQL 17 临时 Schema Prototype 已补测通过。

2026-09-20 收口 Review：AQ06 已改为金额分析优先，旧 Execution Gate 只作为历史 Baseline；完整
Broker / Fractional Execution Contract 不再是 Phase 4 前置工作。Research 结论同时区分 A Alibaba
Native、B Application-owned 与 C Existing Financial Data，C 是优先使用的结构化事实层，不是第三个
Runtime 候选。

### 1.1 Framework 预选修订（2026-09-21）

保留本提案下方的 Current Runtime 暂定推荐作为历史阶段判断。经后续框架预选，PydanticAI 与
OpenAI Agents SDK 成为最后两个候选，Current Runtime 改为对照基线。新增离线 Capability Spike 已
证明两个候选均可支持动态 Tool、只读本地 MCP、Application-owned Source Boundary，以及现有
Conversation / Confirmed Strategy / Memory Retrieval 注入；详见
[Framework Capability Report](ask-quality-phase-3-framework-capability-report.md)。OpenAI Agents SDK 在
当前固定 Qwen Endpoint 的 No-tool / One-tool / Multi-tool Live Evidence 尚未取得，因此 Framework
最终推荐与 Phase 4 Implementation Plan 仍等待该项证据和 Human Review。Research 选型与 Runtime
选型继续相互独立，Brave 未验证不阻塞本次 Runtime 补证。

### 1.2 Framework Capability Spike 结论（2026-09-21）

OpenAI Agents SDK 的固定 Qwen Live Smoke 已执行：No-tool、One-tool 完成；Multi-tool 实际按
`search_web → fetch_page` 完成调用和 URL 传递，但最终回答因引用未观察来源而被统一 Source Gate
安全拒绝。该结果证明 Tool Calling 兼容，同时暴露固定模型 Grounding Gap，不构成 SDK
`ARCHITECTURE_LIMIT`。PydanticAI 的既有 Multi-tool Live Evidence 具有相同分类。

综合当前 Qwen 原生 Provider、动态 Tool / MCP、未来 OpenAI Provider、多轮状态注入，以及迁移和维护
成本，当前正式建议 Phase 4 采用 **PydanticAI**；Current Runtime 保留为对照基线。OpenAI Agents SDK
不进入 Phase 4 双轨实现，但保留为未来 OpenAI 专属能力出现真实需求时的重评候选。Brave 的在线验证
仍不是 Runtime 选型或 Phase 4 Conversation / Strategy 计划的阻塞条件。

## 2. 暂定推荐

> 以下 Current Runtime 推荐保留为 2026-09-20 的历史阶段判断；当前 Framework 推荐以 1.2 节为准。

### Runtime：Current Runtime

暂定使用 Application-owned Current Runtime 进入 Phase 4 设计，理由：

- 直接复用现有 Provider-neutral Message / Tool / Result Contract；
- Tool Schema、Failure、Source 与业务状态继续由 PositionPilot 明确拥有；
- 不新增完整 Agent Framework 依赖或额外 Tool Bridge；
- 离线能力与 PydanticAI 等价，当前没有测得 PydanticAI 的质量、Latency 或维护优势。

PydanticAI 仍是 `SUPPORTED` 候选。其三 Tool Bridge、消息表示差异和未完成 Production 接线属于
`PROTOTYPE_GAP`，不是 `ARCHITECTURE_LIMIT`。若 Live Run 显示其 Tool Loop、Usage 或 Provider 行为具有
明显优势，应重新比较，而不是沿用本暂定推荐。

### Research：暂不选择

Application-owned Research 暂时更容易明确满足 Source Registry、Query Privacy、Fetch Security 和
Search / Fetch 可观察性；Alibaba Native Research 可能减少 Application 编排并提供 Provider-managed
多轮检索。但两者都没有 Live Evidence，不能在本轮选择 Production Provider。

现有 Alpaca Quote、History、Recent News 和 SPY Market Context 继续先回答其覆盖范围内的问题。只有
文章全文、开放来源发现、跨来源核验、Filing / 财报或结构化工具未覆盖的事件才进入 A / B Research。
当前没有新增 Yahoo Finance、Finnhub 或其他金融数据 Provider 的需求证据，Brave 也只是实验候选。

Alibaba Native 必须证明固定 `qwen3.7-max`、实际 Region / Responses Endpoint 能返回可绑定的 URL
Citation；Application-owned 必须证明一个 Brave Search Provider 加受控 Fetch 能取得足够相关、及时且
可读取的来源。缺少其中任一证据时不应进入 Production Research 替换。

### Persistence：保持 PositionPilot-owned Boundary

Phase 4 应沿用 Account-owned Conversation 与 Confirmed Strategy 的 Application Boundary。Framework
History 只承载一次 Runtime 的 Message，不拥有持久状态或确认语义。最终 Thread / Message / Strategy
Schema、Migration、API 和生命周期必须在 Phase 4 计划中设计并重新进入相应 Human Review Gate。

## 3. 证据状态与剩余 Gate

Runtime 的最小 Live Evidence 已满足：Current Runtime、PydanticAI 与 OpenAI Agents SDK 均取得固定
Qwen 的真实执行证据；Tool Selection、Arguments、Source Failure、Latency 与 Usage / UNKNOWN Mapping
已能区分。Multi-tool Final Grounding 仍是 `PROTOTYPE_GAP`，应进入 Phase 4 固定 Eval，不再阻塞
Framework 选择。

Research 继续独立处理。Alibaba Native Capability 已执行；Application-owned Brave 仍为
`NOT_MEASURED` 备选。现有 Alpaca Financial Data 加 Alibaba Native Research 足以支持当前 Phase 4
规划，不因缺少 Brave Key 阻塞 Conversation、Strategy、Tool Catalog 或 Runtime 实现。若未来具体问题
证明需要 Application-owned Search / Fetch，再单独验证并进入 Provider Human Review Gate。

进入 Phase 4 Implementation Plan 前剩余 Gate 只有：Human 明确批准 PydanticAI 选型、确认 Current
Runtime 仅作为迁移回归基线，以及批准 Phase 4 的具体范围。该批准不等于自动开始 Production 实现。

## 4. Phase 4 后续工作

解除 No-go 并经 Human Review 后，Phase 4 Implementation Plan 再处理：

- Production Thread / Message / Run Schema、Migration、API 与前端交互；
- History 裁剪、Retention、Deletion、Streaming、Cancellation 与 Observability；
- Production Research Adapter、最终 Source / Citation Contract 与 Metadata Policy；
- StrategyCandidate、唯一 Pending Mutation、确认、版本、失效、并发与幂等；
- 将本轮 Budget 结构化并由确定性代码提供理论股数（如 Phase 4 产品路径需要股数回答）；
- 生产预算 / Latency / Cost SLO、完整 Failure Code；
- 4A / 4B Dataset、Repeat、unseen、连续 Ask 与 Human Acceptance；
- 正式默认模型或 Provider 更换所需的独立 Eval。

## 5. Human Review 请求

请确认：

1. 接受 PydanticAI 作为 Phase 4 Agent Framework，Current Runtime 只保留为迁移回归基线；
2. 不为 OpenAI Agents SDK 建立 Production 双轨实现，出现 OpenAI 专属真实需求时再重评；
3. Research 选型保持独立，Brave `NOT_MEASURED` 不阻塞 Phase 4；
4. Conversation、Strategy、Memory Retrieval、Tool Authorization 与 Portfolio Truth 继续由
   PositionPilot 拥有；
5. 批准后先制定 Phase 4 Implementation Plan，不在本 Decision Proposal 中直接实施 Production 迁移。
