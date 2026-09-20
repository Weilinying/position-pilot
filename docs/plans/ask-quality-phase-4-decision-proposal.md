# Ask Quality Discovery — Phase 4 Decision Proposal

## 1. 决策状态

**Status:** PROPOSED — NO-GO PENDING LIVE EVIDENCE

Phase 3 已证明两个 Runtime、两条 Research Contract 和最小 Persistence Boundary 在架构上可支持。
但固定模型 Runtime 与两条 Research 路径均缺少受控 Live Evidence，因此本提案不请求立即开始
Phase 4 Production Implementation。PostgreSQL 17 临时 Schema Prototype 已补测通过。

2026-09-20 收口 Review：AQ06 已改为金额分析优先，旧 Execution Gate 只作为历史 Baseline；完整
Broker / Fractional Execution Contract 不再是 Phase 4 前置工作。Research 结论同时区分 A Alibaba
Native、B Application-owned 与 C Existing Financial Data，C 是优先使用的结构化事实层，不是第三个
Runtime 候选。

## 2. 暂定推荐

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

## 3. 解除 No-go 的最小证据

不扩展 Phase 3 范围，只需在显式 Process Environment 下执行：

1. 同一 `qwen3.7-max`、同一 Region / Endpoint 的 Current Runtime 与 PydanticAI No-tool / One-tool /
   最小多轮 Tool Calling Live Smoke，记录 Tool Selection、Arguments、Failure、Latency 与 Token；
2. Alibaba Responses `web_search` / `web_extractor` 的一个公开研究任务，确认实际 Search、Source
   Citation、Usage 与 Failure；
3. 一个 Brave Search + Controlled Fetch 的同任务运行，确认真实正文进入模型、最终引用来自实际
   Source Registry，并记录读取状态、Latency 与可得费用；
4. 更新 `decision-evidence.json` 和 Phase 3 Report，不新增模型或第二个 Search Provider。

如果固定模型或 Endpoint 不支持 Native Research，记录实际限制，不更换 Runtime 实验模型。只有另行
标记的 Native Capability Test 才能使用其他模型，其结果不得参与同模型 Runtime / Research 比较。
步骤 1 与 Native 能力测试只需要 `LLM_API_KEY` / `LLM_BASE_URL`，可以在没有 Brave Key 时先完成；
`BRAVE_SEARCH_API_KEY` 只用于步骤 3，不得因此阻塞其他 Runtime 证据。

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

1. 接受当前 `NO_GO_PENDING_LIVE_EVIDENCE`，暂不开始 Phase 4 Production Implementation；
2. 接受 Current Runtime 为暂定推荐、PydanticAI 为可行备选；
3. Research Provider 暂不选择，待上述最小 Live Evidence 后更新本提案；
4. Persistence 继续由 PositionPilot 拥有，不把 Conversation / Strategy Truth 交给 Framework。
