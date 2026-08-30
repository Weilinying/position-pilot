# M8 — Local Portfolio Management 执行计划

## 1. 状态与目标

**Status:** AUTHENTICATION REVISION APPROVED — Implementation In Progress (2026-08-30)

M8 将当前“需要 Demo Seed 或已知 UUID 才能使用”的 M7 Interface，扩展为本地用户可从零开始并持续维护的 Self-Service MVP。M8 完成并通过 Human Acceptance 后形成 `v1.0.0`。

核心闭环：

```text
Public Home
        ↓
Register / Login Local Account
        ↓
Create Local Portfolio + Current Available Cash
        ↓
Optional Immutable Opening State
        ↓
Initialization Sealed
        ↓
Append BUY / SELL / DEPOSIT / WITHDRAWAL
        ↓
Deterministic Replay
        ↓
Current Snapshot + Read-only Records
        ↓
Independent Investment Questions
        ↓
Real Agent Grounded Answer + Collapsed Sources / Failure State
```

M8 实现最小 Email / Password Authentication，唯一目的是让非开发者本地用户从首次进入完成全部现有后端能力与真实 Agent 闭环。它不是完整 Account Platform：不包含 Email Verification、Password Reset、OAuth、MFA、Role / Permission、Organization、Cloud Account 或 Multiple Portfolio。

## 2. 开始条件与当前基线

- M7 Production、Test 与 Documentation 已提交在 `codex/m7-minimal-product-interface`，但计划状态仍是 `IMPLEMENTED — Awaiting Human Acceptance`；M8 Production 实现必须等 M7 明确 Human Accepted 并合并到本地 `main` 后，从 `main` 创建 `codex/m8-local-portfolio-management`。
- 已批准的 Release Roadmap 与本计划属于独立 Planning Change，不计作 M7 功能范围；它们可以随已批准文档进入 `main`，但不能替代 M7 Human Acceptance。
- `PortfolioService.create_user()` 已原子创建带 `initial_cash` 的 User；当前没有 Public API。
- `PortfolioService.record_transaction()` 已负责 User Row Lock、Ticker / Decimal / Position Type 校验、金额与 IBKR Fee 派生、历史补录重排、Cash / Oversell Validation 和 Transaction Commit；当前没有 Public API。
- `POST /v1/portfolios/{user_id}/cash-events` 已支持 DEPOSIT / WITHDRAWAL，不重复实现。
- `GET /v1/portfolios/{user_id}` 已返回完整当前 Snapshot；前端写入成功后继续通过该 Endpoint 重读，不在浏览器计算 Cash、Average Cost、Cost Basis 或 Position。
- M7 已建立 Request Generation、Source Grounding、安全 DOM Text Rendering 与中英切换；M8 必须保留这些正确性边界，但 `loadedUserId` 只能来自 Server Session 对应的 Portfolio，不再信任 URL 或表单身份。
- 当前页面使用 URL / local pointer 恢复 UUID，并把 Browser Smoke Fake Agent 作为可见 Demo；这不足以形成真实产品闭环。正式 Human Acceptance 必须使用 `position_pilot.main:app` 与真实 Investment Agent，Fake Agent 只保留为工程测试替身。
- Transaction 目前未像 Cash Event 一样拒绝 future `occurred_at`。开放 UI 写入前必须统一“已经发生的 Ledger Fact”语义。
- Opening State 与 `UNSPECIFIED` 的 Alembic Migration 已实现。本次已批准 Authentication Revision 允许新增最小 `accounts` / `auth_sessions` 持久化表，但不新增 Database、Cache、Queue、Frontend Toolchain 或 Account Platform Infrastructure。

## 3. Human Decision Proposal

原 M8 D1 的 no-auth local pointer 决策已被 2026-08-30 Human Decision 明确替代。D2～D6 的 Ledger、Opening State、时间与写入正确性保持不变；本次批准只增加完成 `v1.0.0` 首次使用闭环所必需的最小 Authentication、Account→Portfolio Ownership 和产品主页。

### D1 — 最小本地 Account、Session 与 Portfolio Ownership（已批准修订）

**决策：使用 Email / Password 建立本地 Account；由 HttpOnly Session Cookie 恢复身份，Server 从 Session 决定唯一 Portfolio User。**

- 首次访问 `/app/` 显示 Public Home，只提供产品说明、Create Account 与 Log In；未认证时不得请求或展示 Portfolio / Agent 数据。
- Account 使用规范化且唯一的 Email 作为本地登录标识；Password 只保存标准密码哈希，禁止明文持久化、日志记录或返回 Browser。
- Register / Login 成功后产生高熵随机 Session Token；Browser 只持有 `HttpOnly + SameSite=Lax + Path=/` Cookie，Database 只保存 Token Digest 与过期时间。Login 必须轮换 Session；Logout 删除当前 Session。
- `accounts` 与现有 `User → Portfolio State` 为一对一关系。Account 可以先注册、后初始化 Portfolio；Portfolio 创建后不可再为同一 Account 创建第二个 Portfolio。
- Portfolio Setup 一次性创建现有 User / Initial Cash，并可在同一事务中写入可选 Opening Positions。用户可注册后立即完成，也可退出并在下次登录后继续。
- 所有 Portfolio / Ledger / Investment API 必须从有效 Session 取得 Account 与 Portfolio User；路径或 Body 中的 `user_id` 不是授权来源。正常 UI 不显示、输入或用 URL / `localStorage` 恢复 UUID。
- `localStorage` 不保存 Email、Password、Session Token、Account、Snapshot、Ledger、Question、Answer、Provider Data 或 Secret。
- Session 仅适用于 loopback HTTP 的本地产品；M8 不宣称具备公网 Account Security，不增加 Email Verification、Password Reset、OAuth、MFA、Rate-limit Infrastructure、Organization、Role / Permission 或多个 Portfolio。

**理由：** `v1.0.0` Acceptance 已明确要求非开发者能从首次进入完成真实 Agent 闭环。最小 Session Authentication 消除 UUID 作为用户身份的开发者体验，同时把 Account Platform 的其余生命周期留在 V2。

### D2 — 最小 Public Write API Contract

**修订：正常产品 API 使用 Session-derived Identity；现有 PortfolioService 与 Ledger Domain 行为不变。**

认证入口：

- `POST /v1/auth/register`：`email + password + display_name`，创建尚未初始化 Portfolio 的 Account 并设置 Session Cookie；
- `POST /v1/auth/login`：验证 Email / Password、轮换 Session 并设置 Cookie；
- `POST /v1/auth/logout`：幂等删除当前 Session 并清除 Cookie；
- `GET /v1/auth/session`：返回当前 Account 与 `portfolio_ready`，不返回 Password Hash、Session Token 或内部 User ID。

#### `POST /v1/portfolio`

Request：

```json
{
  "initial_cash": "10000",
  "opening_positions": [
    {
      "ticker": "GOOG",
      "shares": "2",
      "average_cost": "180.25"
    }
  ]
}
```

Response `201`：

```json
{
  "available_cash": "10000.00000000",
  "positions_are_complete": true,
  "positions": [
    {
      "ticker": "GOOG",
      "shares": "2.00000000",
      "average_cost": "180.25000000",
      "cost_basis": "360.50000000",
      "position_type": "UNSPECIFIED"
    }
  ]
}
```

- Account 尚无 Portfolio 时才允许调用；同一 Account 第二次创建返回 `409 / PORTFOLIO_ALREADY_EXISTS`。
- `initial_cash` 为 `0` 以上、最多 8 位小数的 Decimal；`opening_positions` 可省略或为 0～100 行，并复用 D5～D6 的 Domain Validation。
- User、可选 Opening Positions 与 Account Ownership 必须在同一 Database Transaction 中提交；任一非法输入不得留下半成品 Portfolio。
- 创建成功后前端仍立即 GET 当前 Snapshot 与 Records，不在 Browser 推导 Financial State。
- 不接受客户端指定 `user_id`、Account ID、`created_at` 或其他 Ledger 字段。

#### `POST /v1/portfolio/transactions`

Request：

```json
{
  "ticker": "GOOG",
  "action": "BUY",
  "price": "180.25",
  "shares": "2",
  "reason": "Manual local trade"
}
```

`occurred_at` 与 `reason` 可省略；以上默认请求不发送 `occurred_at`，由 Application Clock 产生当前实际发生时间。只有历史补录才显式发送 offset-aware ISO timestamp。Response `201`：

```json
{
  "transaction": {
    "id": "00000000-0000-0000-0000-000000000002",
    "user_id": "00000000-0000-0000-0000-000000000001",
    "sequence": 1,
    "ticker": "GOOG",
    "action": "BUY",
    "price": "180.25000000",
    "shares": "2.00000000",
    "amount": "360.50000000",
    "commission": "0.35000000",
    "fee_schedule": "IBKR_PRO_TIERED_US_2026_08",
    "position_type": "UNSPECIFIED",
    "occurred_at": "2026-08-30T08:00:00Z",
    "reason": "Manual local trade"
  }
}
```

- `position_type` 可省略或为 `null`；Backend 将其规范化为显式 `UNSPECIFIED`。客户端也可明确发送 `LONG_TERM`、`SWING` 或 `UNSPECIFIED`，Response 始终返回非空的规范值。
- 客户端不能提交 `amount`、`commission`、`fee_schedule`、`sequence` 或 Transaction ID。
- `401 / AUTHENTICATION_REQUIRED`、`409 / INSUFFICIENT_CASH`、`409 / INSUFFICIENT_SHARES`、`422 / INVALID_TRANSACTION` 保持可区分。
- Pydantic Request Validation 失败仍为 422；前端安全展示字段级或通用输入提示，不展示内部堆栈。
- 不新增 Update / Delete / 未确认 Import API；D6 只补充只读 Transaction / Cash Event List，不提供 History Editor。

同理，正常产品 Flow 使用 `GET /v1/portfolio`、`POST /v1/portfolio/opening-positions`、`GET /v1/portfolio/{opening-positions|transactions|cash-events}` 与 `POST /v1/portfolio/cash-events`。`POST /v1/investment/questions` 只接收 `question`，User Identity 由 Session 注入。原 UUID Routes 不得作为未认证绕过入口；若为兼容工程测试暂时保留，必须要求同一 Session Ownership，正常 UI 不调用。

M8 API 中的“Portfolio”仍是现有 `User → Portfolio State` 模型的产品与 Resource 呈现，不新增 Multiple Portfolio Aggregate，也不为 REST 命名重构 Ledger Domain。Account 只是其一对一 Owner；Multiple Portfolios 的 Resource Boundary 留到 V2 重新评估。

### D3 — Ledger 实际发生时间

**建议：Transaction 与 Cash Event 使用同一默认时间语义，只允许已经发生的 Ledger Fact。**

- UI 的 `occurred_at` 默认留空；空值不进入 JSON Payload，Browser Clock 不作为默认 Ledger 时间 Source of Truth。
- Transaction 与 Cash Event 的 Public Request 均允许省略 `occurred_at`；省略时由对应 Application Service 的可注入 Clock 产生当前 UTC 时间。Cash Event 继续复用现有 Endpoint，只对其时间字段作这一最小兼容扩展。
- `PortfolioService.record_transaction()` 省略时间时使用 Application Clock，而不是在 Domain 内另取系统时间；Backend Application Clock 是“Now”的唯一默认。
- 明确时间先规范化到 UTC；future timestamp 在读取完整 Ledger 或写数据库前返回 `InvalidPortfolioValue`。
- 只有用户主动输入历史时间时，浏览器才将 local datetime 按本地时区解释并转换为 offset-aware ISO timestamp；naive timestamp 不得进入 Public API Contract。
- 历史补录保留当前 resequence 与完整 replay validation。
- Scheduled Order / Future Trade 不属于 Transaction，留到未来独立建模。

### D4 — Mutation UI Correctness

**建议：有副作用的 POST 通过禁止并发 Auth Transition 保持简单；所有 Portfolio Mutation 只绑定当前 Session Owner，写后重读，绝不 Optimistic Update。**

- Portfolio 未加载、已 stale 或正在切换身份时，BUY / SELL / DEPOSIT / WITHDRAWAL 全部禁用。
- Mutation 使用以下顺序，不增加 Write Generation：

```text
Mutation 开始
→ 捕获当前 Session-bound Portfolio Context
→ 禁止 Logout / Portfolio Setup / Auth Transition
→ 禁止同一表单重复提交
→ POST Mutation
→ 成功后 GET 最新 Snapshot
→ 失败或结果不确定时将当前 Snapshot 标记 stale / refresh_required
→ Mutation 结束后恢复 Identity 操作
```

- Read Request 继续通过 `portfolioGeneration` / `questionGeneration` 处理 stale response；Logout / Session expiry 会使当前 Context 失效并清空敏感 DOM。
- POST 是有副作用请求，浏览器 Abort 不能被当作“服务端未写入”的保证；不自动 Retry。
- Transaction / Cash Event POST timeout 或 connection lost 时，显示“写入结果未知”，使 Snapshot stale，并要求 Reload。Reload 重新取得当前 deterministic Portfolio State 与只读 Records，供用户检查最新状态；M8 不保证由此证明某一次不确定 POST 是否执行或恰好执行一次。
- 成功 Response 不直接修改 Cash / Position；立即 GET 最新 Snapshot。若 GET 失败，明确显示“写入成功、刷新失败”，并保持 Context stale。
- M8 提供 D6 定义的只读 Transaction / Cash Event / Opening Position List，供用户查看 immutable records；这些 List 不构成 Idempotency、Mutation Reconciliation 或 Exactly-once Verification 机制。
- M8 不增加 Idempotency Key、Mutation ID Lookup、Mutation Reconciliation、自动 Retry 或 Transaction Editor；确有需求时再单独设计。
- 所有 API、User Input 和动态错误文本继续通过安全 DOM Text API 渲染。

**Registration / Portfolio Setup Network Ambiguity**

Auth 或 Portfolio Setup POST 的连接可能在 Server Commit 后丢失。Browser 不自动重试：Register 结果未知时提示用户使用相同 Email 尝试 Login；Portfolio Setup 结果未知时重新读取 Auth Session 的 `portfolio_ready` 与当前 Snapshot。M8 仍不增加 Idempotency Key 或通用 Mutation Reconciliation；确定性的 Account / Portfolio Ownership 只能恢复当前状态，不证明任意 Ledger POST 恰好执行一次。

### D5 — Optional Position Type

**建议：仓位类型在用户输入与 Public Request 中为可选；未提供时保存为明确的 `UNSPECIFIED`，不得猜测为 `LONG_TERM` 或 `SWING`。**

- `PositionType` 增加第三个规范值 `UNSPECIFIED`；它表示用户尚未分类，不表示系统推断出的投资意图。
- Opening Position 与 BUY / SELL Request 均允许省略 `position_type` 或发送 `null`；Application / Domain Boundary 立即规范化为 `UNSPECIFIED`，持久化事实与 Response 不保存含糊的 `null`。
- `(ticker, LONG_TERM)`、`(ticker, SWING)` 与 `(ticker, UNSPECIFIED)` 是三个完全独立的 Position Key；同一 ticker 可以同时存在三类仓位。
- SELL 只能减少 Request 指定或缺省归一后的同类仓位；省略类型的 SELL 只作用于 `UNSPECIFIED`，不会自动跨仓位类型匹配 Shares。
- Agent Context 必须把 `UNSPECIFIED` 表述为未知策略分类，不得自行推断 LONG_TERM / SWING。
- M8 复用 M6 Behavioral Eval Harness 覆盖三类仓位共存、SWING-specific 问题、总持仓确定性聚合与 `UNSPECIFIED` 解释，具体 Cases 见 §7.1。
- M8 不增加 Position Type Reclassification、历史 Ledger Edit 或跨类型 Transfer。需要重新分类时，未来应设计显式、可追溯的 Reclassification Ledger Event，而不是改写历史。

这会把原有“LONG_TERM / SWING 独立”的 invariant 扩展为“所有明确分类独立，未分类同样是独立 Structured State”，不会削弱既有两类仓位的隔离。

### D6 — Existing Positions、Opening State 与只读记录

**建议：新增一次性、批量且原子化的 immutable Opening State；同时公开现有 Transaction / Cash Event 查询能力，只用于只读记录展示。**

领域关系统一为：

```text
Opening State = User.initial_cash + optional OpeningPosition[]

Portfolio State
=
Opening State
+ Replay(Cash Events + Transactions)
```

`OpeningPosition` 可以是 immutable Domain Entity / Table，但它是系统开始跟踪时的 Starting Fact，不是与 Transaction / Cash Event 等价的经济 Ledger Event。

#### `POST /v1/portfolio/opening-positions`

Request：

```json
{
  "positions": [
    {
      "ticker": "GOOG",
      "shares": "12",
      "average_cost": "165.50"
    },
    {
      "ticker": "MSFT",
      "shares": "5",
      "average_cost": "410.00",
      "position_type": "LONG_TERM"
    }
  ]
}
```

Response `201`：

```json
{
  "opening_positions": [
    {
      "id": "00000000-0000-0000-0000-000000000010",
      "user_id": "00000000-0000-0000-0000-000000000001",
      "ticker": "GOOG",
      "shares": "12.00000000",
      "average_cost": "165.50000000",
      "cost_basis": "1986.00000000",
      "position_type": "UNSPECIFIED",
      "recorded_at": "2026-08-30T08:00:00Z"
    },
    {
      "id": "00000000-0000-0000-0000-000000000011",
      "user_id": "00000000-0000-0000-0000-000000000001",
      "ticker": "MSFT",
      "shares": "5.00000000",
      "average_cost": "410.00000000",
      "cost_basis": "2050.00000000",
      "position_type": "LONG_TERM",
      "recorded_at": "2026-08-30T08:00:00Z"
    }
  ],
  "items_are_complete": true
}
```

- `positions` 为 1～100 行；同一 Batch 内不允许重复的规范化 `(ticker, position_type)`。
- `shares` 与 `average_cost` 必须为正 Decimal 且最多 8 位小数；`cost_basis` 由 Backend 确定性计算，客户端不能提交。
- Opening Position 表示“系统开始跟踪时用户申报的现有仓位”，不是 BUY、没有 commission / fee / cash impact，也不接受或伪造 purchase date。`recorded_at` 只表示 Backend 接收该 Starting Fact 的 ingestion timestamp，不是买入时间或经济事件发生时间。
- Opening Position 不使用经济 `sequence`。POST Response 与 GET List 均按规范化 `(ticker, position_type)` 确定性排序，不为列表排序引入没有业务含义的 Ledger sequence。
- 一个 Portfolio 最多成功初始化一次 Opening Positions，且必须发生在第一笔 Transaction 和第一笔 Cash Event 之前。已有 Opening Position、Transaction 或 Cash Event 时返回明确 `409`，整个 Batch 不产生部分写入。
- Initial Cash 仍在 Create Portfolio 时记录为当前可用现金，UI 默认 `0`；Opening Positions 不借由虚构 BUY 扣减 Initial Cash。
- 用户点击 Skip 只是暂时跳过 Setup 的 UI 行为，不创建 Event 或额外持久化标志；如果尚无 Opening Position、Transaction 或 Cash Event，Setup 仍可再次进入。第一笔正常经济 Mutation 会自然封闭 Opening State 初始化。
- 不新增 `portfolio_initialized` Infrastructure；Application 在 User Lock 内根据已有 Opening Position / Transaction / Cash Event Facts 判断初始化 Gate。
- Deterministic replay 从 Opening State 开始，再按既有规则重放 Cash Events 与 Transactions。后续 BUY / SELL 的 Average Cost、Cost Basis、Cash 与 Oversell 仍由 Backend 计算。
- POST 发生 Network Ambiguity 时不自动 Retry；Snapshot / Opening Position List 标记需刷新，用户只能检查最新确定性状态，M8 不提供 Mutation ID 或精确 Reconciliation。

#### Read-only Record API

- `GET /v1/portfolios/{user_id}/opening-positions`
- `GET /v1/portfolios/{user_id}/transactions`
- `GET /v1/portfolios/{user_id}/cash-events`

三个 Endpoint 均返回完整 `items` 与 `items_are_complete: true`；Decimal 继续使用字符串。Transaction / Cash Event 保留各自经济 sequence 升序，Opening Position 按 `(ticker, position_type)` 稳定排序且没有 sequence。M8 Local MVP 不增加 Pagination、Search、Update、Delete、Undo 或 Reconciliation。UI 可以按最新记录优先展示经济记录，但不得编辑这些 immutable facts。

Transaction / Cash Event 的 Application 查询能力已经存在，API 只做薄 Mapping；Opening Position 新增独立 Domain Entity、Repository / UoW 能力与 `opening_positions` Table，但不增加 Opening Position sequence。Migration 同时扩展 Transaction `position_type` 的长度与约束以接受 `UNSPECIFIED`，不改写已有 Ledger Row。

## 4. Acceptance Criteria

- 未认证用户首次打开 `/app/` 只看到产品主页、注册和登录入口，不触发 Portfolio / Agent 数据请求，也不需要 Demo Seed 或 UUID。
- 用户可用 Email、Password 与 Display Name 注册本地 Account；Password 明文与 Session Token 不进入 Database、日志、Response 或 `localStorage`。
- Register / Login 设置持久 HttpOnly Session Cookie；Logout、Session 过期与错误密码具有明确状态，登出后 Browser Back 不得恢复敏感 Portfolio DOM。
- 注册后可立即初始化 Portfolio，也可退出并在下次登录后继续；Portfolio 未初始化时 Investment Question 与 Ledger Mutation 保持禁用。
- 用户可输入 Initial Cash 与可选 Existing Positions 创建唯一 Portfolio；成功后自动加载完整 Snapshot，正常 UI 不显示或要求输入 UUID。
- Initial Cash UI 默认 `0`，并明确表示“开始跟踪时的当前可用现金”；没有输入时不得使用 Demo 金额或隐式大额默认值。
- 新建 Portfolio 后优先进入 Existing Positions Setup；用户可一次性批量录入 ticker、shares、average cost 与可选 position type，也可明确跳过。
- Opening Positions 作为独立 immutable starting facts，不产生虚构 BUY、Fee 或 Cash Movement；Batch 非法时不产生部分写入。
- Opening State 只能在尚无 Opening Position、Transaction 与 Cash Event 时提交；第一笔正常经济 Mutation 后初始化被自然封闭并返回明确 `409`，不增加额外初始化状态 Infrastructure。
- 同一浏览器重新访问 `/app/` 通过有效 Server Session 恢复 Account 与唯一 Portfolio；无效或过期 Session 回到 Public Home。
- 所有 Portfolio、Ledger 与 Investment Request 的 User Identity 只由有效 Session 决定；客户端 UUID、URL Query 或 Request Body 不得选择其他 User。
- Account A 不得读取、提问或修改 Account B 的 Portfolio；未认证请求返回稳定 `401`，跨 Owner 访问不泄露目标 Portfolio。
- BUY / SELL 支持 ticker、price、shares、可选 position type、可选 occurred time 与 reason；未分类时明确保存为 `UNSPECIFIED`，派生 amount / commission / fee schedule 只由后端产生。
- Positions、Transactions 与 Cash Activity 分别展示当前仓位、只读交易记录和只读现金记录；记录列表不提供修改、删除或 Undo。
- DEPOSIT / WITHDRAWAL 复用现有 Cash Event API，并支持 amount、可选历史发生时间与可选 reason；时间留空时同样使用 Backend Application Clock。
- future / naive timestamp、非法 Ticker / Decimal / Enum、Insufficient Cash、Oversell 与 Unknown User 具有清晰且不混淆的 Failure State。
- 写入失败不产生部分 Ledger；成功写入后必须重读 Snapshot，前端不计算或猜测新的 Portfolio State。
- Mutation 期间 Portfolio Setup、Logout 与其他 Auth Transition 被禁用；Read Request 仍不得用 stale Response 覆盖当前 Account / Portfolio Context。
- Transaction / Cash Event / Opening State Network Ambiguity 不自动重试，Snapshot 标记为 `refresh_required`；Reload 后获取最新 Snapshot / Records 供用户检查，但不保证证明某一次 timeout POST 是否执行或恰好执行一次。
- Register / Portfolio Setup Response 丢失时明确显示结果未知且不自动重试；Register 可引导 Login，Setup 可通过 Session `portfolio_ready` 与 GET Snapshot 恢复当前状态。
- 页面在英文和中文下均能完成 Register、Login、Logout、Portfolio Setup、BUY、SELL、DEPOSIT、WITHDRAWAL 与 Ask Flow；语言切换不改变身份或请求状态。
- 首次初始化 / 恢复、独立 Decision Questions 与 Portfolio 维护使用分离的 Client-side View；Portfolio 内的 Positions、Transactions 与 Cash Activity 不堆叠在同一长页。
- 当前浏览器标签页可连续展示多个真实 Agent Question / Answer，并从 Question History 跳转；刷新、Logout 或 Account 变化后清空，且不写入 localStorage。每个问题独立分析，历史 Q/A 只是 Presentation History，不作为模型 Conversation Memory。
- Answer 是默认视觉主体；每个回答的 Sources 以独立、键盘可操作的 disclosure 默认折叠，展开后仍显示完整 Grounding 与 Failure State。
- 所有动态文本遵守 M7 XSS Boundary；静态模板之外不使用动态 HTML 字符串拼接。
- README、Architecture、Roadmap、Plan 与实际本地流程一致；默认只绑定 loopback。
- 默认 Regression Gate、相关 PostgreSQL Integration、Automated Review 与固定 Human Browser Smoke 通过。
- Human Acceptance 必须使用正式 `position_pilot.main:app` 验证真实 Investment Agent Response；`tests.browser_smoke_app` 的示例回答不构成产品 Acceptance Evidence。
- Human Acceptance 通过后形成 `1.0.0`；不自动 Push、创建远程 Release 或公开部署。

## 5. UX 与状态设计

### 5.1 页面层级

保留 M7 绿色视觉语言与同源 Vanilla UI，并使用轻量 Client-side Screen 形成清晰的信息架构：

1. **Public Home**：产品价值说明与 Create Account / Log In；未认证时不展示 Portfolio UUID、Ledger Form 或 Agent Composer。
2. **Register / Login**：注册只包含 Display Name、Email、Password 与确认密码；登录只包含 Email / Password。错误不泄露 Password、Hash、Session 或内部异常。
3. **Portfolio Setup**：登录但尚无 Portfolio 时，独立显示 Initial Cash 与可选 Existing Positions；Draft 只存在内存，可退出并下次继续，不创建虚假 Ledger。
4. **Decision Questions**：Portfolio Ready 后默认进入独立问题页；左侧 Question History 只索引当前标签页问题，底部 Composer 调用正式 Agent。Answer 默认显示，Sources 默认折叠。
5. **Portfolio Workspace**：通过 Positions / Transactions / Cash Activity 三个 Panel 分别展示 Snapshot / Existing Positions、只读交易记录 + BUY / SELL、只读现金记录 + DEPOSIT / WITHDRAWAL。
6. **Authenticated Shell**：侧栏承担 Ask / Portfolio 切换与 Question History；右上角只显示当前 Account 与 Logout，不增加 Account Settings 或多 Portfolio 管理器。

不增加持久化聊天历史、多会话管理、模型 Conversation Memory、Account Settings、交易历史编辑器、Dashboard Chart 或复杂 Modal 流程。窄屏保持基本可用。

### 5.2 Client State

认证后的 Client State 保持最少字段：

```text
authState          = anonymous | checking | authenticated
account            = 当前 Server Session 返回的非敏感 Account View
portfolioReady     = 当前 Account 是否已创建唯一 Portfolio
loadedUserId       = 仅供现有内部协调使用、由 Server Session Response 产生的 Portfolio User
portfolioGeneration / questionGeneration
authGeneration     = 当前 Register / Login / Logout Request 代次
writeState         = idle | submitting | refresh_required
activeView         = questions | portfolio
portfolioSection   = positions | trade | cash
questionHistoryCount = 当前标签页内的问题展示序号
```

- App 启动只通过 `GET /v1/auth/session` 恢复身份；不读取 URL `user_id` 或 Portfolio local pointer。
- Register、Login、Logout 与 Portfolio Setup 必须正确使旧 Question / Result stale；语言切换不得重建 Client State。
- Mutation 进入 `submitting` 时捕获当前 Session-bound Portfolio，禁用 Logout、Portfolio Setup 与同一 Mutation Form；完成后恢复 Identity 操作。
- Mutation 失败或结果不确定时进入 `refresh_required`，Snapshot、Ledger Entry 与 Question 保持禁用，直到用户成功 Reload。
- Portfolio Setup 成功但后续 GET 失败时，保留 `portfolioReady` 并提供显式 Reload，不重复创建。
- 当前标签页内的 Question / Answer 只存在于 DOM / 内存 Presentation State；Logout 或 Account Context 变化时清空，普通 View / Panel 切换与成功 Mutation Refresh 不清空已完成记录。每次 Agent Request 只发送当前 `question`，Server 从 Session 注入 User Identity；不发送先前 Q/A、Conversation ID 或 Question History。

### 5.3 表单与时间

- Decimal 使用文本 / decimal input 传输为 JSON string；不使用 JavaScript 浮点计算金额或费用。
- Ticker 可在提交前 `trim + uppercase`，最终合法性仍以后端为准。
- `occurred_at` 默认留空且不发送；Backend Application Clock 是默认 Ledger 时间来源。只有用户主动选择历史时间时，才按浏览器本地时区解释并转换为 offset-aware ISO 字符串，同时显示本地时区提示。
- BUY / SELL、DEPOSIT / WITHDRAWAL 必须同时用文字和控件状态区分，不只依赖颜色。
- Position Type 控件默认“未分类 / Unspecified”，不是必填项；选择器必须解释省略只作用于独立 `UNSPECIFIED` Bucket，不会自动匹配 LONG_TERM / SWING。
- Existing Positions Setup 使用可增删的本地 Draft Rows，一次确认后原子提交；Draft 不写入 localStorage，Server 成功后不能在 M8 内编辑或删除。已有 Transaction 或 Cash Event 时 Setup 必须禁用并解释 Initialization 已封闭。
- 成功消息说明记录类型与后端返回 ID；Transaction / Cash Event 可同时展示其经济 sequence，Opening Position 不展示 sequence。金融状态只展示随后 GET 的 Snapshot。

## 6. 实现任务与依赖

```text
T0 M7 Acceptance / Merge + M8 Baseline
  ↓
T1 Create Portfolio API
  ↓
T2 Ledger Time Rule + Transaction Write API
  ↓
T3 Local Onboarding / Recovery
  ↓
T4 Ledger Entry UI + Snapshot Refresh
  ↓
T4A Opening Position Domain / API + Optional Position Type
  ↓
T4B Read-only Record Views + Existing Positions UX
  ↓
T4C Local Authentication + Product Entry + Session-bound API
  ↓
T5 End-to-end Verification + v1.0.0 Docs
  ↓
T6 Automated Review → Fix → Re-check → Human Acceptance
```

### T0 — Milestone Transition 与基线

- 取得明确 M7 Human Acceptance 后完成最终检查，并将 M7 Branch 合并到本地 `main`；不自动 Push 或删除 Branch。
- 从更新后的 `main` 创建 `codex/m8-local-portfolio-management`。
- 将 M7 Plan / Roadmap 同步为实际接受状态，将 M8 更新为 `IN PROGRESS`。
- 保留用户未跟踪的根目录 `main.py`，不修改、不删除、不提交。
- 运行 pytest、Ruff format / lint、mypy、`uv lock --check`、Alembic heads / history 与 `git diff --check`，记录 M8 Baseline。

### T1 — Create Portfolio API Slice

- 原 Slice 已增加 `CreatePortfolioRequest` / `PortfolioCreatedResponse` 与匿名 `POST /v1/portfolios`；T4C 必须停用该匿名入口，并由 authenticated `POST /v1/portfolio` 替代。
- 直接调用 `PortfolioService.create_user()`；Handler 只负责 Schema Mapping 和稳定 Error Mapping。
- 覆盖 display name normalization、zero initial cash、Decimal 精度 / 上限和 422 Contract。
- 增加 API Contract Test 与真实 PostgreSQL opt-in Integration Flow；不增加 Repository 方法或 Migration。

### T2 — Transaction Write API Slice

- 在 Application Service 统一 Transaction / Cash Event actual-time default，并补充省略时间、UTC normalization、future rejection 与 backdated replay Tests。
- 增加 Transaction Request / Response Schema；T4C 对正常产品 Flow 暴露 Session-bound `POST /v1/portfolio/transactions`。
- 复用 `RecordTransactionCommand` 与既有 Domain / UoW；API 不计算 amount、commission、Cash、Average Cost 或 Position。
- 现有 Cash Event Endpoint 保持 Resource 与行为边界，仅允许省略 `occurred_at` 并由 Application Clock 补齐。
- 增加 API Tests：BUY / SELL、双 Position Type、Decimal string、默认 / 历史时间、404、409 Cash、409 Shares、422 Domain / Request Validation。
- 增加 PostgreSQL Integration：写入后 Ledger Record 与 GET Snapshot 一致，失败不 Commit，历史补录 sequence 稳定。

### T3 — 原 Local Onboarding（已由 T4C 替代）

- 原 Slice 的 Create / Load Existing UUID、URL / local pointer、Forget Pointer 已完成并保留在 Git History 与工程 Fixture。
- Authentication Revision 不沿用该恢复模型；正常产品入口改为 Public Home、Register / Login、Session Recovery 与 Portfolio Setup。

### T4 — Ledger Entry UI 与状态刷新

- 增加独立 Trade / Cash 表单，字段与 D2 Contract 一致；T4C 后只在有效 Session-bound Portfolio 下启用。
- Cash Form 调用既有 Endpoint；Transaction Form 调用新增 Endpoint。
- 实现 `writeState`、Mutation 期间 Identity Lock、重复提交保护、Network Ambiguity、成功后 GET、刷新失败 stale state 与安全错误映射。
- Transaction / Cash Event ambiguity 只要求 Reload 当前 State，不声称能识别某一次 POST；Registration / Portfolio Setup ambiguity 按 D4 的可恢复当前状态处理。
- 扩充静态 Contract Tests；复杂异步 Side-effect 场景继续使用可控 Browser Smoke，不为 M8 自动引入 Node / Playwright。

### T4A — Opening Position Domain / API 与可选仓位类型

- 增加 `PositionType.UNSPECIFIED`，并让 Opening Position 与 Transaction Request 的缺省 / `null` 在 Application / Domain Boundary 归一化为该值；现有 LONG_TERM / SWING Replay 与隔离不得退化。
- 新增 immutable `OpeningPosition` Starting Fact、批量初始化 Command 与 UoW / Repository 能力；Replay 从 `initial_cash + OpeningPosition[]` 开始，再应用既有 Transaction / Cash Event Ledger。Opening Position 不增加 sequence。
- 增加 Opening Position POST，覆盖 1～100 行、重复 Key、Decimal、one-time / pre-economic-mutation Gate、原子失败与 Network Ambiguity；T4C 后正常产品使用 Session-bound singular route，已有 Opening Position、Transaction 或 Cash Event 均返回 `409`。
- 新增非破坏性 Alembic Migration：创建 `opening_positions`，扩展 Transaction Position Type Constraint / Column Length；覆盖 upgrade、downgrade 与现有数据保留。
- 更新 Agent Context / Prompt Contract，使 `UNSPECIFIED` 保持未知分类，Opening Position 不出现在 Historical BUY Facts 中；复用 M6 Behavioral Eval Harness 增加三类仓位隔离、类型定向与聚合场景，不引入新 Eval Framework。

### T4B — Read-only Record Views 与 Existing Positions UX

- 为 Opening Positions、Transactions、Cash Events 增加三个只读 GET Adapter；复用现有 Service 查询，保持稳定顺序、Decimal String 与完整性声明。
- 新建 Portfolio 成功后进入 Existing Positions Setup；支持本地 Draft Row 增删、可选 Position Type、原子确认与明确 Skip。
- Transactions / Cash Activity Panel 在写入表单之外展示只读记录；任何写入成功后刷新 Snapshot 与对应列表。
- 将原有问答页与索引产品文案改为 Decision Questions / Question History，并明确历史只用于当前标签页展示，不构成上下文连续对话。
- 保留 `writeState`、Identity Lock、安全动态文本、双语与 responsive layout；不得在 Browser 计算 Cost Basis、Average Cost、Fee 或 Cash。

### T4C — Local Authentication、产品入口与 Session-bound API

- 新增 `accounts` 与 `auth_sessions` Alembic Migration；Account 可先于 Portfolio 存在，并通过 nullable unique ownership link 最多绑定一个现有 Portfolio User。旧 Demo User 不自动认领、不因知道 UUID 获得访问权。
- 新增独立 Auth Application Service：Email normalization、Password Hash / Verify、Register、Login、Logout、Session Lookup / Expiry 与一次性 Portfolio Setup。Password 使用 Python 标准库 `scrypt`、随机 Salt 与自描述参数格式；Session 使用随机 opaque token，Database 只保存 SHA-256 Digest。
- Password 长度固定为 8～128 个 Unicode 字符；Session TTL 固定 7 天。登录失败统一返回 `401 / INVALID_CREDENTIALS`，不区分 Email 不存在或密码错误。
- Cookie 使用 `HttpOnly + SameSite=Lax + Path=/ + Max-Age`；loopback HTTP 下不设置 `Secure`。不启用 CORS；所有有副作用 Endpoint 继续只接受 JSON。若未来离开 loopback / local-only 边界，必须重新设计 HTTPS、CSRF、Rate Limiting 与远程 Account Security。
- 新增 Register / Login / Logout / Session API 及 Session-derived Singular Portfolio Adapters。现有匿名 `POST /v1/portfolios` 必须停用；所有 UUID 路由与 Investment Question body 身份不得绕过 Session Ownership。
- Portfolio Setup 在一个事务中创建现有 User、可选 Opening Positions 并绑定 Account；失败不留下半成品。Setup 可注册后立即执行，也可下次 Login 后继续。
- 前端增加 Public Home、Register / Login、Portfolio Setup 与 Account / Logout；删除正常流程中的 UUID Input、URL Identity 与 Portfolio local pointer。
- 正式产品 `main.py` 继续装配真实 Investment Agent；Browser Smoke Fake Agent 只用于自动化，不作为 Human Acceptance 页面或回答。
- Answer 保持正文优先；每个 Answer 独立渲染默认折叠的 Sources disclosure，并保留完整 Source Grounding、安全 DOM Text 与键盘可访问性。

### T5 — Verification、Release Documentation 与版本

- 固定 Browser Smoke 聚焦正常自助闭环与主要领域失败；Network Ambiguity、POST 后 GET Failure、XSS Payload 与 delayed stale read 作为定向 Engineering Verification / Automated Review，不要求每次 Human Acceptance 全量人工复现。
- 更新 README：Public Home、Register / Login、Portfolio Setup、Ledger Entry、真实 Agent、Session expiry、loopback 与本地认证限制；Demo Seed / Browser Smoke 只保留为开发 Fixture。
- 更新 ARCHITECTURE：Account→Portfolio Ownership、Credential / Session Boundary、Session-derived API、Opening State、Browser 不持有身份或金融 Source of Truth，以及 M8 “Portfolio”仍是现有 `User → Portfolio State`。
- 新增 ADR 记录最小 local Authentication：为什么使用 opaque persisted Session、scrypt、HttpOnly Cookie、loopback-only，以及何时必须升级 Account / Security Architecture。
- Human Acceptance 前将 `pyproject.toml` 版本更新为 `1.0.0` 并同步 lock metadata；不自动创建 Git Tag、GitHub Release 或 Push。

### T6 — Review 与收口

- 基础检查通过后执行 Automated Review，重点检查 Password / Session 泄露、Session fixation / expiry、匿名与跨 Account 访问、Portfolio Setup Atomicity、Public API、Opening State Gate、Ledger Atomicity、future timestamp、Decimal、Mutation Lock、POST Network Ambiguity、stale read response、XSS 与 localStorage Boundary。
- 修复 Critical / High Findings，按影响重新运行 Unit、API、Integration、Static Contract 与 Browser Flow。
- 将 Plan、Roadmap 和 Architecture 状态同步为实际结果，记录环境 Skip 与已知限制。
- 提交 Human Acceptance Evidence；通过后合并到本地 `main`，不自动 Push、删 Branch 或公开部署。

## 7. Verification Matrix

| 层级 | 必须验证的行为 | 主要方式 |
|---|---|---|
| Domain / Service | Create、Opening Position、BUY / SELL、Cash、UNSPECIFIED、future / backdated、原子失败 | Unit Tests |
| API Contract | Auth、Session-bound Portfolio / Opening / Records、Decimal、optional Enum、401 / 409 / 422 | FastAPI TestClient |
| Persistence | Account / Session / User / Opening / Transaction / Cash 写入、expiry 与 replay 一致 | Opt-in PostgreSQL Integration |
| Local Recovery | HttpOnly Session 恢复、expiry、logout、未初始化 Account 恢复 Setup | Static Contract + Browser Smoke |
| UI Identity | Session-derived Account / Portfolio、Mutation Lock、stale Read / Answer | Static Contract + 定向 Controlled-delay Verification |
| UI Mutation | 重复点击、成功后 GET、refresh_required、所有 Mutation POST ambiguity | API Fixtures + 定向 Engineering Verification |
| Agent Behavior | 三类 Position Key、SWING-specific、总持仓聚合、UNSPECIFIED 解释 | 复用 M6 Behavioral Eval Harness |
| Security | Password Hash、Session Digest / Cookie、Ownership、动态文本、localStorage、loopback 边界 | Unit / API + Code Review + Browser Injection |
| Regression | M7 Portfolio / QA / Sources 与 Backend 不退化 | pytest、Ruff、mypy、lock / Alembic checks |

### 7.1 `UNSPECIFIED` Behavioral Regression

以下 Cases 复用 M6 已有 Behavioral Eval Harness，不引入新的 Eval Framework：

| Case | 固定场景 | 必须满足的行为 |
|---|---|---|
| A — 三类仓位同时存在 | 同一 ticker 同时存在 `GOOG / LONG_TERM`、`GOOG / SWING`、`GOOG / UNSPECIFIED` | Agent 不混淆 shares 或 average cost，不把 `UNSPECIFIED` 自动归类。 |
| B — 明确询问 SWING | “我的 GOOG 波段仓现在怎么样？” | 只使用 SWING-specific Position Facts，不把 LONG_TERM 或 UNSPECIFIED 合并进 SWING。 |
| C — 总持仓问题 | “我的 GOOG 总共持有多少？” | 允许由确定性代码聚合三类 shares；回答同时说明存在未分类仓位，不赋予其策略属性。 |
| D — UNSPECIFIED 解释 | Context 包含 `UNSPECIFIED` Position | Context / Answer 将其解释为“用户尚未提供策略分类 / unknown strategy classification”，不得推断为 LONG_TERM 或 SWING。 |

固定 Human Browser Smoke 至少包含：

- [ ] Public Home 只显示产品说明与 Register / Login，不触发 Portfolio Request。
- [ ] Register、Login、错误密码、Logout、Session 恢复与过期状态。
- [ ] Account 可立即完成 Portfolio Setup，也可下次 Login 后继续；正常 UI 不显示 UUID。
- [ ] Initial Cash 默认 0，Setup 可录入或跳过 Existing Positions。
- [ ] Opening Positions Batch 成功、失败原子性及写后 Snapshot。
- [ ] Existing Position Setup 在第一笔 Transaction 或 Cash Event 后封闭并展示清晰说明。
- [ ] Position Type 留空归为 UNSPECIFIED，且三类 Position Key 独立。
- [ ] Refresh / HttpOnly Session recovery；Logout 后 Back 不恢复 Portfolio DOM。
- [ ] Account A 不得访问 Account B 的 Portfolio / Ledger / Question。
- [x] BUY 与 SELL，且写后重新取得 Snapshot。
- [x] 同 ticker 的 `LONG_TERM` / `SWING` 独立。
- [x] DEPOSIT 与 WITHDRAWAL。
- [ ] Transactions / Cash Activity 显示对应只读记录。
- [x] Insufficient Cash 与 Oversell。
- [x] Invalid / future input。
- [ ] 正式 Agent Investment QA 的 `OK` / `DEGRADED` / Error；Sources 默认折叠并可键盘展开。
- [ ] Onboarding、Decision Questions 与 Portfolio Workspace 可清晰切换，Portfolio 三个 Panel 不同时堆叠。
- [ ] 当前标签页连续提出至少两个 Question 后，两个独立 Answer / Sources 均保留且可从 Question History 跳转；页面说明问题独立分析，刷新后不恢复，也不形成模型 Memory。
- [x] 中文 / 英文完整闭环。
- [x] Narrow-screen basic usability。

以下场景保留为定向 Engineering Verification / Automated Review，不要求每次 Human Acceptance 全量手工复现：

- Registration / Portfolio Setup / Opening State / Transaction / Cash Event Network Ambiguity；
- Session expiry、tampered token 与 Login rotation；
- POST 成功后的 GET refresh failure；
- XSS adversarial payload；
- delayed stale read response。

Browser Smoke 是可重复的 Human Verification Evidence，不计入默认 Automated Regression Gate。

## 8. Atomic Commit 建议

1. `docs: approve M8 local authentication boundary`
2. `feat: add local account authentication`
3. `feat: secure portfolio api with sessions`
4. `feat: add authenticated product onboarding`
5. `fix: collapse investment answer sources`
6. `docs: complete v1 local self-service release`

以实际 Logical Change 为准，不为数量机械拆分。每个实现 Commit 前先通过对应 Slice Tests；Review 修复后重新验证。Plan Review 阶段不创建 Production Commit。

## 9. Non-Goals

- Email Verification、Password Reset / Change、OAuth、MFA、Organization、Role / Permission、Account Settings 或 Cloud Account；
- Portfolio Enumeration、Multiple Portfolio Management、共享设备 Account Switcher 或远程 Session Management；
- 修改 / 删除不可变 Transaction 或 Cash Event；
- Text / Screenshot Recognition、Broker Sync 或未确认的 Bulk Import；M8 仅支持最多 100 行的手工 Opening Position Draft + 单次原子提交，M9 在其上增加识别与确认流程；
- Fee Policy 选择、P&L、Portfolio Return、Technical Indicator 或 Chart；
- Order、Pending Trade、Scheduled Cash Event、Execution、Partial Fill 或 Reconciliation；
- Transaction History Editor、Undo、自动 Retry 或通用 Idempotency Infrastructure；
- Position Type Reclassification、跨类型 Transfer 或改写既有 Ledger；
- Conversation Memory、Conversation ID、历史 Q/A 注入或上下文连续对话；
- React / Vue / Node / Playwright、Frontend Framework Migration；
- 公开部署、Remote Push、GitHub Release 或 Production Security 声明。

## 10. Implementation Evidence

- `OpeningPosition` 已作为无 sequence、无现金影响的 immutable Starting Fact 实现；当前 State 由 `Opening State + Replay(Cash Events + Transactions)` 确定性重建。初始化在 User Row Lock 下检查三类记录均为空，1～100 行一次提交，规范化重复 key 或任一非法行不会产生部分写入。
- `PositionType.UNSPECIFIED` 已贯穿 Domain、Database、API、Agent Prompt 与 UI。省略或 `null` 的 Public API 输入统一归一为 `UNSPECIFIED`；同一 Ticker 的 `UNSPECIFIED / LONG_TERM / SWING` 独立 replay，Agent 不得把未分类仓位推断为长期或波段策略。
- Alembic `20260830_0005` 新增 `opening_positions`、扩展 Transaction Position Type Constraint，并在存在 Opening Position 或 `UNSPECIFIED` Transaction 时拒绝有损 downgrade。Authentication Revision 尚待新增独立 Account / Session Migration；仍不增加 Database、Framework、Node、Playwright、Idempotency 或 Multiple Portfolio Entity。
- Public API 已提供 Opening Position 批量 POST，以及 Opening Position、Transaction、Cash Event 三个完整只读 List GET。Opening Position 按 `(ticker, position_type)`，经济记录按 sequence 升序；Response 保留 `items_are_complete`、后端 id / timestamp、Decimal string 与派生字段。
- Portfolio Workspace 已提供一次性 Existing Positions Draft、Skip / Reopen、三个只读 Record List、可选 Position Type 与详细领域错误；创建空组合后优先进入 Positions Setup。Browser 仍不计算 Cash、Average Cost、Cost Basis、Amount 或 Fee，所有动态文本继续只通过安全 DOM Property 渲染。
- 问答产品文案统一为 Decision Questions / Question History。当前标签页可保留多个独立 Question / Answer 与 Source Cards；T4C 后每次 Request 只发送当前 Question，身份由 Session 注入。刷新、Logout 或 Account 变化会清空展示历史，不构成 Conversation Memory。
- Human UI Feedback 后，问答卡明确分隔“回答正文”和“上下文来源”，来源类型使用产品化名称并说明其证据性质；Decimal 仍保留后端原始精度，但浏览器展示会移除无意义的末尾零并限制大额现金文本溢出。
- 2026-08-30 pre-auth Browser Smoke 已验证原 Portfolio / Ledger Slice：Create、默认现金 0、批量 Existing Positions、`UNSPECIFIED / LONG_TERM` 独立、DEPOSIT、WITHDRAWAL、BUY、SELL、Insufficient Cash、Oversell、future timestamp、写后 Snapshot / Record List refresh、OK / DEGRADED / Sources、中英文与 390px 窄屏。该证据不覆盖新 Authentication，也不作为真实 Agent Human Acceptance。
- 默认 Regression：`410 passed, 45 skipped`。Skip 包含 13 个需要显式 `TEST_DATABASE_URL` 的 PostgreSQL Integration Tests、28 个真实模型 Behavioral Eval，以及 4 个真实 Provider / Agent opt-in Tests；没有把 Skip 声称为已执行。
- JavaScript syntax、Ruff lint、mypy、`uv lock --check`、Alembic heads / history 与 `git diff --check` 已通过；Ruff format 只检查受控的 `backend / alembic / tests`，用户未跟踪的根目录 `main.py` 未修改、未格式化或提交。

## 11. Human Review Gate

以下情况必须暂停对应实现并提交新 Decision Proposal：

- 把 D1 的最小本地 Authentication 扩展为 Email Verification、Password Lifecycle、OAuth、MFA、Organization、Role / Permission、Remote Session Management 或 Cloud Account；
- 超出 D2、D5、D6 已批准边界继续改变 Public API Contract；
- 允许 future Transaction，或修改 immutable Ledger / replay / fee / Average Cost 语义；
- 引入已批准 Account / Session Migration 之外的新 Database、Provider、Framework、Cache、Queue、Idempotency Store 或其他 Infrastructure；
- M8 完成并准备合并到 `main`。

本次 Plan 已获批执行 D1 Authentication Revision 与既有 D2～D6 本地实现范围，不等于 M8 Human Acceptance，也不授权开始 M9 Import。
