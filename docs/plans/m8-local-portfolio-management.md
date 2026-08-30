# M8 — Local Portfolio Management 执行计划

## 1. 状态与目标

**Status:** IMPLEMENTED — Awaiting Human Acceptance (2026-08-30)

M8 将当前“需要 Demo Seed 或已知 UUID 才能使用”的 M7 Interface，扩展为本地用户可从零开始并持续维护的 Self-Service MVP。M8 完成并通过 Human Acceptance 后形成 `v1.0.0`。

核心闭环：

```text
Create Local Portfolio + Initial Cash
        ↓
Auto-load Deterministic Snapshot
        ↓
Append BUY / SELL / DEPOSIT / WITHDRAWAL
        ↓
Reload Ledger-derived Portfolio State
        ↓
Ask Investment Question
        ↓
Grounded Answer + Sources / Failure State
```

M8 不实现 Authentication 或线上注册。“Portfolio name”只用于创建本地 Portfolio Owner；浏览器保存的 UUID 只是本机便利指针，不是 Session、Credential 或访问控制。

## 2. 开始条件与当前基线

- M7 Production、Test 与 Documentation 已提交在 `codex/m7-minimal-product-interface`，但计划状态仍是 `IMPLEMENTED — Awaiting Human Acceptance`；M8 Production 实现必须等 M7 明确 Human Accepted 并合并到本地 `main` 后，从 `main` 创建 `codex/m8-local-portfolio-management`。
- 已批准的 Release Roadmap 与本计划属于独立 Planning Change，不计作 M7 功能范围；它们可以随已批准文档进入 `main`，但不能替代 M7 Human Acceptance。
- `PortfolioService.create_user()` 已原子创建带 `initial_cash` 的 User；当前没有 Public API。
- `PortfolioService.record_transaction()` 已负责 User Row Lock、Ticker / Decimal / Position Type 校验、金额与 IBKR Fee 派生、历史补录重排、Cash / Oversell Validation 和 Transaction Commit；当前没有 Public API。
- `POST /v1/portfolios/{user_id}/cash-events` 已支持 DEPOSIT / WITHDRAWAL，不重复实现。
- `GET /v1/portfolios/{user_id}` 已返回完整当前 Snapshot；前端写入成功后继续通过该 Endpoint 重读，不在浏览器计算 Cash、Average Cost、Cost Basis 或 Position。
- M7 已建立 `userIdInput` / `loadedUserId`、Request Generation、Source Grounding、安全 DOM Text Rendering 与中英切换；M8 必须保留这些正确性边界。
- 当前页面只从 URL 预填 UUID，不自动加载，也不记住最近成功使用的 Portfolio；仅增加 Create 按钮仍不足以形成“持续维护”的本地体验。
- Transaction 目前未像 Cash Event 一样拒绝 future `occurred_at`。开放 UI 写入前必须统一“已经发生的 Ledger Fact”语义。
- 预计不需要 Database Migration、新依赖、前端 Toolchain 或新 Infrastructure。

## 3. Human Decision Proposal

批准本计划即批准 D1～D4 的产品与 Public API 边界；若不接受其中任一项，应在开始 Production 实现前调整计划。

### D1 — 本地身份与恢复方式

**建议：不做注册 / 登录；创建 Portfolio 后，用 URL + `localStorage` 保存最近一个成功加载的 `user_id`。**

- 首次访问优先展示 Create Portfolio，输入 Portfolio Name 与 Initial Cash。
- Server 生成 UUID；创建成功后写入 URL Query、保存为 versioned local pointer，并自动读取 Snapshot。
- 后续访问 `/app/` 时，优先级为“有效 URL `user_id` → 有效 local pointer → 未加载状态”，并自动加载选中的 Portfolio。
- 手工成功加载既有 UUID 后才更新 local pointer；仅修改输入框不得覆盖它。
- 404 时清理与该 UUID 匹配的 local pointer；提供显式“Forget local portfolio”仅删除浏览器指针，不删除 Server Ledger。
- `localStorage` 不保存 Snapshot、Transaction、Cash Event、Question、Answer、Provider Data 或 Secret。
- 不增加 Portfolio List Endpoint、账户发现、多个 Portfolio 切换器或 Server-side Session。

**理由：** 这是让单浏览器本地用户无需抄写 UUID 且能再次打开 Portfolio 的最小方案。其限制是更换浏览器或清除 Storage 后仍需通过 URL / UUID 恢复；没有 Authentication 时不能安全提供 Server 端 Portfolio Enumeration。

### D2 — 最小 Public Write API Contract

**建议：新增 Create Portfolio 与 Transaction Append 两个 Endpoint，复用现有 Cash Event Endpoint。**

#### `POST /v1/portfolios`

Request：

```json
{
  "display_name": "My Portfolio",
  "initial_cash": "10000"
}
```

Response `201`：

```json
{
  "user_id": "00000000-0000-0000-0000-000000000001",
  "display_name": "My Portfolio",
  "initial_cash": "10000.00000000",
  "created_at": "2026-08-30T08:00:00Z"
}
```

- `display_name` 为 1～200 个字符；`initial_cash` 为 `0` 以上、最多 8 位小数的 Decimal。
- 创建后前端必须调用现有 GET Snapshot，不把 Create Response 当作 Portfolio State。
- 不接受客户端指定 `user_id`、`created_at` 或其他 Ledger 字段。

#### `POST /v1/portfolios/{user_id}/transactions`

Request：

```json
{
  "ticker": "GOOG",
  "action": "BUY",
  "price": "180.25",
  "shares": "2",
  "position_type": "LONG_TERM",
  "reason": "Initial long-term position"
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
    "position_type": "LONG_TERM",
    "occurred_at": "2026-08-30T08:00:00Z",
    "reason": "Initial long-term position"
  }
}
```

- 客户端不能提交 `amount`、`commission`、`fee_schedule`、`sequence` 或 Transaction ID。
- `404 / USER_NOT_FOUND`、`409 / INSUFFICIENT_CASH`、`409 / INSUFFICIENT_SHARES`、`422 / INVALID_TRANSACTION` 保持可区分。
- Pydantic Request Validation 失败仍为 422；前端安全展示字段级或通用输入提示，不展示内部堆栈。
- 不新增 Update / Delete / Bulk Import / Transaction List API。

M8 API 中的“Portfolio”是现有 `User → Portfolio State` 模型的产品与 Resource 呈现，不新增独立 Portfolio Entity，也不为 REST 命名重构当前 Domain Model。User / Portfolio Resource Boundary 等到 V2 Multiple Portfolios 时根据 Ownership / Authorization 需求重新评估。

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

**建议：有副作用的 POST 通过禁止并发身份切换保持简单；所有 Portfolio Mutation 只绑定当前 `loadedUserId`，写后重读，绝不 Optimistic Update。**

- Portfolio 未加载、已 stale 或正在切换身份时，BUY / SELL / DEPOSIT / WITHDRAWAL 全部禁用。
- Mutation 使用以下顺序，不增加 Write Generation：

```text
Mutation 开始
→ 捕获当前 loadedUserId
→ 禁止 Create / Load / Forget / User Identity 切换
→ 禁止同一表单重复提交
→ POST Mutation
→ 成功后 GET 最新 Snapshot
→ 失败或结果不确定时将当前 Snapshot 标记 stale / refresh_required
→ Mutation 结束后恢复 Identity 操作
```

- Read Request 继续通过 `portfolioGeneration` / `questionGeneration` 处理 stale response；Mutation 期间既然不能切换 Identity，就不设计 A 的 Mutation Response 返回后发现已经切换到 B 的运行状态。
- POST 是有副作用请求，浏览器 Abort 不能被当作“服务端未写入”的保证；不自动 Retry。
- Transaction / Cash Event POST timeout 或 connection lost 时，显示“写入结果未知”，使 Snapshot stale，并要求 Reload。Reload 只重新取得当前 deterministic Portfolio State，供用户检查最新状态；M8 不保证通过 Snapshot 精确识别某一次不确定 POST 是否已经执行。
- 成功 Response 不直接修改 Cash / Position；立即 GET 最新 Snapshot。若 GET 失败，明确显示“写入成功、刷新失败”，并保持 Context stale。
- M8 不增加 Idempotency Key、Transaction List、Mutation Reconciliation 或自动 Retry；确有需求时再单独设计。
- 所有 API、User Input 和动态错误文本继续通过安全 DOM Text API 渲染。

**Known Limitation — Create Portfolio Network Ambiguity**

`POST /v1/portfolios` 可能已在 Server 成功创建，但 Response 在返回 UUID 前丢失。此时当前 UI 无法通过 Portfolio Enumeration、Session 或 Idempotency 恢复该 UUID。页面必须显示“Portfolio creation result unknown. Do not automatically retry.”或等价双语文案，不得错误声明创建失败，也不得自动 Retry。

M8 接受这一低概率 localhost 限制，不引入 client-generated UUID、Idempotency Infrastructure、Portfolio List 或 Server-side Session。

## 4. Acceptance Criteria

- 首次打开页面无需 Demo Seed 或 UUID，即可看到明确的 Create Portfolio 入口。
- 用户可输入 Portfolio Name 与 Initial Cash 创建 Portfolio；成功后 URL / local pointer 更新并自动加载完整 Snapshot。
- 同一浏览器重新访问 `/app/` 能自动恢复最近成功 Portfolio；无效或已删除的 pointer 被安全清理并回到 Create / Load 状态。
- 页面仍支持通过 UUID 加载既有 Portfolio，但 UUID 被明确描述为本地恢复标识，不是安全凭证。
- 只有当前有效 `loadedUserId` 可以提交 Ledger Entry 或 Investment Question。
- BUY / SELL 支持 ticker、price、shares、`LONG_TERM / SWING`、可选 occurred time 与 reason；派生 amount / commission / fee schedule 只由后端产生。
- DEPOSIT / WITHDRAWAL 复用现有 Cash Event API，并支持 amount、可选历史发生时间与可选 reason；时间留空时同样使用 Backend Application Clock。
- future / naive timestamp、非法 Ticker / Decimal / Enum、Insufficient Cash、Oversell 与 Unknown User 具有清晰且不混淆的 Failure State。
- 写入失败不产生部分 Ledger；成功写入后必须重读 Snapshot，前端不计算或猜测新的 Portfolio State。
- Mutation 期间 Create、Load、Forget 与 User Identity 切换被禁用；Read Request 仍不得用 stale Response 覆盖当前 Portfolio Context。
- Transaction / Cash Event Network Ambiguity 不自动重试，Snapshot 标记为 `refresh_required`；Reload 后只提供当前 State，不保证识别某一次 POST 是否执行。
- Create Portfolio Response 丢失时明确显示结果未知，不自动重试，并接受当前 UI 可能无法恢复 Server 已创建 Portfolio 的 Known Limitation。
- 页面在英文和中文下均能完成 Create、Load、BUY、SELL、DEPOSIT、WITHDRAWAL 与 Ask Flow；语言切换不改变身份或请求状态。
- 首次初始化 / 恢复、连续问答与 Portfolio 维护使用分离的 Client-side View；Portfolio 内的 Overview、Transactions 与 Cash Activity 不堆叠在同一长页。
- 当前浏览器标签页可连续展示多个 Question / Answer 并从 Session 列表跳转；刷新或更换 Portfolio Context 后清空，且不写入 localStorage、不作为模型 Conversation Memory。
- 所有动态文本遵守 M7 XSS Boundary；静态模板之外不使用动态 HTML 字符串拼接。
- README、Architecture、Roadmap、Plan 与实际本地流程一致；默认只绑定 loopback。
- 默认 Regression Gate、相关 PostgreSQL Integration、Automated Review 与固定 Human Browser Smoke 通过。
- Human Acceptance 通过，项目版本更新为 `1.0.0`；不自动 Push、创建远程 Release 或公开部署。

## 5. UX 与状态设计

### 5.1 页面层级

保留 M7 绿色视觉语言与同源 Vanilla UI，并使用轻量 Client-side Screen 形成清晰的信息架构：

1. **Start / Recover Onboarding**：无有效 Portfolio Context 时单独显示 Create Portfolio 与 Load Existing UUID；这是本地初始化，不称为账号注册。
2. **Decision Chat**：加载成功后默认进入连续问答流；左侧 Session 列表只索引当前标签页已经提出的问题，底部 Composer 提交新的独立 Question。
3. **Portfolio Workspace**：通过 Overview / Transactions / Cash Activity 三个 Panel 分别展示 Snapshot、BUY / SELL 与 DEPOSIT / WITHDRAWAL，避免账本表单和问答堆在一页。
4. **Application Shell**：侧栏只承担 Ask / Portfolio View 切换、当前 Session 跳转和本地 Portfolio 恢复入口，不扩展为账户系统或多 Portfolio 管理器。

不增加账户菜单、持久化聊天历史、多会话管理、模型 Conversation Memory、交易历史编辑器、Dashboard Chart 或复杂 Modal 流程。窄屏保持基本可用。

### 5.2 Client State

在 M7 身份状态上增加最少字段：

```text
userIdInput        = 当前 UUID 输入值
loadedUserId       = 当前成功加载 Snapshot 的 User
portfolioGeneration / questionGeneration
createGeneration   = 当前 Create Request 代次
writeState         = idle | submitting | refresh_required
activeView         = chat | portfolio
portfolioSection   = overview | trade | cash
sessionEntryCount  = 当前标签页内的展示序号
```

- local pointer 只在 Create 成功或 GET Snapshot 成功后写入。
- Create、Load 与 Mutation 开始时必须正确使旧 Question / Result stale；语言切换不得重建 Client State。
- Mutation 进入 `submitting` 时捕获 `loadedUserId`，禁用 Create / Load / Forget / User ID 输入及同一 Mutation Form；完成后恢复 Identity 操作。
- Mutation 失败或结果不确定时进入 `refresh_required`，Snapshot、Ledger Entry 与 Question 保持禁用，直到用户成功 Reload。
- 新 Portfolio 创建成功但后续 GET 失败时，保留生成的 UUID / local pointer，并提供显式 Reload，不重复 Create。
- 当前标签页内的 Question / Answer 只存在于 DOM / 内存 Presentation State；Identity Context 变化时清空，普通 View / Panel 切换与成功 Mutation Refresh 不清空已完成记录。每次 Agent Request 仍只发送当前 `question` 与 `loadedUserId`。

### 5.3 表单与时间

- Decimal 使用文本 / decimal input 传输为 JSON string；不使用 JavaScript 浮点计算金额或费用。
- Ticker 可在提交前 `trim + uppercase`，最终合法性仍以后端为准。
- `occurred_at` 默认留空且不发送；Backend Application Clock 是默认 Ledger 时间来源。只有用户主动选择历史时间时，才按浏览器本地时区解释并转换为 offset-aware ISO 字符串，同时显示本地时区提示。
- BUY / SELL、DEPOSIT / WITHDRAWAL 必须同时用文字和控件状态区分，不只依赖颜色。
- 成功消息说明记录类型与后端返回 ID / sequence；金融状态只展示随后 GET 的 Snapshot。

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

- 在 API 层增加 `CreatePortfolioRequest` / `PortfolioCreatedResponse` 与 `POST /v1/portfolios`。
- 直接调用 `PortfolioService.create_user()`；Handler 只负责 Schema Mapping 和稳定 Error Mapping。
- 覆盖 display name normalization、zero initial cash、Decimal 精度 / 上限和 422 Contract。
- 增加 API Contract Test 与真实 PostgreSQL opt-in Integration Flow；不增加 Repository 方法或 Migration。

### T2 — Transaction Write API Slice

- 在 Application Service 统一 Transaction / Cash Event actual-time default，并补充省略时间、UTC normalization、future rejection 与 backdated replay Tests。
- 增加 Transaction Request / Response Schema 和 `POST /v1/portfolios/{user_id}/transactions`。
- 复用 `RecordTransactionCommand` 与既有 Domain / UoW；API 不计算 amount、commission、Cash、Average Cost 或 Position。
- 现有 Cash Event Endpoint 保持 Resource 与行为边界，仅允许省略 `occurred_at` 并由 Application Clock 补齐。
- 增加 API Tests：BUY / SELL、双 Position Type、Decimal string、默认 / 历史时间、404、409 Cash、409 Shares、422 Domain / Request Validation。
- 增加 PostgreSQL Integration：写入后 Ledger Record 与 GET Snapshot 一致，失败不 Commit，历史补录 sequence 稳定。

### T3 — Local Onboarding 与恢复

- 在现有页面增加 Create Form 与清晰的首次使用说明；保留 Load Existing 作为恢复入口。
- 实现 URL / local pointer precedence、成功后自动 GET、404 pointer cleanup 与 Forget Pointer。
- 页面初始化自动加载有效目标；无效 local value 只清理，不发起请求。
- Create Request 使用独立 Generation / Controller；旧 Create / Load Response 不能覆盖更新的身份上下文。
- 使用 `textContent` / DOM Property 渲染 Portfolio Name、UUID 与 Error；中英词条完整。

### T4 — Ledger Entry UI 与状态刷新

- 增加独立 Trade / Cash 表单，字段与 D2 Contract 一致；只在 `loadedUserId` 有效时启用。
- Cash Form 调用既有 Endpoint；Transaction Form 调用新增 Endpoint。
- 实现 `writeState`、Mutation 期间 Identity Lock、重复提交保护、Network Ambiguity、成功后 GET、刷新失败 stale state 与安全错误映射。
- Transaction / Cash Event ambiguity 只要求 Reload 当前 State，不声称能识别某一次 POST；Create ambiguity 使用独立结果未知文案并接受 UUID 可能不可恢复。
- 扩充静态 Contract Tests；复杂异步 Side-effect 场景继续使用可控 Browser Smoke，不为 M8 自动引入 Node / Playwright。

### T5 — Verification、Release Documentation 与版本

- 固定 Browser Smoke 聚焦正常自助闭环与主要领域失败；Network Ambiguity、POST 后 GET Failure、XSS Payload 与 delayed stale read 作为定向 Engineering Verification / Automated Review，不要求每次 Human Acceptance 全量人工复现。
- 更新 README：无需 Seed 的主流程、既有 UUID 恢复、local pointer 限制、Ledger Entry、loopback 与无 Auth 警告；Demo Seed 保留为开发 Fixture，不再是正常使用前置条件。
- 更新 ARCHITECTURE：两个新增 API、local pointer 信任边界、Browser 不持有金融 Source of Truth，以及 M8 “Portfolio”仍是现有 `User → Portfolio State` 的 API 呈现；独立 Portfolio Entity 留到 V2 Multiple Portfolios 重新评估。
- 检查是否需要 Engineering Note；D1 的 local pointer / no-auth trade-off 若仅停留在已批准 Plan 与 Architecture，不机械新增 ADR。
- Human Acceptance 前将 `pyproject.toml` 版本更新为 `1.0.0` 并同步 lock metadata；不自动创建 Git Tag、GitHub Release 或 Push。

### T6 — Review 与收口

- 基础检查通过后执行 Automated Review，重点检查 Public API、Ledger Atomicity、future timestamp、Decimal、Mutation Identity Lock、重复写入、POST Network Ambiguity、stale read response、XSS 与 localStorage Boundary。
- 修复 Critical / High Findings，按影响重新运行 Unit、API、Integration、Static Contract 与 Browser Flow。
- 将 Plan、Roadmap 和 Architecture 状态同步为实际结果，记录环境 Skip 与已知限制。
- 提交 Human Acceptance Evidence；通过后合并到本地 `main`，不自动 Push、删 Branch 或公开部署。

## 7. Verification Matrix

| 层级 | 必须验证的行为 | 主要方式 |
|---|---|---|
| Domain / Service | Create、BUY / SELL、Cash、future / backdated、原子失败 | Unit Tests |
| API Contract | 201 Payload、Decimal、Enum、404 / 409 / 422 | FastAPI TestClient |
| Persistence | User / Transaction / Cash Event 写入与 replay 一致 | Opt-in PostgreSQL Integration |
| Local Recovery | URL 优先、local pointer、404 cleanup、forget | Static Contract + Browser Smoke |
| UI Identity | loaded user only、Mutation Identity Lock、stale Read / Answer | Static Contract + 定向 Controlled-delay Verification |
| UI Mutation | 重复点击、成功后 GET、refresh_required、两类 POST ambiguity | API Fixtures + 定向 Engineering Verification |
| Security | 动态文本、localStorage 内容、loopback / no-auth 边界 | Code Review + Browser Injection |
| Regression | M7 Portfolio / QA / Sources 与 Backend 不退化 | pytest、Ruff、mypy、lock / Alembic checks |

固定 Human Browser Smoke 至少包含：

- [x] Create Portfolio。
- [x] Refresh / local pointer recovery。
- [x] Load Existing UUID。
- [x] Forget Pointer 只清理本地引用，不删除 Portfolio。
- [x] BUY 与 SELL，且写后重新取得 Snapshot。
- [x] 同 ticker 的 `LONG_TERM` / `SWING` 独立。
- [x] DEPOSIT 与 WITHDRAWAL。
- [x] Insufficient Cash 与 Oversell。
- [x] Invalid / future input。
- [x] Investment QA 与 `OK` / `DEGRADED` / Sources 保持 M7 行为。
- [x] Onboarding、Decision Chat 与 Portfolio Workspace 可清晰切换，Portfolio 三个 Panel 不同时堆叠。
- [x] 当前标签页连续提出至少两个 Question 后，两个独立 Answer / Sources 均保留且可从 Session 列表跳转；刷新后不恢复，也不形成模型 Memory。
- [x] 中文 / 英文完整闭环。
- [x] Narrow-screen basic usability。

以下场景保留为定向 Engineering Verification / Automated Review，不要求每次 Human Acceptance 全量手工复现：

- Transaction / Cash Event / Create Portfolio Network Ambiguity；
- POST 成功后的 GET refresh failure；
- XSS adversarial payload；
- delayed stale read response。

Browser Smoke 是可重复的 Human Verification Evidence，不计入默认 Automated Regression Gate。

## 8. Atomic Commit 建议

1. `docs: start M8 local portfolio management`
2. `feat: expose local portfolio creation api`
3. `feat: expose immutable transaction write api`
4. `feat: add local portfolio onboarding and recovery`
5. `feat: add portfolio ledger entry interface`
6. `docs: complete v1 local self-service release`

以实际 Logical Change 为准，不为数量机械拆分。每个实现 Commit 前先通过对应 Slice Tests；Review 修复后重新验证。Plan Review 阶段不创建 Production Commit。

## 9. Non-Goals

- Authentication、Password、Email Registration、Authorization 或 Cloud Account；
- Portfolio Enumeration、Multiple Portfolio Management、Server Session 或共享设备隔离；
- 修改 / 删除不可变 Transaction 或 Cash Event；
- Bulk Import、Text / Screenshot Recognition 或 Broker Sync；
- Fee Policy 选择、P&L、Portfolio Return、Technical Indicator 或 Chart；
- Order、Pending Trade、Scheduled Cash Event、Execution、Partial Fill 或 Reconciliation；
- Transaction History Editor、Undo、自动 Retry 或通用 Idempotency Infrastructure；
- React / Vue / Node / Playwright、Frontend Framework Migration；
- 公开部署、Remote Push、GitHub Release 或 Production Security 声明。

## 10. Implementation Evidence

- `POST /v1/portfolios` 已作为 `PortfolioService.create_user()` 的薄 Adapter 实现；`POST /v1/portfolios/{user_id}/transactions` 复用既有 Transaction Application / Domain Flow；Cash Event Endpoint 只扩展为允许省略时间。
- Transaction 与 Cash Event 的默认发生时间统一由可注入 Backend Application Clock 产生；显式历史时间要求 offset-aware，统一规范化到 UTC，并拒绝 future timestamp。
- 页面已实现 Create、URL / versioned local pointer 恢复、Load Existing、Forget Pointer、Trade / Cash 两类 Ledger Form、Mutation Identity Lock、`refresh_required`、写后 GET Snapshot 与中英切换。M8 Acceptance refinement 将首次 Onboarding、Decision Chat 与 Portfolio Workspace 拆成独立 Client-side View，并把 Portfolio 维护分为 Positions / Transactions / Cash Activity；Browser 不计算金额、手续费、Cash、Shares、Average Cost 或 Cost Basis。
- Decision Chat 可在当前标签页追加多个独立 Question / Answer 并从 Session 列表跳转；这些内容不进入 localStorage，刷新或 Identity Context 变化即清空，也不随下一次请求发送，因此不属于 Conversation Memory。该调整未改变 API、Domain、Authentication 或 Multiple Portfolio Scope。
- Human Acceptance feedback 将 Portfolio 第一分区从泛化的 Overview 明确为 Positions，并使三分区在不同页面尺寸下自适应。新 Portfolio 的 Initial Cash UI 实际默认值改为 `0`，但仍由用户决定开始跟踪时的真实可用现金；该调整不改变 Public API 或 Ledger replay。
- 交易与现金表单的示例值统一增加 `e.g.` / “例如”前缀，避免 placeholder 被误认成已输入值。客户端对 Portfolio Name、Initial Cash、Ticker、Price、Shares、Amount 与历史时间给出逐字段错误、`aria-invalid` 与焦点定位；已知后端 Ledger Failure 同时展示本地化说明、稳定 Error Code 与安全 Detail。
- “系统开始跟踪时已经存在的仓位”仍不属于 M8。它不能用 BUY 伪造，继续进入 M9 `Text / Screenshot → Draft → Human Confirmation → Opening Position` 的领域语义与 Human Review；M8 未新增 Opening Position、Ledger History Read API 或 Import UI。
- 默认 Regression：`390 passed, 39 skipped`。Skip 包含 11 个需要显式 `TEST_DATABASE_URL` 的 PostgreSQL Integration Tests、28 个真实 Provider / Model opt-in Tests；没有把 Skip 声称为已执行。
- JavaScript syntax、Ruff format / lint、mypy、`uv lock --check`、Alembic heads / history 与 `git diff --check` 已通过。用户未跟踪的根目录 `main.py` 未修改、未纳入检查或提交。
- 2026-08-30 Human Browser Smoke 已完成全部固定 Checklist；390px 视口没有水平溢出，Browser Console 无 warning / error。Network Ambiguity、POST 后 GET Failure、XSS adversarial payload 与 delayed stale read 仍按计划保留为定向 Engineering Verification / Automated Review，不属于默认自动化 E2E Gate。
- 2026-08-30 Acceptance refinement Browser Smoke 再次验证：Start / Recover 后进入独立 Decision Chat；同一标签页连续 `OK` / `DEGRADED` 两个 Question 时保留两个 Answer、五张 Source Card 与两个 Session 索引；成功 Trade / Cash Mutation Refresh 不清除已完成问答；Overview / Transactions / Cash Activity 互斥显示；刷新后 local pointer 恢复 Portfolio，但 Session Question / Answer 归零；中英切换保持身份、Snapshot 与动态 Answer；桌面侧栏与 390px 窄屏均可用，390px `scrollWidth` 无溢出，Browser Console 无 warning / error。
- Automated Review 未发现 Backend API、Ledger Atomicity、Application Clock、future timestamp、Decimal、XSS 或 Generation 的阻断问题。Review 指出的 Create 后首次 GET 404 pointer 丢失、Mutation 成功反馈、Create / Load 并发、malformed Create Response 语义、M8 文档与 stale Snapshot 展示均已修复，并在修复后重新执行相关验证。
- 未增加 Migration、Dependency、Framework、Node、Playwright、Authentication、Portfolio Enumeration、Idempotency、Transaction History 或独立 Portfolio Entity。

## 11. Human Review Gate

以下情况必须暂停对应实现并提交新 Decision Proposal：

- 改变 D1 的 no-auth local identity / persistence 边界；
- 扩展或改变 D2 Public API Contract；
- 允许 future Transaction，或修改 immutable Ledger / replay / fee / Average Cost 语义；
- 引入 Migration、新 Database、Provider、Framework、Session、Idempotency Store 或其他 Infrastructure；
- M8 完成并准备合并到 `main`。

本计划获批只授权 M8 的上述本地实现范围，不等于 M7 Human Acceptance，也不授权开始 M9 Import。
