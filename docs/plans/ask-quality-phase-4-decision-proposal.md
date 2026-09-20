# Ask Quality Discovery — Phase 4 Decision Proposal

## 1. 决策状态

**Status:** PROPOSED — NO-GO PENDING LIVE EVIDENCE

Phase 3 已证明两个 Runtime、两条 Research Contract 和最小 Persistence Boundary 在架构上可支持。
但固定模型 Runtime、两条 Research 路径和 PostgreSQL Prototype 均缺少受控 Live Evidence，因此本提案
不请求立即开始 Phase 4 Production Implementation。

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

Alibaba Native 必须证明固定 `qwen3.7-max`、实际 Region / Responses Endpoint 能返回可绑定的 URL
Citation；Application-owned 必须证明一个 Brave Search Provider 加受控 Fetch 能取得足够相关、及时且
可读取的来源。缺少其中任一证据时不应进入 Production Research 替换。

### Persistence：保持 PositionPilot-owned Boundary

Phase 4 应沿用 Account-owned Conversation 与 Confirmed Strategy 的 Application Boundary。Framework
History 只承载一次 Runtime 的 Message，不拥有持久状态或确认语义。最终 Thread / Message / Strategy
Schema、Migration、API 和生命周期必须在 Phase 4 计划中设计并重新进入相应 Human Review Gate。

## 3. 解除 No-go 的最小证据

不扩展 Phase 3 范围，只需在显式 Process Environment 下执行：

1. 同一 `qwen3.7-max`、同一 Region / Endpoint 的 Current Runtime 与 PydanticAI No-tool / One-tool
   Live Smoke；
2. Alibaba Responses `web_search` / `web_extractor` 的一个公开研究任务，确认实际 Search、Source
   Citation、Usage 与 Failure；
3. 一个 Brave Search + Controlled Fetch 的同任务运行，记录 Source、读取状态、Latency 与可得费用；
4. 一个显式 `SPIKE_DATABASE_URL` 临时 Schema Integration Test；
5. 更新 `decision-evidence.json` 和 Phase 3 Report，不新增模型或第二个 Search Provider。

如果固定模型或 Endpoint 不支持 Native Research，记录实际限制，不更换 Runtime 实验模型。只有另行
标记的 Native Capability Test 才能使用其他模型，其结果不得参与同模型 Runtime / Research 比较。

## 4. Phase 4 后续工作

解除 No-go 并经 Human Review 后，Phase 4 Implementation Plan 再处理：

- Production Thread / Message / Run Schema、Migration、API 与前端交互；
- History 裁剪、Retention、Deletion、Streaming、Cancellation 与 Observability；
- Production Research Adapter、最终 Source / Citation Contract 与 Metadata Policy；
- StrategyCandidate、唯一 Pending Mutation、确认、版本、失效、并发与幂等；
- 完整 Broker / Account Execution Constraints 和 Fractional Share Domain Contract；
- 生产预算 / Latency / Cost SLO、完整 Failure Code；
- 4A / 4B Dataset、Repeat、unseen、连续 Ask 与 Human Acceptance；
- 正式默认模型或 Provider 更换所需的独立 Eval。

## 5. Human Review 请求

请确认：

1. 接受当前 `NO_GO_PENDING_LIVE_EVIDENCE`，暂不开始 Phase 4 Production Implementation；
2. 接受 Current Runtime 为暂定推荐、PydanticAI 为可行备选；
3. Research Provider 暂不选择，待上述最小 Live Evidence 后更新本提案；
4. Persistence 继续由 PositionPilot 拥有，不把 Conversation / Strategy Truth 交给 Framework。
