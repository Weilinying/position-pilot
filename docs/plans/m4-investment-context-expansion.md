# M4 — Investment Context Expansion 执行计划

## 1. 状态与目标

**Status:** IN PROGRESS

**Cash Adjustment Slice:** IMPLEMENTED（等待 Human Acceptance）

M4 在扩展 Market Context、News、Fundamentals / Earnings 或 Asset Indicators 前，先完成一个独立的 Cash Adjustment Vertical Slice。该 Slice 解决 Portfolio 创建后无法追加或取出投资预算的问题，并保持 M1 已建立的 immutable ledger 与 deterministic replay 原则。

## 2. 已批准语义

- `User.initial_cash` 只表示 Portfolio 创建时的初始资金，后续不得原地修改。
- Portfolio 创建后的现金调整使用独立、不可变的 Cash Event Ledger。
- Cash Event 当前只支持 `DEPOSIT` 与 `WITHDRAWAL`，不伪装成 BUY / SELL Transaction。
- Cash Event 保存正数 `amount`、实际 `occurred_at` 和可选 `reason`；金额沿用 `Decimal` / `NUMERIC(28, 8)` 规则。
- `DEPOSIT` 增加 Available Cash；`WITHDRAWAL` 减少 Available Cash，且不得超过事件发生时可用现金。
- Position Shares、Cost Basis 与 Average Cost 只受 Transaction 影响，Cash Event 不参与持仓计算。
- Available Cash 从 Initial Cash、Cash Event Ledger 与 Transaction Ledger 确定性重建。Transaction 继续保留 M1 的佣金语义：BUY 扣除 `amount + commission`，SELL 增加 `amount - commission`。
- Cash Event 与 Transaction 按实际发生时间合并重放；同一发生时间固定先处理 Cash Event，再处理 Transaction，各自 Ledger 内按只读 sequence 保持稳定顺序。
- 写入 Cash Event 与 Transaction 都锁定 User 行，并在同一事务中读取完整 Source of Truth、重放校验和追加记录。

## 3. Scope

- 建立无 ORM 依赖的 `CashEventType`、`CashEvent` 与独立 sequence 重排。
- 扩展 Portfolio 重放，使 Cash Snapshot 同时反映 Initial Cash、Deposits、Withdrawals 和 Transactions。
- 建立 `cash_events` SQLAlchemy Model、非破坏性 Alembic Migration 与数据库约束。
- 扩展 Unit of Work 和 Portfolio Service，支持追加与查询 Cash Events。
- 新增 `POST /v1/portfolios/{user_id}/cash-events`，返回不可变 Cash Event 和写入后的 Available Cash。
- 保持 Investment Agent 的 Portfolio Snapshot 自动读取 Cash Event 调整后的 Available Cash。
- 覆盖 Domain、Service、API、PostgreSQL Persistence 与 Agent Snapshot Regression Tests。
- 更新当前 Architecture 与长期保留的 Engineering Note。

## 4. Non-Goals

- Dividend、Fee、Interest、Tax 或其他 Cash Event 类型。
- Margin、负现金、Multiple Currencies 或 Broker Synchronization。
- Investment Return、XIRR、Money-weighted Return 或 Time-weighted Return。
- Cash / Position 物化投影、Event Bus、新 Database 或新 Framework。
- M4 原有 Market / News / Fundamentals / Asset Context Expansion。

## 5. Acceptance Criteria

- `DEPOSIT 500` 使 Available Cash 增加 500；`WITHDRAWAL 200` 使其减少 200。
- Initial Cash 1000 的 Portfolio 依次发生 Deposit 500、净 BUY 现金流 300、净 SELL 现金流 100、Withdrawal 200 后，Available Cash 为 1100。
- Available Cash 100 时，Withdrawal 101 明确失败，且无 Cash Event 被写入或提交。
- Cash Event amount 必须大于 0、最多 8 位小数，并保存带时区的实际发生时间。
- Cash Event 不改变任何 Position Shares、Cost Basis 或 Average Cost。
- BUY / SELL 的金额、佣金、Position Type、历史补录和不足现金行为无 Regression。
- Portfolio State 与注入 Investment Agent 的 Snapshot 均反映 Cash Event 调整后的 Available Cash。
- 相同 User、Transaction Ledger 与 Cash Event Ledger 重建结果稳定且确定。
- `cash_events` 只能通过 Migration 创建，数据库拒绝非法 amount 与 type。
- 默认 Tests、Ruff、mypy 与可用的 PostgreSQL Integration Tests 通过。

## 6. 执行顺序

```text
T1 Roadmap / Plan / Engineering Note
  ↓
T2 Domain Cash Event + Combined Replay
  ↓
T3 SQLAlchemy Model / Migration / Unit of Work
  ↓
T4 Portfolio Service + FastAPI Vertical Slice
  ↓
T5 Unit / API / Persistence / Agent Regression Tests
  ↓
T6 Full Tests / Quality Checks
  ↓
T7 主线程 Automated Review → 修复 → 再验证
  ↓
Atomic Commits → Human Acceptance
```

Cash Event 与 Transaction 共同影响同一个 Available Cash 不变量，Domain、Service 与 Persistence 修改按依赖顺序由主线程串行完成，避免并行写入同一核心接口。

## 7. 验证方式

- Domain Tests 验证金额精度、枚举、时间、combined replay、Position 隔离、确定性与不足现金。
- Service Tests 验证 User 行锁、写入前重放、失败不追加/不 Commit、历史事件 sequence 和查询。
- API Tests 验证 201 Response、422 Validation、404 User、409 Insufficient Cash 与 Dependency Boundary。
- PostgreSQL Integration Tests 验证 Migration 后持久化恢复、数据库约束、Transaction/Cash Event 混合 Ledger 和失败回滚。
- Agent Regression Test 验证 Cash Event 调整后的 Available Cash 进入现有 Portfolio Snapshot，且不引入 Cash Event History。
- 完成实现后运行完整 pytest、Ruff lint / format check、mypy strict、Migration 检查与 `git diff --check`。

## 8. Cash Adjustment Completion Summary

### Implemented

- `initial_cash` 保持创建时事实，新增独立 frozen `CashEvent` 与 `DEPOSIT` / `WITHDRAWAL` 类型。
- Transaction 与 Cash Event 按实际发生时间 combined replay；CashBalance 派生 Available Cash、Total Deposits 与 Total Withdrawals，Position 只由 Transaction 改变。
- 新增 `cash_events` Migration、SQLAlchemy Model、独立 sequence、正金额/类型/外键/唯一约束与 Unit of Work 映射。
- Cash Event 与 Transaction 写入均使用 User 行锁和完整 ledger 重放；失败时不追加、不 Commit。
- `POST /v1/portfolios/{user_id}/cash-events` 返回 201、不可变事件及同事务重建的 Available Cash；未知 User、超额 Withdrawal 与非法输入使用不同失败状态。
- Investment Agent 继续只接收当前 Portfolio Snapshot，不注入 Cash Event History，但 Available Cash 自动反映 Cash Events。

### Automated Review

- 修正旧数据库元数据测试，使 `cash_events` 被认定为 Source-of-Truth Ledger 表，同时继续禁止 Cash / Position Projection。
- 将通用 API 错误模型从 Investment 专属命名调整为共享边界命名。
- 修正 Architecture 中把 M4 Cash Event 事实误写成 M1 原始事实的表述。
- 补强 Cash Event owner / sequence 损坏、发生时间与原因规范化、Command 不接受 ID / sequence 的边界测试。

### Verification

- 默认 pytest：177 passed，30 skipped。跳过项为显式启用的真实模型、在线 Market Data 与需要 `TEST_DATABASE_URL` 的 10 条 PostgreSQL Integration Tests。
- Cash Adjustment 定向 Domain / Service / API / Agent Tests：64 passed。
- Ruff format check / lint：PASS。
- mypy strict：PASS（41 source files）。
- `uv lock --check`、`git diff --check`、Alembic head / history：PASS。
- 使用不读取 Repository `.env` 的显式离线配置生成 Alembic 全量 PostgreSQL SQL：PASS。
- 当前 Docker daemon 未运行，且没有显式 `TEST_DATABASE_URL`，因此本次未实际执行 PostgreSQL Integration Tests。

### Decision Records

- 本设计是 ADR 0003 immutable ledger 与 deterministic replay 原则的自然延伸，没有新增 ADR。
- 新增 Engineering Note：`docs/engineering-notes/m4-cash-adjustment-ledger-extension.md`。
- M4 原有 Investment Context Expansion 尚未开始，Roadmap 保持 M4 `IN PROGRESS`。

## 9. Investment Context Slice 1 Proposal：Recent Price History

**Status:** PROPOSED（等待 Human Review）

### Problem / Evidence

M2 已通过 Alpaca Market Data Provider 实现 Historical Daily OHLCV，ADR 0004 也已批准 Basic Plan 的延迟 SIP、`adjustment=all` 与来源边界；但 M3 Agent 的 Context Capability 仍将 `price_history` 标记为 `UNAVAILABLE`。因此“最近走势如何”“近期价格路径是否走弱”等问题只能保持 UNKNOWN，现有真实能力没有进入 Agent 闭环。

该缺口可以在不选择新 Provider、不增加数据库和不改变 Single Agent Orchestration 的前提下解决，并能通过固定 Fake Historical Bars 的 Evaluation Case 验证。

### Proposed Scope

- 新增内部 LLM Tool：`get_recent_price_history(ticker)`。
- Tool 使用已批准的 `MarketDataService.get_historical_bars` 与 Alpaca Historical Daily OHLCV；不新增 Provider。
- Application 使用可注入 Clock 创建固定查询：最近 45 个日历日范围、最多 30 个 Daily Bars，结束时间至少落后当前 15 分钟。
- Tool Result 不把金融计算交给 LLM；Application 从 Historical Bars 确定性提供：Bar Count、Period Start / End、First / Latest Close、Period High / Low、Absolute Close Change、Close Change Percent 和 `UP / DOWN / FLAT` Direction。
- `price_history` Capability 改为 `AVAILABLE`；`technical_analysis` 继续为 `UNAVAILABLE`。
- 不实现 Moving Average、RSI、Support / Resistance、技术信号、预测或 BUY / SELL 规则。
- Current Quote 与 Recent Price History 共用 M3 的单一 Tool Round 和每轮最多三个调用；语义重复调用按 `(tool_name, ticker)` 去重。
- Price History Failure 与 Current Quote Failure 使用既有 Market Data Status，并使最终 Answer 确定性标记为 `DEGRADED`。
- Source Tracking 新增 `PRICE_HISTORY` 类型，复用现有 `ticker / provider / feed / market_timestamp / fetched_at` 字段，不增加新的 Response JSON 字段。

### Public API Contract Proposal

`POST /v1/investment/questions` 的 Response 结构保持不变，仅扩展：

```text
sources[].type
= PRICE_HISTORY
```

当 Price History 成功时：

- `ticker` 为规范化标的；
- `provider / feed` 保留 Alpaca / SIP；
- `market_timestamp` 使用最新一根返回 Bar 的 timestamp；
- `fetched_at` 使用 Historical Bars 的获取时间。

失败时仍返回 `PRICE_HISTORY` Source 与明确 `status`，不伪造时间或数据。

### Acceptance Criteria

- “GOOG 最近一个月走势如何？”可以只调用 `get_recent_price_history`，不机械调用 Current Quote。
- “GOOG 现在多少钱？”继续只调用 Current Quote，不机械调用 Price History。
- 一个问题可以在同一 Tool Round 同时请求 Current Quote 与 Recent Price History，且总调用数仍不超过三个。
- Historical Tool Query 使用固定窗口、注入 Clock、规范化 Ticker，模型不能自行传 start / end / limit。
- 成功 Tool Result 保留 source、feed、coverage、adjustment、timestamps，并只包含代码计算出的数值事实。
- Final Response Guard 接受 Tool 已提供的历史数值，继续阻断 Context 未提供的金融数值；显式复述相反 Direction 时产生高置信违规。
- NO_DATA、认证、限流、Provider 不可用与非法响应保持独立状态，并产生 `DEGRADED` Answer。
- Capability Manifest 中 `price_history=AVAILABLE`、`technical_analysis=UNAVAILABLE`。
- Fake LLM deterministic tests 覆盖 Tool Selection、参数校验、去重、混合 Tool Round、Source Tracking、Failure 与 Round Limit。
- Opt-in Real-Model Behavioral Eval 新增固定 Fake Historical Bars Case，人工验证模型使用历史事实但不升级为技术信号或预测。
- Existing M1–M4 Cash Adjustment、Current Quote、Guard 与 API Tests 无 Regression。

### Non-Goals

- News、Earnings、Fundamentals、Market Context / Regime 或 VIX。
- 新 Market Data Provider、付费 SIP、WebSocket、缓存或历史行情持久化。
- 用户自定义任意时间范围、分钟级 K 线或多阶段 Tool Retrieval。
- Technical Analysis、Portfolio Return、Backtest 或预测。

### Human Review Gate

该 Slice 复用 ADR 0004 已批准的 Provider 与现有 Agent 架构，不需要重新选择 Provider；但新增 `sources[].type=PRICE_HISTORY` 会扩展对外公共 API Contract，因此实现前等待 Human Review 明确批准该最小 Contract。
