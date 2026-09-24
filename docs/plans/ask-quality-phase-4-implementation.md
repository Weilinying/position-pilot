# Ask Quality Discovery — Phase 4 Implementation Plan

## 1. 状态、目标与批准依据

**Status:** HUMAN ACCEPTED — P4-T0 ～ P4-T4A COMPLETE，P4-T5 CORE IN PROGRESS（2026-09-23）。
P4-T2 已将 Production Bootstrap 切换为单一 PydanticAI Runtime；Current Runtime 只保留为回归基线。

**Strategy Review Revision（2026-09-21）：** Strategy Candidate 仅承载跨会话 Persistent User Intent；
Current Recommendation 与 Ledger Derived Facts 不进入 Strategy。Pending 冲突域为
`account + scope + kind`，Position Plan 表达当前资本配置目标。历史 Phase 2 / Phase 3 证据不改写。

**Native Timeout Revision（2026-09-24，Human Approved）：** AQ07 同模型在线诊断中，
30 秒总预算重复在第二次模型请求期间耗尽；60 秒诊断完成一次，但不代表稳定性已验收。
PydanticAI Production Native 路径的 Wall-clock Ceiling 与单次 Provider Request Timeout
均调整为 60 秒；Model / Tool / Research 次数和无隐式 Retry 规则不变。旧 Current Runtime
的 30 秒请求配置及既有 Phase 3 / 4A Artifact 均不回写。4A Gate 仍需完整回归和 Human Review。

Phase 3 已通过 Human Acceptance，批准的架构边界为：

- Production Agent Runtime 采用 PydanticAI；
- Current Runtime 只作为迁移回归基线，不建设长期双 Runtime；
- Research Provider 与 Runtime 独立，Brave `NOT_MEASURED` 不阻塞 Phase 4；
- Portfolio Ledger、Transaction、Cash、Confirmed Strategy / Persistent User Intent、Conversation Ownership、Memory
  Lifecycle、Tool Authorization 与 Source Registry 均由 PositionPilot 持有；
- Single Agent 保持不变。

Phase 4 的目标是交付第一个完整 Ask 闭环：4A 完成 PydanticAI、服务端 Conversation、动态只读
Toolset、现有 Financial Data 与 Citation；Open Research 经过独立 Gate 后接入。通过固定 Eval 后，
4B 再完成最小 Persistent User Intent 生命周期。它不是完整 Memory、插件平台或投资复盘 Milestone。

截至 P4-T4A，Production Agent 已通过 Application-owned `AgentRuntime` Port 使用 PydanticAI 原生
Tool Loop；Conversation Thread / Turn / Message / Source 已由 PositionPilot 持有，前端使用 Thread API。
Strategy 表仍待 4B。Phase 3 `tests/spikes/` 只能作为 Contract 与测试证据，不得被 Production 代码导入。

### 1.1 本次 Human Review 需要明确批准的产品选择

以下是本计划提出的 Phase 4 最小规则，不是 Phase 3 已经批准的事实；批准本计划才表示接受：

- Conversation 初始只注入最近 20 条 User / Assistant Message，并另受序列化长度上限约束；
- Thread 使用软删除，物理 Retention / Account Erasure Policy 后续单独评审；每个 Thread 同时最多一个
  RUNNING Turn，Phase 4 使用同步 POST；
- 每个 `account + scope + kind` 冲突域最多一个 Pending Strategy Candidate；不同 ticker / position type /
  kind 允许同时 Pending。Candidate 默认 24 小时过期；确认只走明确 Candidate UI / API，不把自然语言
  肯定词直接视为持久化授权；Candidate 只表达需要跨会话持续生效的用户意图，不保存普通实时
  Recommendation；
- 4B 只实现 `POSITION_PLAN_V1`、`INVESTMENT_THESIS_V1`、`HOLDING_HORIZON_V1`；
- Answer V2 使用 `[source:<source_id>]` near-claim token，由前端映射为经验证的 Source；
- 初始 Run Safety Ceiling 为 4 次 Model Request、4 次 Tool Call、2 次 Research、30 秒 wall-clock；
  Native Timeout Revision 后仅 PydanticAI Production Native wall-clock 改为 60 秒，仍是安全上限而非
  Production SLO；
- 旧 `/v1/investment/questions` 在 Phase 4 保持 deprecated compatibility，不创建 Thread、不生成
  Strategy Candidate，也不启用 Open Research。

这些选择可以在 Human Review 中单独调整，不改变已批准的 PydanticAI Framework 结论。

## 2. In Scope / Out of Scope

### 2.1 In Scope

- PydanticAI Production Adapter、Provider / Failure / Usage Mapping 与结构化输出；
- Application-owned Context Builder、Tool Catalog、Tool Authorization、Source Registry；
- Account-owned Thread、Turn、Message、Observed Source 的 PostgreSQL Schema、Migration、Repository、
  API 和前端恢复；
- 有界 Conversation History、本轮 Budget / Intent Correction 与跨刷新 / 重新登录恢复；
- 现有 Alpaca Quote、History、News、SPY Market Context 接入 PydanticAI Toolset；
- 一个 Provider-neutral Open Research Tool Boundary；Alibaba Native 只作为当前首选候选，Production
  Adapter 必须通过独立 Research Decision Gate 后才能实施；
- Inline / near-claim Citation 与持久 Source Metadata；
- Strategy Candidate、明确确认、版本、替代、失效、过期、幂等与并发保护；
- 基于 Confirmed Position Plan 与实时 Ledger 的确定性 `PositionFundingSnapshot`；
- Long-term Memory 的只读 Retrieval Port、`NoOp` Production Default 与 Fixture 注入测试；
- 4A / 4B Eval、Migration 验证、Human Acceptance、Runtime Cutover 与 Rollback 演练。

### 2.2 Out of Scope

- 完整 Long-term Memory 数据表、自动提取、确认 UI、编辑 / 删除、Embedding、Vector Database 或 RAG；
- Multi-Agent、LangGraph、durable workflow、跨进程 Run Resume 或 Queue；
- Skills Framework、Skills Marketplace、用户上传代码、远程 MCP Trust / OAuth、通用插件安装；
- 大规模 Tool Semantic Search；Phase 4 只实现 enabled / disabled 与按请求暴露的扩展接口；
- Brave 或第二个 Search Provider、Yahoo Finance、Finnhub Financial Data 等新增 Research Provider；
- 自动交易、Broker Connection、Execution Contract、碎股权限验证或订单数量保证；
- 投资复盘、行为偏差分析、自动生成长期偏好；
- 持久 Decision Memory、价格触发器、tranche、某次具体买入金额或历史 Recommendation 自动执行；
- Token Streaming、持久 Tool Trace、复杂 Conversation Summary、全文搜索和物理 Retention Job；
- 默认模型 / Provider 更换；正式换模继续使用独立 Eval。

## 3. Target Architecture 与职责

```text
Session Account
  → Conversation API / Strategy API
  → ConversationService / StrategyService
  → ContextBuilder
      ├─ Portfolio / Ledger Facts
      ├─ PositionFundingSnapshot（每轮确定性计算）
      ├─ Bounded Conversation History
      ├─ Confirmed Persistent User Intent
      └─ MemoryReader Retrieval Result（Phase 4 默认为空）
  → InvestmentAgent Application Facade
      ├─ ToolCatalog + ToolAccessPolicy
      ├─ SourceRegistry
      └─ AgentRuntime Port
             └─ PydanticAIRuntimeAdapter
                    → 当前 Production Model / Provider Configuration
                    → Application-owned Tool Executors
  → Answer / Citation Validation
  → Current Recommendation + Sources
  → optional Pending Intent Candidate（仅持久用户意图）
```

PydanticAI 只拥有一次 Run 的 Message Mapping、Model Loop、Function Tool 调用、Usage / Latency 与
Provider Error Mapping。它不得读取 ORM，不得写 Conversation / Strategy / Memory / Ledger，也不得
成为 Source 或 Tool Permission 的事实源。

`InvestmentAgent` 继续作为 Application Facade，但从当前大文件中逐步移出：Context Construction、
Tool Execution、Source Validation 和 Runtime Adapter。现有确定性 Portfolio / Quote / History / News /
Market Context 逻辑原样复用，不在迁移时重写金融规则。

### 3.1 四类状态的职责与优先级

| 类型 | 事实源 / 生命周期 | 可以做什么 | 不可以做什么 |
|---|---|---|---|
| Portfolio Facts | Ledger / Portfolio；交易后即时变化 | 提供 Cash、Quantity、Average Cost、Position Type、当前持仓成本及确定性计算，拥有最高业务事实权威 | 被 Strategy、Memory 或模型文本覆盖；因 Recommendation 自动改变 |
| Persistent User Intent | 仅 Confirmed Version；显式确认、版本化、可失效 | 保存 ticker、Position Type scope、总目标预算、长期 thesis / horizon，描述用户持续目标 | 保存已投入、剩余预算、实时价格或当前建议；覆盖 Ledger / 新市场证据；充当订单 |
| Conversation / Decision Memory | Conversation Message 持久化；Future Decision Memory 本阶段不实现 | 保存当时问题、回答、来源和决策背景，帮助理解上下文 | 成为持续指令、价格触发器或交易事实；未经重新评估直接复用历史 Recommendation |
| Current Recommendation | 每次 Run 根据当前事实、意图、市场、Research、启用 Tool 与相关 Memory 重新生成 | 给出当前时点的条件式分析和金额建议 | 自动提升为 Strategy / Memory、直接写 Ledger，或在未来条件再次出现时自动执行 |

Context Builder 的顺序固定为：先读取 Portfolio / Ledger Facts 并执行确定性计算，再加入 Confirmed
Persistent User Intent、当前 Turn 与有界 Conversation / Memory Background，随后取得最新 Market /
Research / Tool Observation，最后生成本轮 Recommendation。旧 Thesis / Horizon 可影响分析目标，但新
事实与证据可以使 Agent 给出不同建议；用户在当前 Turn 的纠正可以形成新 Candidate，但确认前不替换
现有 Intent。当前 Turn 的明确纠正可以立即用于本轮分析，但只有确认后的版本才跨会话持续生效。

`PositionFundingSnapshot` 是只读派生 Context，不是 Strategy 或持久事实副本。它至少包含匹配
`ticker + position_type` 的 confirmed `target_budget`、Ledger 当前 Quantity / Average Cost / open cost
basis，以及 `remaining_target_budget = max(target_budget - open_cost_basis, 0)`。交易变化后必须重新计算；
价格变化不改写成本基础。若用户本轮另给 Budget，它继续与 Cash、remaining target budget 分开保存，
只在确定性分析中形成当轮上限；缺少本轮 Budget 时不得把 Cash 或 remaining target budget 当成用户已
授权全部投入的金额。若 open cost basis 已达到或超过 target budget，remaining 为 0；这不自动产生卖出
建议或修改持仓。

这里冻结的资金语义是：`target_budget` 表示该 `ticker + position_type` Scope 的**目标当前资本配置**，
不是历史累计 BUY 上限；`open_cost_basis` 只表示当前仍持有仓位的成本基础，使用 Ledger 对该 Scope 的
剩余持仓确定性计算。卖出使 open cost basis 降低，因此释放相同语义下的 target budget 空间。公式不得
改用累计历史 BUY，也不得混入 realized proceeds、Cash、Market Value 或当前价格。未来若需要“累计投入
上限”等语义，必须作为新的独立产品概念进入 Human Review，不能复用 `POSITION_PLAN_V1.target_budget`。

## 4. Production Runtime 与 Current Runtime 迁移

### 4.1 AgentRuntime Port

新增 Provider-neutral Production Contract，输入至少包括：

- 当前 Account / Thread 的受信 Conversation History；
- Current Turn Context、Portfolio Facts、PositionFundingSnapshot、Confirmed Persistent User Intent、
  Memory Retrieval Result；
- 本轮已授权 Tool Definitions / Executors；
- Model Request、Tool、Research、Wall-clock Budget。

输出至少包括：Structured Answer Candidate、Model / Tool Trace、Observed Sources、Usage 或
`UNKNOWN`、Latency、Warnings 与稳定 Failure Code。Production Contract 不暴露 PydanticAI Message、
Agent、Toolset 或 Exception 类型。

### 4.2 PydanticAI Adapter

Production Adapter 使用 Phase 3 已验证的 Alibaba-compatible Provider 接入方式、`message_history`、
动态 Schema Tool 和 `UsageLimits`，但重新实现于 Production Integration 层，不从 Spike import。
Phase 4 沿用部署时现有 Production Model / Provider 配置；Phase 3 的固定 `qwen3.7-max` 只是兼容性
证据，不自动成为 Production Default。PydanticAI 依赖从
`spike` Group 以已验证版本加入 Production Dependencies；OpenAI Agents SDK 保持 Spike-only。

Adapter 负责：

- Application Message ↔ PydanticAI Message 映射；
- JSON Schema Tool ↔ Function Tool 映射；
- Provider / UsageLimit / Tool Exception → PositionPilot Failure Contract；
- Model Requests、Tool Calls、Usage / UNKNOWN 与 Latency Trace。

Application 继续负责：Tool 参数和权限、Search / Fetch Budget、Source Registration、Final Citation
Validation、Answer JSON / 业务 Contract Validation、Strategy Candidate Validation，以及 Tool Failure
后是否允许 Final Answer。只有经过这些 Application Gate 的结果才称为 Validated Answer。

Candidate Validation 还必须证明候选来自当前用户明确表达的长期意图或持久计划请求；普通实时建议、
Tool Observation、Research 内容和 Assistant 自行提出的交易判断不得进入 Candidate。

更换现有 Production Model、Provider 或 Endpoint 不属于 Runtime Migration；如确有需要，必须单独
提交 Model / Provider Decision Proposal，并用独立 Eval 验证。

### 4.3 Current Runtime 退出

迁移期间不做 Shadow Request 或双模型调用。先用固定 Fixture 和真实模型 Eval 比较 PydanticAI 与冻结的
Current Runtime 基线；达到 4A Gate 后，Production Bootstrap 只装配 PydanticAI。旧
`/v1/investment/questions` 在兼容期也调用 PydanticAI，不继续装配 Legacy Runtime。

最终删除 Production `InvestmentAgent` 内旧的手写 Model / Tool Loop，只保留可复用的业务 Contract、
Tool Executor、Source Validator 及历史测试 Artifact。Current Runtime 的行为 Fixture 留在测试中；如需
回滚，部署 Phase 4 前的 Application Artifact，不在 Production 长期保留 Runtime 选择开关。

## 5. Production Tool Catalog / Toolset

新增 Application-owned `ToolCatalog`，核心对象为：

- `ToolDescriptor`：稳定 ID / name、version、description、JSON Schema、capability tags、
  `READ_ONLY` / `MUTATION` risk class、source policy；
- `ToolProvider`：列出 Descriptor 并解析对应 Executor；
- `ToolAccessPolicy`：按 Account、配置、当前产品能力与 risk class 计算 eligible tools；
- `ToolExposurePlanner`：按本轮 Intent / Context capability 选择最小暴露集合；
- `ToolExecutor`：返回结构化 Result、Failure、Source Records，不返回 Framework 对象。

Phase 4 只注册现有只读 Quote、Price History、Recent News、Market Context 与批准的 Open Research
Tool。Agent Toolset 不包含 Portfolio / Ledger / Strategy Mutation；Strategy Confirm / Invalidate 只能走
显式业务 API。未知、重复、禁用、未授权 Tool 必须在进入 Framework 前拒绝。

自定义指标、MCP 与 Skills 未来通过 `ToolProvider` / `ToolDescriptor` 接口接入，不修改 Runtime Port。
Phase 4 不实现插件持久化、用户配置 UI、远程 MCP、Skill Loader 或大型目录的语义检索；当前小目录
使用确定性 capability tags 与 per-run exposure，避免预建未证明必要的 Tool Discovery 系统。

## 6. Conversation / Thread / Message Design（4A）

### 6.1 Production Schema

使用独立 Alembic Additive Migration，新表不修改 Portfolio / Ledger：

**`conversation_threads`**

- `id UUID PK`
- `account_id UUID NOT NULL FK accounts.id`
- `title VARCHAR(200) NULL`，首条用户消息确定性截断生成，不调用 LLM
- `revision BIGINT NOT NULL DEFAULT 0`
- `next_sequence BIGINT NOT NULL DEFAULT 1`
- `created_at / updated_at TIMESTAMPTZ`
- `deleted_at TIMESTAMPTZ NULL`
- `UNIQUE(id, account_id)`，并按 `(account_id, updated_at)` 建索引

**`conversation_turns`**

- `id UUID PK`
- `thread_id / account_id`，复合 FK 到 Thread Owner
- `client_request_id UUID NOT NULL`
- `status RUNNING | COMPLETED | FAILED`
- `failure_code VARCHAR NULL`
- `run_deadline_at TIMESTAMPTZ`
- `created_at / completed_at TIMESTAMPTZ`
- `UNIQUE(thread_id, client_request_id)`，用于网络重试幂等
- Partial Unique Index：每个 Thread 最多一个 `RUNNING` Turn

**`conversation_messages`**

- `id UUID PK`
- `thread_id / account_id / turn_id`
- `sequence BIGINT NOT NULL`
- `role USER | ASSISTANT`
- `content TEXT NOT NULL`
- `created_at TIMESTAMPTZ`
- `UNIQUE(thread_id, sequence)` 与 `UNIQUE(turn_id, role)`

只持久化用户可见 User / Assistant Message；Tool Call、Observation、隐式思维链和 PydanticAI 内部
Message 不进入 Conversation。Message append-only，不提供编辑 API。

**`message_sources`**

- `source_id UUID PK`、`assistant_message_id FK`
- `source_type`、`provider`、可选 `provider_reference`
- 可选 `url / title / publisher / published_at / event_time`
- `fetched_at`、`content_scope`、`status`
- 未提供 Metadata 使用 `NULL / UNKNOWN`，不伪造完整性

Tool 原始正文、Secret、Query 中的私有 Context 和 Provider Raw Payload 不持久化。

### 6.2 Ownership、并发与生命周期

- 所有 API 从 HttpOnly Session 取得 Account；请求不接受 `account_id` / `user_id` 作为权限依据；
- Thread / Turn / Message 使用复合 Owner FK，Repository 查询始终包含 Account；
- `POST message` 携带 `expected_thread_revision`。短事务锁 Thread，校验 revision 且不存在 RUNNING
  Turn，使用 `next_sequence` 原子分配 User Message sequence，创建 RUNNING Turn，并递增 revision 后
  提交；Partial Unique Index 作为并发兜底，保证两个相同 revision 的请求只有一个进入 LLM；
- 成功后再次锁 Thread，使用 `next_sequence` 分配 Assistant Message sequence，原子提交 Assistant
  Message / Sources / Candidate、完成 Turn 并再次递增 revision；失败只记录 Turn Failure，不伪造
  Assistant Message，并递增 revision 反映状态变化；等待 LLM 时不持有数据库事务；
- 同一 `client_request_id` 重试返回同一 Turn，不重复追加消息或执行外部副作用；
- 同一请求仍为 RUNNING 时返回 `409 TURN_IN_PROGRESS` 和原 `turn_id`；已完成时返回已持久化结果，
  已失败时返回已持久化 Failure，不再次调用模型；
- 请求超时应在可控路径把 Turn 标为 FAILED；进程中断留下的 RUNNING Turn 在下次 Thread 访问时，若已
  超过 `run_deadline_at`，在锁内收敛为 `AGENT_RUN_ABANDONED`，不自动重跑模型；
- Context Builder 初始读取最近 20 条 User / Assistant Message，并受序列化长度上限约束；不做摘要，
  不重放历史市场 Tool Result，当前 Quote / News / Market Context 仍重新取得；
- Delete 在 Phase 4 使用 `deleted_at` 立即从列表、读取与 Agent Context 排除，同时取消该 Thread 的
  所有 Pending Candidate，但不影响其他 Thread / 冲突域的 Candidate；存在 RUNNING Turn 时返回
  `409 TURN_IN_PROGRESS`。物理清除与 Retention Policy 另行 Human Review，不在本阶段假定。

### 6.3 API Contract

- `POST /v1/threads`：创建当前 Account Thread；
- `GET /v1/threads?cursor=&limit=`：列出未删除 Thread；
- `GET /v1/threads/{thread_id}`：读取当前 revision、RUNNING / last Turn 状态和 Thread Metadata；
- `GET /v1/threads/{thread_id}/messages?before=&limit=`：分页读取，并回传当前 thread revision 与
  active Turn status，确保刷新后的客户端可提交 `expected_thread_revision`；
- `POST /v1/threads/{thread_id}/messages`：提交 `content`、`client_request_id`、
  `expected_thread_revision`，同步返回 Turn、User / Assistant Message、Sources、Candidate 与新 revision；
- `DELETE /v1/threads/{thread_id}`：软删除并停止 Context 读取；
- `POST /v1/investment/questions`：迁移期保持单问 Request / Response 兼容并标记 deprecated，不静默
  创建 Thread；它只映射现有 SourceReference 能力，不启用新的 Open Research Citation，也不生成
  Strategy Candidate，前端切换后不再调用。

新的 Thread Message Response 使用 `AnswerV2`：answer text、warnings、结构化 Source / Citation、
optional Candidate 与 Turn metadata。T0 必须冻结 `AnswerV2` / `CitationV2` JSON Schema、Source ID 与
现有 `ContextSource` 的映射，以及旧 `/questions` 的无损兼容规则；PydanticAI 内部结果不是 Public API。

稳定失败至少包括 `THREAD_NOT_FOUND`、`THREAD_CONFLICT`、`TURN_IN_PROGRESS`、
`AGENT_REQUEST_FAILED` 和现有 Provider Failure。跨 Owner 统一表现为不可访问，不泄露对象存在性。

### 6.4 Frontend

- 将 “This tab only” 历史替换为服务端 Thread 列表；登录 / 刷新后加载当前 Thread 与 Messages；
- New Question 创建 Thread，切换 Thread 时取消当前前端请求并加载服务端状态；
- Ask 使用 Thread Message API；重复提交由 `client_request_id` 防止；409 时重新加载 Thread，不自动
  重放问题；
- 展示 Turn Failure、Source / Citation、Pending Strategy Candidate；
- Logout、Session Expiry、Account 切换立即清除 Thread / Candidate 的浏览器状态；
- Answer 继续以 text node 安全渲染；Citation Link 只允许经 Source Registry 返回的 HTTP(S) URL，
  使用安全外链属性，不渲染 Provider HTML。

Phase 4 使用同步 POST 与清晰 Loading State；Token Streaming、Server-side Cancellation 与 Durable
Resume 不进入首个闭环。

## 7. Persistent User Intent / Confirmed Strategy Design（4B）

### 7.1 最小策略范围

Strategy 在 Phase 4 更准确地表示 **Persistent User Intent**，而不是历史 Recommendation。Storage
Envelope 支持 `kind + payload_schema_version + typed JSON payload`，但 4B 只实现并 Eval：

- `POSITION_PLAN_V1`：`ticker`、`position_type LONG_TERM | SWING`、`target_budget Decimal / USD`；表达
  用户对该 Position Scope 的总目标投入，不是本轮 Budget、Cash、订单或自动执行指令；
- `INVESTMENT_THESIS_V1`：ticker / Position Type Scope + 用户确认的 thesis text；只作为可被新证据质疑
  和更新的分析背景；
- `HOLDING_HORIZON_V1`：ticker / Position Type Scope + horizon category 与可选明确期限；只描述用户意图，
  不重新分类或改写 Ledger 中的 Lot / Position Type。

`remaining_budget`、已投入金额、Quantity、Average Cost、Market Value 与 Current Price 禁止进入上述
payload；这些值只从 Portfolio / Ledger / Market Data 动态取得。`POSITION_PLAN_V1.target_budget` 不得
提高 Cash，也不得覆盖用户本轮 Budget。

tranche、价格触发条件、某次具体买入金额、当前“可以买 / 不可以买”的判断、复杂 Exit Rule、自动触发器
与任意自由 Schema 均不进入 Phase 4 Persistent Intent。比如“当前先买 80 美元”或“跌到 320 美元再
加仓”只作为当时的 Conversation / Recommendation 保存；未来价格再次到达 320 时必须重新读取持仓、
成本、剩余目标预算、市场、Research、启用 Tool 与相关 Memory 后生成新建议。

### 7.2 Schema 与生命周期

**`strategy_candidates`**

- owner：`id / account_id / thread_id / source_user_message_id`
- intent：`operation UPSERT | INVALIDATE`、`strategy_id`、规范化 `scope_key`（ticker + position type）、
  kind、typed payload / schema version
- concurrency：`base_version`、`candidate_revision`、`proposal_request_id`、可选 `replaces_candidate_id`
- provenance：`origin USER_STATED_INTENT | USER_REQUESTED_DRAFT`、`purpose PERSISTENT_USER_INTENT`
- lifecycle：`PENDING | CONFIRMED | CANCELLED | EXPIRED | STALE`
- `created_at / expires_at / resolved_at`

Pending 冲突域与实际 Strategy 一致，规范化为 `account_id + scope_key + kind`。数据库使用
`UNIQUE(account_id, scope_key, kind) WHERE status = 'PENDING'` Partial Unique Index；不同 ticker、不同
Position Type Scope 或不同 kind 的 Candidate 可以同时 Pending。

`scope_key` 是 Application 生成的非空规范值，例如 `GOOG:LONG_TERM`；不直接使用客户端自由文本，
避免大小写、空值或别名绕过唯一约束。

同一冲突域已有 Pending 时不得静默覆盖：新 Candidate 只有携带匹配的 `replaces_candidate_id` 与旧
candidate revision，才能在同一事务把旧 Candidate 标为 `CANCELLED` 并创建新 Candidate；否则返回
`409 STRATEGY_CANDIDATE_CONFLICT`。Cancel API 只取消指定 Candidate，不影响其他冲突域。Candidate
仍记录来源 Thread，初始 `expires_at` 为创建后 24 小时；读取时即使尚未写回状态，超过时间也不得确认
或进入 Context。

**`confirmed_strategy_versions`**

- `id / strategy_id / account_id`
- scope、kind、payload / schema version
- `version`、`status ACTIVE | SUPERSEDED | INVALIDATED`
- `previous_version_id / source_candidate_id`
- `confirmed_by_account_id / confirmation_request_id / confirmed_at`
- `superseded_at / invalidated_at`

每个 `account_id + scope_key + kind` 最多一个 ACTIVE 版本，并使用对应 Partial Unique Index；
`(strategy_id, version)` 唯一。Context Builder 只读 ACTIVE Confirmed Version；Pending、Expired、Stale、
Superseded、Invalidated 均不得进入决策 Context。
读取 `POSITION_PLAN_V1` 后，Application 必须与实时 Ledger 共同生成 `PositionFundingSnapshot`，不得从
历史 Assistant Message 或 Strategy payload 读取已投入 / 剩余金额。

### 7.3 Confirm / Replace / Invalidate

- Model Structured Output 只有在当前 User Message 明确表达跨会话长期意图，或明确请求起草持久计划时，
  才能提出 Candidate Draft；普通分析和实时 Recommendation 必须返回 `candidate = null`；
- Application Validator 必须拒绝包含 remaining budget、Ledger 派生值、tranche、price trigger、具体本轮
  buy amount 或其他 Recommendation 字段的 Candidate。验证成功后，Candidate 与展示它的 Assistant
  Message 在同一短事务提交；
- 确认只通过显式 Candidate UI / API，绑定已展示的 Candidate ID、candidate revision、base version 与
  idempotency key；Phase 4 不把固定肯定词直接当写入授权；
- Strategy Service 锁 Candidate 与同一 `account + scope_key + kind` 的当前 Active Version，重新验证
  Owner、status、expiry、scope、payload 与 base version；再把旧 ACTIVE 标记 SUPERSEDED，并插入新
  ACTIVE / INVALIDATED Version。不同冲突域不使用 Account-wide Lock，也不互相阻塞确认；
- 相同 idempotency key 的重复确认返回已生成 Version；候选过期、Thread 已删除或 active version 已改变
  返回 `409 STRATEGY_CONFLICT`，不得静默覆盖；
- 用户要求“删除”时创建 `INVALIDATE` Candidate，确认后写 INVALIDATED Version；不删除历史版本，
  也不影响 Portfolio / Lot Position Type；
- External page、Tool Result、Assistant Message 自身都不能创建持久意图依据或确认 Candidate；
- Candidate 被确认只表示用户意图跨会话生效，不确认当时 Recommendation，也不要求未来 Agent 重复
  相同买入金额、tranche 或价格条件。

### 7.4 Strategy API / UI

- `GET /v1/strategies?scope=`：返回当前 ACTIVE Confirmed Intent；
- `GET /v1/strategy-candidates/{candidate_id}`：读取当前 Account Candidate；
- `POST /v1/strategy-candidates/{candidate_id}/confirm`：提交 candidate revision、base version、
  `client_request_id`；
- `POST /v1/strategy-candidates/{candidate_id}/cancel`：取消未确认 Candidate。

Candidate 由 Agent Answer 流程根据 User Message 生成，不提供绕过“展示 → 确认”的任意 Payload
Public Create API。前端 Candidate Card 明确标为“持续投资意图”，展示 operation、scope、字段、来源与
影响，并提示它不是当前买入建议或订单；成功确认后更新 Strategy 状态，失败或冲突时重新读取，不乐观
声称已保存。用户要求持久化当前不支持的 trigger / tranche 时，保留 Conversation 并说明未保存，不生成
降级或近似 Candidate。

## 8. Research 与 Source / Citation Contract

### 8.1 Research Routing

现有 Alpaca Quote、Daily History、Recent News 与 SPY Market Context 继续作为首选结构化金融数据。
Open Research 只用于它们无法覆盖的开放网页发现、Filing / Earnings 原文、跨来源核验、宏观事件或
文章正文需求。

新增 Provider-neutral `ResearchGateway` / `ResearchRequest` / `ResearchResult`。Alibaba Native 是
当前首选 Production 候选，但批准 PydanticAI Runtime 不等于批准该 Research Provider。实施 Adapter
前必须独立 Review：当前 Production Model / Region / Endpoint 的真实能力、可绑定 Source Identity、
Query Privacy、Failure、Latency / Usage 与 Credential Boundary；通过后才作为只读
`research_public_sources` Tool 接入 Catalog。PydanticAI Runtime 不直接拥有 Provider。Brave 不加入
依赖或 Acceptance。

Research Decision Gate 尚未通过时，现有 Financial Data、Runtime、Conversation、Source Registry 与
Citation V2 可独立实施和验收；Open Research Tool 保持 disabled，相关 Case 保持 `DIAGNOSTIC` /
`NOT_MEASURED`。这不阻止 PydanticAI Cutover 或 Conversation 工作，也不得用更换 Runtime 固定模型来
补齐 Research 证据。Phase 4 Final Acceptance 前要么单独批准一个 Production Open Research Adapter，
要么由 Human 明确接受 Open Research 延后并相应修订 Final Scope。

Research Query 只允许公开 ticker、company、event、time window，不发送 Portfolio shares、cost、cash、
Strategy、Conversation 全文、Account / Session ID。Provider Answer / Excerpt 以
`UNTRUSTED_EXTERNAL_CONTENT` 注入，没有 Tool、Mutation 或 Confirmation 权限。Normal Empty、
Provider Failure、Budget Exhausted 与 Partial Result 必须分开。

初始 Safety Ceiling 延续 Phase 3：每 Run 最多 4 次 Model Request、4 次 Tool Call、2 次 Research、
30 秒 wall-clock。2026-09-24 Human Review 将 PydanticAI Production Native 的总时限和单次模型
请求时限调整为 60 秒，次数上限不变；这不是 Production SLO。4A 报告真实 Usage / UNKNOWN、
Latency 与费用后再决定是否收窄，不为达到速度跳过必要来源。

### 8.2 Source Registry 与 Citation

所有 Tool Observation 先进入 Application-owned Run Source Registry。Source Record 至少表达：

- server-generated `source_id`、source type、provider；
- URL / title / publisher（可得时）；
- published / event / fetched time（分别记录）；
- `STRUCTURED_FACT | TITLE_SUMMARY | PROVIDER_EXTRACT | FULL_TEXT` content scope；
- success / no-result / provider-failure / fetch-failure status。

只有本轮实际观察且成功的 Source ID 可引用。Final Answer 使用靠近相关陈述的
`[source:<source_id>]` Token；Application 同时校验声明 ID 和显式 URL，拒绝未观察、失败或跨 Run 来源。
摘要不得表述为全文，News 始终保持 attributed reporting。Metadata 缺失允许 `UNKNOWN`，但来源身份、
URL（开放网页）和读取范围不能伪造。

开放网页 Source 必须具有 Registry 验证过的 HTTPS URL；Quote、History、Market Context 等结构化金融
Source 可用 `source_id + provider_reference + observed/event time` 绑定，URL 允许为 `UNKNOWN`。若回答
显式输出 URL，该 URL 必须与对应 Registry Record 完全匹配；模型不得为结构化事实补造网页链接。

Assistant Message 与 Source Records 一起持久化，刷新后仍可展示。自动校验只证明 Citation 来自本轮
Registry；Citation 是否真正支持自然语言 Claim 继续由固定 Fixture 与 Human Grounding Eval 检查。

## 9. Long-term Memory Boundary

Phase 4 只新增 Application-owned：

- `MemoryReader.retrieve(account_id, retrieval_context) -> tuple[MemoryHit, ...]` Port；
- `MemoryHit` 的 owner、scope、content、source、effective / expiry metadata；
- `NoOpMemoryReader` 作为 Production Default；
- Context Builder 的独立 `retrieved_memories` 输入与 Fixture Tests。

Memory Result 必须在进入 Runtime 前完成 Account、scope、confirmed、未过期过滤，并标记为检索背景；
不得覆盖 Portfolio、Cash、Transaction、Confirmed Intent 或本轮用户指令。Phase 4 不新增 Memory 表、
写入 Tool、候选、API、UI、Embedding 或自动摘要。未来 Memory Service 只需实现 `MemoryReader`，无需
更换 PydanticAI Runtime 或 Conversation / Strategy Schema。

Current Recommendation 只随 Assistant Message 保存在 Conversation，用于审计和本 Thread 的有界上下文，
不自动成为 Long-term Memory。Future Decision Memory 如进入后续阶段，必须记录 as-of time、当时 Facts /
Sources 与非权威状态，只能帮助解释历史判断；它不得成为价格触发器、持续交易规则或跳过当前重新分析。

## 10. Task Decomposition 与执行顺序

### P4-T0 — Decision Record 与冻结 Contract

- 将已批准的 PydanticAI 选择记录为 ADR；同步 Discovery / ROADMAP 状态；
- 冻结 AgentRuntime、Context、Tool Result、Source、Answer V2 / Citation V2、旧 `/questions` 兼容、
  Conversation 与 Strategy Contract；
- 冻结四类状态的 Authority、`POSITION_PLAN_V1`、`PositionFundingSnapshot` 计算语义，以及
  Recommendation 不自动提升为 Candidate / Strategy / Memory 的边界；资金公式只使用当前 open cost
  basis，不使用累计 BUY、realized proceeds、Cash 或 Market Value；
- 从历史 Dataset `ask-quality-discovery/0.1` 派生 `0.2` Manifest：问题、Fixture 与 Rubric `0.1` 保持
  可追溯，只更新 Phase 4 已具备能力对应的 execution scope / sequential script metadata；保留全部
  `0.1` Artifact，不改写历史分母或结果；
- 冻结 4A / 4B Case Scope、Safety Ceiling 与 Critical Gate；AQ04 保持 `DIAGNOSTIC Regression`，除非
  独立 Research / Earnings Capability Review 后另行批准。

Dataset 0.2 的目标 Scope 固定如下；实际运行失败使用 `execution_status` 表达，不改写 Scope：

| Gate | Case | 目标 Scope |
|---|---|---|
| 4A Core | AQ03、AQ05～AQ12、AQ17a / b、AQ18、AQ20 | `FULL` |
| 4A Open Research | AQ01、AQ02、AQ19 | T4R 通过后为 `FULL`；T4R 延后时为 `DIAGNOSTIC / NOT_MEASURED`，不阻塞 Core |
| Earnings Regression | AQ04 | `DIAGNOSTIC`，除非另行批准 Earnings Capability |
| 4B Strategy | AQ13～AQ16 | T6 / T7 完成后为 `FULL` |

**验收：** 只记录已批准决策；Public API / Schema 示例经 Human Review；没有 Production 行为变更。

### P4-T1 — Application Boundary Extraction

- 从当前 `InvestmentAgent` 提取 ContextBuilder、Tool Executors、SourceValidator；
- 建立 AgentRuntime Port、ToolCatalog / Policy / Exposure Planner 与 MemoryReader Port；
- 在 ContextBuilder 中加入 Ledger-owned `PositionFundingSnapshot`，并保持 Cash、本轮 Budget、目标预算、
  当前成本与剩余目标预算为不同字段；
- 用 Characterization Tests 保持现有 `/questions`、Portfolio、Tool Failure、Source 与 AQ06 行为。

**验收：** Current Runtime 输出 Contract 与现有定向测试不变；Ledger / Calculation 无修改。

### P4-T2 — PydanticAI Production Adapter

- 加入锁定的 Production Dependency，并让 Provider Builder 读取现有 Production Model / Provider
  Configuration，不在迁移中更换默认模型；
- 实现 history、dynamic toolset、structured output、usage / latency、budget、failure mapping；
- 用 Current Fixture、Phase 3 Live Smoke 与 Provider Failure 测试做等价回归；
- 在用户本地对运行时实际解析出的 Production Model / Provider / Endpoint 执行最小 No-tool、One-tool、
  Multi-tool Live Smoke；Phase 3 的 `qwen3.7-max` 结果只作参考，不能替代该 Gate；
- 让旧 `/questions` 经 PydanticAI 形成兼容 Response，Legacy Runtime 退出 Bootstrap。

**验收：** No-tool / One-tool / Multi-tool、Usage UNKNOWN、Source Failure、AQ06、异常路径通过；
Production 只装配一个 Runtime。

**完成证据（2026-09-22）：** 离线 Adapter / Agent / 回归测试与独立 Automated Review 通过。用户在
部署时实际解析的 `qwen3.7-max`、`ALIYUN_MODEL_STUDIO` 与当前 Endpoint 上运行 Production Smoke：
No-tool、One-tool、Multi-tool 均通过，Tool Arguments 均为预期 `GOOG`；三次延迟约为 3.75s、3.59s、
5.84s。Provider 未报告 Token Usage，按 Contract 明确记录为 `UNKNOWN / USAGE_NOT_REPORTED`，不伪造
Token 或 Cost。结果关闭 P4-T2 Compatibility Gate，不形成模型质量或性能横向结论。

### P4-T3 — Conversation Persistence 与 API

- Alembic 0010 新增 Thread / Turn / Message / Source；
- 新增独立 Repository / UoW / Service 与 FastAPI Router，避免继续扩大现有 `models.py`、
  `unit_of_work.py` 和 `main.py`；
- 实现 Owner、revision、idempotency、bounded history、soft delete 与分页；
- 完成 PostgreSQL Integration 与 API Contract Tests。

**验收：** A / B Account 隔离；并发追加只有合法请求成功；失败无假 Assistant；Migration upgrade /
downgrade 在空测试库通过，已有 Ledger 数据不变。

**完成记录（2026-09-23）：** Alembic 0010、独立 Conversation UoW / Service、Session-owned API 与有界
History 已落地。此前已验证含 Ledger sentinel 的 upgrade / downgrade / upgrade 往返；修订后的 Schema
再次 upgrade 成功。定向 Unit / API 36 passed，PostgreSQL Integration 2 passed；Ruff / mypy 通过。
已完成 Automated Review，并补齐幂等重试的持久 warnings 与 `TURN_IN_PROGRESS` 原 `turn_id`。
Source / Citation 的完整校验与前端恢复属于 P4-T4A。

### P4-T4A — Conversation Frontend + Financial Data / Citation

- 前端切换 Thread API、恢复、列表、删除、失败与安全 Citation；
- 现有 Financial Data Tool 经 Catalog 接入；
- 实现 ResearchGateway Port、Source Registry、Answer V2 与 inline Citation；
- 新增 Fake Research、Prompt Injection、No Result / Failure / Partial Result 测试。

**验收：** Conversation 与现有 Financial Data 场景取得完整执行能力；未观察来源与外部指令被拒绝；
不需要 Brave Key，Open Research Provider 尚未批准也不阻塞本 Task。

**完成记录（2026-09-23）：** 前端已切换 Thread API，支持列表、分页恢复、切换、删除、冲突刷新与
Account 切换隔离；现有 Financial Data Tool 保持经 Catalog 暴露。Conversation Answer 绑定本轮
Tool Observation 的 Source ID，News 以实际文章 URL / Metadata 建立来源，inline Citation 在写入前
验证，未观察或重复 Source ID、虚构 URL 拒绝；旧 T3 已存回答只作为 `CITATION_NOT_VERIFIED` 恢复。
ResearchGateway 只实现 Provider-neutral Port 与 Fake Security / Failure 测试，未接真实开放搜索、网页
读取或模型 Research Tool；T4R 仍为独立 `DEFERRED / NOT_MEASURED`。定向 Backend 147 passed、
PostgreSQL Integration 2 passed，Frontend Conversation / Refresh / Chart 检查、Ruff / mypy 与
Automated Review 通过；真实 Browser / 质量 Eval 属 T5。

### P4-T4R — 独立 Research Decision / Adapter（不阻塞 Runtime Migration）

- 以 Alibaba Native 为首选候选，复核用户已执行的 Live Evidence 与当前 Production Model / Region /
  Endpoint 的适用性；缺失证据只补 Provider 选型所需的最小 Smoke，不换 Runtime 固定模型；
- 提交独立 Research Decision Proposal；仅在 Human Approval 后实现 Adapter、query privacy、Source /
  Citation Mapping 与必要 Live Smoke；
- 若未获批准，Open Research Tool 保持 disabled，Brave 继续 `NOT_MEASURED`，不临时新增 Provider。

**验收：** Provider 选择与 Runtime 选择分别归因；Source Identity 可绑定，失败与 Usage / Latency
可观察，外部内容无 Mutation 权限；或明确记录 DEFERRED，且不阻塞 T2 / T3 / T4A。

### P4-T5 — 4A Fixed Eval / Human Checkpoint

- 运行 Dataset 0.2 的 4A Cases、Protected Set、Repeat、PostgreSQL Integration、Browser Smoke；
- 记录能力覆盖、质量分布、请求成功、Critical Failure、Latency / Usage / Cost；
- Core Runtime / Conversation 与 Open Research 分栏报告；Research Gate 未通过时，相关 Case 明确保持
  `DIAGNOSTIC / NOT_MEASURED`，不阻塞 PydanticAI / Conversation 技术验收，但不能声称 Research 完成；
- Automated Review 修复后重跑受影响测试。

**验收：** Core Gate 满足第 11 节要求。形成 4A Report 并暂停等待 Human Review；Human 根据独立
Research 栏决定先进入 4B、等待 T4R，或明确延后 Open Research。

### P4-T6 — Strategy Persistence / Service / API

- Alembic 0011 新增 Candidate / Confirmed Version；
- 实现 `POSITION_PLAN_V1` / Thesis / Horizon typed payload validator、禁止 Recommendation / Ledger
  Derived Field、每个 `account + scope_key + kind` 唯一 Pending、显式 replacement / cancel、24h expiry、
  confirm / invalidate、version conflict、row lock 与 idempotency；
- ContextBuilder 只注入 Active Confirmed Intent，并每轮重新计算 PositionFundingSnapshot；
- 实现 Candidate Card 与显式确认 UI。

**验收：** Candidate 不自动生效；同一冲突域并发创建最多一个 Pending，不同冲突域可并行创建；并发
确认只有一个有效版本；旧版本 / stale / deleted Thread Candidate 不进入 Context；Intent 写入不触碰
Ledger，也不保存当前 Recommendation 或 Derived Facts。

### P4-T7 — 4B 连续 Ask + Memory Seam

- 接入 NoOp MemoryReader 与 Fixture Retrieval；
- 完成 AQ13～AQ16、跨 Session Strategy 读取、替代 / 失效和完整连续 Ask 脚本；
- 验证 BUY / SELL 后 open cost basis 与 remaining target budget 变化；SELL 会释放当前资本配置空间，
  realized proceeds / Cash / Market Value 不进入公式；市场或 Research 变化后 Recommendation 可改变，
  历史 buy amount / price trigger 不会自动复用；
- 保持 4A 的模型、Research Provider 状态、Prompt 基线与 Market Fixtures，记录仅由 Strategy 带来的
  变化；如 4A Research 为 DEFERRED，4B 不借机启用新 Provider。

**验收：** 未确认建议不提升；确认的 Position Plan 跨 Session 生效但不冻结 Recommendation；交易后
派生金额重新计算；失效 Intent 不复活；Memory Fixture 不能覆盖业务事实；无需 Memory Database。

### P4-T8 — Cutover、Rollback 与 Final Acceptance

- 运行完整 Dataset、相关 Unit / Integration / Browser / Live Checks；
- 演练 Application Artifact 回滚与 additive Schema forward recovery；
- 删除 Legacy Runtime Production Loop 与临时兼容代码；旧 `/questions` 在 Phase 4 保持 deprecated
  compatibility，未来移除需单独处理 Public API 变更；
- 更新 ADR、ARCHITECTURE、ROADMAP、Eval Report 与 Release Mapping；
- 完成 Human Acceptance 后才合并 `main`。

**验收：** 第 11 节全部 Done Criteria；没有长期 Runtime 开关或双轨装配。

## 11. Test、Eval 与 Human Acceptance

### 11.1 Automated Test Matrix

- Runtime：0 / 1 / multi Tool、history mapping、structured answer、usage unknown、limits、provider failure；
- Tool：duplicate / disabled / unauthorized、argument validation、read vs mutation、dynamic exposure；
- Conversation：Owner、sequence、pagination、revision conflict、idempotency、failure turn、soft delete；
- Strategy：pending exclusion、confirm、repeat confirm、expiry、base-version conflict、concurrent confirm、
  replace / cancel / invalidate、cross-session read、Position Plan payload allowlist；同一 Account 的不同
  scope / kind 可同时 Pending；同一冲突域并发创建只有一个成功，另一请求稳定 Conflict；不同冲突域
  并发创建均成功；同一 `scope_key + kind` 的后续 Candidate 必须显式 replace 或 conflict；
- State Authority：target budget 持久化；Quantity / Average Cost / open cost basis / remaining target budget
  从 Ledger 动态计算；SELL 降低 open cost basis 并释放 remaining target budget；累计 BUY、realized
  proceeds、Cash、Market Value / 本轮 Budget 不混入公式；Recommendation 不生成持久 trigger / tranche；
- Research：query privacy、source mapping、empty / failure / partial、prompt injection、budget；
- Citation：unobserved / failed / cross-run ID、invented URL、summary vs full-text scope；
- Memory Seam：wrong owner / scope / expired hit exclusion，不能覆盖 Ledger / Intent，也不能把历史
  Recommendation 提升为当前指令；
- Regression：Portfolio、Cash、Transaction、Position Type、AQ06 金额边界、旧 API compatibility；
- PostgreSQL：0010 / 0011 upgrade、empty-db downgrade、既有 Schema upgrade、constraint / row-lock；
- Frontend：Thread restore / switch / delete、logout clear、conflict、Candidate Card、XSS-safe Citation。

### 11.2 Fixed Eval Gates

不修改 Phase 1～3 历史结果；新增 Dataset / Report Version。

**4A Core Gate：** 沿用已批准 Phase 2 Decision Proposal §9.1 的逐 Case 最低分、Repeat 与 Critical
Gate，不用新平均分覆盖失败。Conversation、Runtime、现有 Financial Data 对应的已启用 Case 必须达到
目标 Scope；固定 Fixture Primary Run 全部完成，Critical Failure 为 0。AQ04 保持
`DIAGNOSTIC Regression`，最低分不低于 `1/1/2/2/2/1`，不得假装取得 Earnings Evidence。Protected
AQ12、AQ18 必须通过 Core Gate；AQ19 仅在 Research Gate 启用后作为阻塞性 Gate，延后时保留
Diagnostic Security Evidence。

**4A Research Gate：** 只有 T4R 获得独立批准并完成真实 Adapter 后，AQ01、AQ02、AQ19 等开放研究
能力才能按 Dataset 0.2 Manifest 提升为 `FULL`；Research Sufficiency 与 Evidence / Inference 达到
Phase 2 冻结目标，Critical Failure 为 0。未批准时保持 `DIAGNOSTIC / NOT_MEASURED`，不解释为 Runtime
失败，也不阻止 Core Runtime / Conversation Human Checkpoint。

**4B Gate：** AQ13～AQ16 转为 `FULL`，并达到 Dataset 0.2 Manifest 对已启用能力定义的目标覆盖；
State Authority 目标维度必须为 2；Candidate 未确认、旧版本复活、跨 Owner 或 Ledger Mutation 任一
出现即失败。将实时 Recommendation、Ledger Derived Field、price trigger 或 tranche 持久化为 Active
Intent，在新事实下机械复用旧 Recommendation，错误阻止不同 scope / kind 同时 Pending，允许同一冲突
域出现两个 Pending，或使用累计 BUY / realized proceeds / Cash / Market Value 计算 remaining target budget，
同样是 Critical Failure。AQ12 与 AQ15 各重复三次，Critical Failure 必须为 0。AQ04 或 Human 明确延后
的 Research Case 不得为了制造“20 / 20”而伪装成 `FULL`；只有各独立 Capability Gate 均通过时才能
声明全覆盖。

既有 AQ03、AQ05、AQ07、AQ17a / b 重复集继续三次；不得只报告最好结果。Safety Ceiling 为硬边界，
Usage 不可得可记录 `UNKNOWN`，不得伪造成 0。正式报告展示 Coverage、完整场景 Rubric 分布、Request
Success、Critical Failure、median / max Latency 与费用可得性，不以单一平均分掩盖失败。

### 11.3 Human Acceptance Script

1. 登录 → 创建 Thread → 连续讨论 GOOG → 切到 MSFT → 回到 GOOG；
2. 本轮 Budget 500 更正为 200，刷新 / 重新登录后恢复正确上下文且不修改 Cash；
3. 需要时调用 Financial Data；若 T4R 已批准，再调用获批 Open Research，来源可打开、读取范围真实、
   无虚构 Citation；
4. 用户确认 GOOG / LONG_TERM `target_budget = 300 USD`；跨 Session 保留该 Intent，但不改写 Cash；
5. 通过现有 Transaction 路径记录真实交易后，Quantity、Average Cost、open cost basis 与 remaining target
   budget 从 Ledger 重新计算；再记录 SELL，确认 open cost basis 降低并重新释放 target budget 空间，
   realized proceeds、Cash 与 Market Value 不进入公式；
6. 同一 Account 可同时保留 GOOG / LONG_TERM Position Plan、MSFT / LONG_TERM Position Plan，以及
   GOOG / LONG_TERM Thesis Candidate；第二个 GOOG / LONG_TERM Position Plan 必须显式 replace / cancel
   旧 Candidate，否则返回稳定 Conflict；
7. “当前先买 80 美元”“跌到 320 再加仓”只留在 Conversation，不生成 Candidate；价格再次到达 320
   时结合新 Portfolio、Market、Research 与 Tool 重新建议；
8. Thesis / Horizon 可以影响说明，但新证据允许给出不同建议；Replace / Invalidate 后旧 Intent 不复活；
9. Account B 不能读取 Account A Thread、Source、Candidate 或 Strategy；
10. 删除 Thread 后 UI 与 Context 不再读取；Confirmed Intent 不因删除 Conversation 自动消失；
11. Provider Failure、No Result、Thread Conflict、Strategy Conflict 均显示可理解状态，不伪造 Answer；
12. Rollback 演练不删除 Conversation / Strategy / Ledger 数据。

## 12. Migration、Deployment 与 Rollback

- 使用 Expand → Switch → Retire；0010 / 0011 只新增表、索引与约束，不改写 Ledger；
- Migration 前备份；在空库、当前 Head 副本和已有数据 Fixture 上验证；
- 不在等待 LLM 时持有数据库锁；所有外部调用结束后用短事务提交；
- PydanticAI Cutover 使用单一 Application Artifact，不做请求级双跑；
- Hard Rollback 触发条件：Owner 越权、Ledger / Cash 改写、未确认 Strategy 生效、虚构来源通过、
  Recommendation / Ledger Derived Field 被持久化为 Active Intent、Migration 数据损坏或持续 Provider
  Contract Failure；
- 触发时回退到 Phase 4 前 Artifact / Frontend，保留新增表和已写数据，不执行破坏性 Production
  Downgrade；用 forward fix 恢复；
- 4A / 4B 未通过前不删除 Legacy 代码；Final Acceptance 后删除生产装配与临时分支，测试 Artifact
  继续保留历史基线。

## 13. Done Criteria

- PydanticAI 是唯一 Production Agent Runtime；Current Runtime 已退出生产代码路径；
- Portfolio / Ledger、Strategy、Conversation、Memory、Tool Authorization、Source Registry 的 Owner
  边界符合批准架构；
- Tool Catalog 支持注册、启用 / 禁用、授权与 per-run exposure，且没有插件市场 / Skills Framework；
- Thread / Turn / Message / Source Schema、Migration、API、Frontend 恢复、Owner 与并发边界完成；
- Persistent User Intent Candidate / Confirmed Version 的确认、版本、过期、替代、失效、幂等和并发完成；
  Pending 唯一性限定为 `account + scope_key + kind`，不同冲突域可并存；
- `POSITION_PLAN_V1` 只保存目标预算等稳定意图；投入、剩余预算、Quantity 与 Average Cost 每轮由
  Ledger 动态计算，SELL 可通过降低 open cost basis 释放 target budget 空间；公式不使用累计 BUY、
  realized proceeds、Cash 或 Market Value，实时 Recommendation 不被持久化为长期 Strategy；
- 现有 Financial Data 正式接入；Open Research 经独立 Decision Gate 批准后才接入，或由 Human 明确
  接受延期；Brave 不成为依赖；
- Source Registry 与 near-claim Citation 拒绝虚构、失败和跨 Run 来源；
- Long-term Memory 只有只读 Retrieval Seam，Production 默认不持久化 Memory；
- 4A Core、4B Automated / Eval / PostgreSQL / Browser / Live Evidence 达标，Critical Failure 为 0；
  Open Research 只按独立 Gate 的批准 / 延后状态报告；
- Rollback 演练、Automated Review 与 Human Acceptance 完成；
- 没有 Multi-Agent、RAG、Vector DB、完整 Memory、Skills Marketplace、投资复盘或自动交易；
- 更新 ADR / ARCHITECTURE / ROADMAP / Evaluation Report；Human Acceptance 后才合并本地 `main`。

## 14. Human Review Gate

批准本计划即批准在上述边界内新增 Conversation / Strategy Production Schema、Public API 与
PydanticAI Runtime；不自动批准 Alibaba Native 或其他 Production Research Provider。以下变化仍须
重新暂停并提交 Decision Proposal：

- 改用其他 Framework、Model、Research Provider 或 Database / Queue / Vector Store；
- 将 Framework Session / Memory 作为业务事实源；
- 扩大 Strategy Kind、改变 Thread 删除 / Retention 或开放任意 Mutation Tool；
- 将 tranche、价格触发条件、具体买入金额或其他 Current Recommendation 提升为 Persistent Intent；
- 引入远程 MCP、用户代码 / Skills、Streaming / Durable Run 或 Multi-Agent；
- 放宽 Owner、Source、Citation、Confirmation、Budget 或 Ledger Boundary；
- 修改本计划已冻结的 Public API、并发语义或 Critical Failure Gate。

计划批准后按 P4-T0 → T1 → T2 → T3 → T4A → T5 Core 顺序执行；T4R 作为独立 Research Gate，
不阻塞 T2 / T3 / T4A。在 4A Report 后暂停 Human Review，由 Human 决定是否进入 T6 → T8 及
Research 是否继续。
