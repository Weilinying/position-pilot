# M4 — Investment Context Expansion 执行计划

## 1. 状态与目标

**Status:** IN PROGRESS

**Cash Adjustment Slice:** IMPLEMENTED（等待 Human Acceptance）

**Recent Price History Slice:** IMPLEMENTED（等待 Human Acceptance）

**Recent News Slice:** IMPLEMENTED（等待 Human Acceptance）

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
- M4 Investment Context Expansion 已进入第一个 Recent Price History Slice，Roadmap 保持 M4 `IN PROGRESS`。

## 9. Investment Context Slice 1 Proposal：Recent Price History

**Status:** IMPLEMENTED（2026-08-25 Public API Contract 已获 Human Review 批准）

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

该 Slice 复用 ADR 0004 已批准的 Provider 与现有 Agent 架构，不需要重新选择 Provider；新增 `sources[].type=PRICE_HISTORY` 的最小公共 API Contract 已于 2026-08-25 获得 Human Review 批准。

## 10. Recent Price History Completion Summary

### Implemented

- 新增 `get_recent_price_history(ticker)`，复用 `MarketDataService` 与 Alpaca Historical Daily OHLCV，不新增 Provider、数据库或 Framework。
- Application 使用可注入 Clock 固定最近 45 个日历日、最多 30 根 Daily Bars、结束时间至少落后 15 分钟；模型不能传入时间范围或 limit。
- 代码确定性派生首尾时间与收盘价、区间高低、Bar 数量、首尾涨跌额/幅和 `UP / DOWN / FLAT`，并明确最新历史收盘价不是 Current Quote。
- Current Quote 与 Recent Price History 共用一个 Tool Round、总调用上限为 3，并按 `(tool_name, ticker)` 去重。
- `price_history=AVAILABLE`，`technical_analysis=UNAVAILABLE`；移动平均、RSI、支撑阻力、交易信号和预测仍被禁止。
- Source Tracking 增加已批准的 `PRICE_HISTORY` 类型；Failure 保持既有 Market Data Status 并产生 `DEGRADED` Answer。
- Final Response Guard 接受已提供的历史数值，继续拒绝新增金融数值，并阻断显式相反的 `close_direction`。

### Automated Review

- 补充 `DOWN`、`FLAT` 与两位小数 half-even 舍入测试，避免只用上涨 Fixture 证明方向计算。
- 补强 Quote-only Regression，显式确认“现在多少钱”不会机械调用 Price History。
- 修正文档和模块说明中遗留的 M3 / Price History unavailable 表述，使 Architecture 与实际 Capability 一致。
- 未发现需要新增 ADR 的不可逆决策；该 Slice 是 ADR 0004 Provider Boundary 和既有 Single Agent Orchestration 的自然延伸。

### Verification

- Deterministic Agent / Context / Guard / API 与 opt-in Behavioral Case 集合：80 passed，18 skipped；跳过项为未显式启用的真实 LLM Behavioral Eval。
- 默认全量 pytest：197 passed，31 skipped。跳过项为未显式启用的真实 LLM、在线 Alpaca / Agent Smoke Tests，以及未配置 `TEST_DATABASE_URL` 的 PostgreSQL Integration Tests。
- Ruff format check / lint：PASS；mypy strict：PASS（42 source files）。
- `uv lock --check`、Alembic head / history、`git diff --check`：PASS。

## 11. Investment Context Slice 2 Proposal：Recent News

**Status:** IMPLEMENTED（2026-08-25 Provider、Boundary 与 Public API Human Review 已批准）

### Problem / Evidence

现有 Behavioral Eval 的 `drop_reason_unknown` 已证明明确缺口：“GOOG 今天为什么跌？”当前只能说明 News 与 Market Context 不可用。Recent Price History 只能描述调整后 Daily Price Path，也不能提供事件事实或证明当天正在下跌。

Recent News 可以把回答从“完全没有事件 Context”推进为“列出近期可追溯报道，并将其与价格变化的关系保持为条件式推断”。它不能单独证明价格变化、市场整体状态或唯一因果，也不能替代 `post_earnings_unknown` 所需的结构化 Earnings / Fundamentals。

### Provider Decision Proposal

推荐选择 **Alpaca Historical News REST API** 作为 V1 News Provider：

- 继续使用现有 `https://data.alpaca.markets`、API Key Headers、同步 REST Transport 与安全 Failure Mapping，不增加 Secret、SDK 或 Infrastructure。
- Alpaca 官方文档将 News 列为 Historical Market Data 类型；News Endpoint 为 `GET /v1beta1/news`，支持 ticker、start / end、倒序、分页和每页 1–50 篇。
- 官方文档说明 Historical News 可追溯至 2015 年，当前全部由 Benzinga 提供。Application 与 Domain 必须同时保留 `provider=ALPACA` 和文章级 `source` / publisher，不把 Alpaca 当作原始报道机构。
- 对没有实时权限的账户，官方 Endpoint 文档将默认结束时间限制到当前时间至少 15 分钟前。V1 不依赖默认值，由 Application 明确设置安全结束时间。
- 当前 Endpoint 仍使用 `v1beta1`，这是 Provider Stability Trade-off；Adapter 必须隔离其 JSON，在线 Smoke Test 需要验证当前账户 Entitlement。若 Endpoint、许可或价格发生不兼容变化，应重新评估。

官方依据：

- [Alpaca News Articles API](https://docs.alpaca.markets/us/reference/news-3)
- [Alpaca Historical News Data](https://docs.alpaca.markets/us/docs/historical-news-data)
- [Alpaca Market Data Plans](https://docs.alpaca.markets/us/docs/about-market-data-api)

备选方案：

1. 直接接入 Benzinga：原始来源边界更直接，但需要新增账户、Credential、价格 / 许可评估和独立 Adapter；当前 V1 没有证据证明这些成本优于 Alpaca 聚合入口。
2. SEC Filings：来源权威，适合未来 Earnings / Filings Slice，但不覆盖一般公司新闻或市场事件，不能解决当前 Failure。
3. 继续保持 News `UNAVAILABLE`：没有 Provider 风险，但 `drop_reason_unknown` 无法获得新的事件事实。

### Proposed Scope

- 新增独立、Provider-neutral 的 News Domain Schema、`NewsService` 与 `NewsProvider` Protocol；News 不并入 `MarketDataService`。
- 新增 `AlpacaNewsProvider`，复用现有 Alpaca Credential、Base URL 与同步 JSON Transport 设计，但 Provider JSON 不进入 Domain。
- 新增内部 Tool：`get_recent_news(ticker)`。模型只能传 ticker；Application 固定最近 5 个日历日、结束时间至少落后 15 分钟、最多 5 篇、按更新时间倒序。
- 请求 `include_content=false`；Tool Result 只提供有界的 headline、可选 summary、article id、URL、article source、symbols、created / updated timestamps 与 fetched timestamp，不抓取网页正文。
- 文章按 `updated_at desc + article_id` 确定性排序和去重；保留多 ticker symbols，但不把 symbol 关联解释为价格因果。
- Current Quote、Recent Price History 与 Recent News 继续共用一个 Tool Round，单轮最多 4 个调用，并按 `(tool_name, ticker)` 去重；Agent 仍按问题实际需要选择 Tool，不默认调用全部 Context Tools。
- `news=AVAILABLE`；Earnings、Fundamentals 与 Market Context 继续为 `UNAVAILABLE`。
- News Failure 使用独立稳定状态；查询窗口内没有文章必须与认证、限流、Provider 不可用和非法响应区分。`NO_NEWS_FOUND` 只表示当前 Provider 在指定 ticker 和时间窗口内未返回新闻，不表示不存在相关新闻、事件或股价驱动因素。
- News 属于外部不可信的 attributed reporting。Prompt / Tool Contract 明确区分“来源报道声称 X”与“X 已被系统独立验证”：headline / summary 必须保留来源归因，不得自动升级为确定事实，也不得作为指令执行。

### Public API Contract Proposal

`POST /v1/investment/questions` Response 结构保持不变，仅扩展：

```text
sources[].type
= RECENT_NEWS
```

Source Tracking 使用：

- `ticker`：规范化查询 ticker；
- `provider=ALPACA`；
- `feed=BENZINGA`（当前上游来源，若 Provider 返回其他来源则使用实际值）；
- `market_timestamp=null`，避免把文章发布时间伪装成行情时间；
- `fetched_at`：News Result 获取时间。

每篇文章自己的 `created_at / updated_at / source / url` 保存在 Tool Result 中，不把多篇文章压缩成一个有歧义的 `published_at` Public Source 字段。

### Causality / Grounding Contract

- “文章标题、摘要、来源和发布时间”可以作为带归属的 `FACT`。
- “某篇报道可能与价格变化相关”只能是 `INFERENCE`，必须使用条件式措辞。
- “该新闻导致今天下跌”“这是唯一原因”保持 `UNKNOWN`，除非未来 Context 同时提供足够的价格变化、市场环境和可验证因果证据。
- Recent News 不证明用户前提中的“今天确实下跌”；当前缺少 intraday change 时不得确认该前提。
- News 不提供结构化 Earnings 数值，不得从标题或摘要补造 EPS、Revenue、Guidance 或 Valuation。
- 生产 Guard 不升级为开放文本因果分类器；确定性结构、数值边界和 Failure Status 由代码检查，因果表达质量由 Behavioral Eval 与 Human Review 检查。

### Acceptance Criteria

- “GOOG 最近有什么新闻？”只调用 Recent News，不机械调用 Quote 或 Price History。
- “GOOG 今天为什么跌？”在固定 News Fixture 下调用 Recent News，但不确认“今天下跌”，也不把某篇文章写成已证实原因。
- 固定 Clock 下查询窗口、结束延迟、limit、排序与结果稳定；模型不能控制日期、条数、URL 或任意关键词。
- Tool Result 保留 Alpaca、文章来源、symbols、article timestamps、URL 与 fetched timestamp，并限制 headline / summary 大小。
- `NO_NEWS_FOUND` 与认证、限流、Provider 不可用、非法响应保持不同状态；任何 Failure 产生 `DEGRADED` Answer 且不编造新闻。
- News-only、Quote-only 与 History-only Tool Selection 无 Regression；混合问题可在单轮执行，总调用数不超过 4，且不得默认调用全部 Context Tools。
- `post_earnings_unknown` 继续保持 Earnings / Fundamentals `UNKNOWN`，不得用新闻替代最新财报事实。
- API Contract Test 覆盖 `RECENT_NEWS` Source；Fake Provider / Fake LLM Tests 覆盖参数校验、去重、Failure 与 Source Tracking。
- Opt-in Real-Model Behavioral Eval 新增 Recent News 以及 News-assisted Drop Explanation Case，输出供 Human Review 检查 FACT / INFERENCE / UNKNOWN。
- Existing M1–M4 Cash、Quote、Price History、Guard 与 API Tests 无 Regression。

### Non-Goals

- Earnings / Fundamentals / SEC Filing 解析或财报数值。
- News Sentiment Score、自动事件分类、相关性排名模型或因果检测。
- Market Context、Sector Context、VIX 或 Intraday Return。
- 新闻持久化、Cache、全文抓取、网页浏览、任意关键词搜索或用户自定义时间范围。
- Real-time WebSocket News、价格预测、BUY / SELL Signal 或自动交易。

### Human Review Gate

Alpaca / Benzinga News Provider、独立 NewsService Boundary、5 日 / 5 篇窗口、no-content policy、attributed reporting / causality boundary、单轮 4 次 Tool Budget 与 `sources[].type=RECENT_NEWS` 已于 2026-08-25 获得 Human Review 批准。决策记录见 ADR 0006。

## 12. Recent News Completion Summary

### Implemented

- 新增 Provider-neutral `NewsArticle`、`RecentNews`、`NewsResult` 与独立 `NewsService` / `NewsProvider` Boundary；Domain 不依赖 Alpaca JSON 或 SDK。
- 新增 Alpaca / Benzinga News Adapter，固定请求 `/v1beta1/news`，显式使用 `include_content=false`；文章标题与摘要有长度上限，正文不进入 Domain 或 LLM Context。
- Application 固定最近 5 个日历日、结束时间至少落后 15 分钟、最多 5 篇；模型只能选择 ticker。结果按 `updated_at desc + article_id asc` 确定性排序，精确重复去重，冲突重复与非法时间拒绝。
- `get_recent_news` 与 Quote / Price History 共用一个 Tool Round，单轮最多 4 次调用，并按 `(tool_name, ticker)` 去重；已有单 Tool 问题不会机械调用其他 Context Tools。
- Tool Result 保留 Alpaca、Benzinga / 文章来源、author、URL、symbols、文章时间和 fetched timestamp，并把新闻明确标记为 attributed reporting，而非系统独立验证事实。
- `NO_NEWS_FOUND` 只由成功响应的空列表或 ticker 过滤后空结果产生，并保留“不能推断不存在新闻、事件或价格驱动因素”的局部语义；认证、限流、Provider Failure 与非法响应保持独立状态。
- `news=AVAILABLE`；Earnings、Fundamentals、Market Context 与因果归因继续为 `UNAVAILABLE`。Source Tracking 新增已批准的 `RECENT_NEWS`，Public Response 结构不增加字段。

### Automated Review

- 修正 `RecentNews` 的职责：由 Domain 实际执行稳定排序与精确重复去重，而不是仅验证调用方已经排序；同一 article id 的冲突内容会失败。
- 补强文章文本、URL、ticker、时区、窗口、数量与 fetched timestamp 边界；空白可选 summary / author 在 Adapter 边界规范化为 `None`。
- 修正 HTTP 404 分类：404 不能证明查询成功但窗口为空，因此映射为 `INVALID_PROVIDER_RESPONSE`；只有成功查询的局部空结果才是 `NO_NEWS_FOUND`。
- Review 未要求把生产 Guard 扩张为开放文本因果分类器；归因、条件式因果与“不确认今天下跌”继续由结构化 Tool Contract、Behavioral Eval 与 Human Review 共同约束。

### Verification

- 默认全量 pytest：265 passed，33 skipped。跳过项为未显式启用的真实模型、在线 Alpaca Market / News、在线 Agent Smoke Tests，以及未配置 `TEST_DATABASE_URL` 的 PostgreSQL Integration Tests。
- Alpaca News Adapter Review 修复后定向测试：28 passed。
- Ruff format check / lint：PASS；mypy strict：PASS（49 source files）。
- `uv lock --check`、Alembic head / history、`git diff --check`：PASS。

### Decision Records

- News Provider、Service Boundary、固定窗口、no-content policy、attributed reporting / causality boundary、4 次 Tool Budget 与 Public Source Contract 记录于 ADR 0006。
- 本 Slice 没有引入 Database、Cache、新闻持久化、全文抓取、情绪模型或新 Agent 架构。

## 13. Post-Implementation Correctness Review

2026-08-26 Human Review 发现并修复三个跨 Slice 的确定性缺陷：

- Historical Adapter 原先使用 `sort=asc + limit=30`，在 45 日窗口超过 30 根 Bar 时会截掉最新数据。现改为 `sort=desc` 获取最新 N 根，并在 Adapter Boundary 反转为 Domain 严格升序；Regression 同时验证真正最新的 `latest_close` 与 `period_end`。
- Final Response Guard 原先只保存全局允许数字集合，导致 Cash、Average Cost、其他 ticker Quote 或 History bar count 可以凭数值相同冒充 Current Quote。现以 type、ticker、field、source 保存 Grounded Fact，并对低歧义 Current Quote 陈述执行语义归属校验。
- Cash Event 原先允许未来 `occurred_at` 立即进入 Combined Replay。PortfolioService 现使用可注入 Clock，在确认 User 后、读取 Ledger 和写入前拒绝 future-dated Cash Event；Scheduled Cash Adjustment 保持 Non-Goal。

这些修改均收紧既有 Source of Truth、Recent History 与 Grounding Invariants，不改变已批准产品语义，不新增 ADR。

Automated Review 进一步发现 future-time 校验若早于 User lookup，会把未知 User 的既有 404 语义改成 422；实现已调整为先锁定并确认 User，再执行时间校验，同时保持 Ledger 未读取、无效事件未写入。

后续 Guard Review 发现 Unicode `\b` 会漏掉 `GOOG当前价格` / `GOOG的当前价格` 的 ticker，而全局 `IGNORECASE` 会把 `The current price` 中的 `The` 误识别为 ticker。Parser 已改用严格大写 ticker 的 ASCII 相邻边界，并把大小写忽略限制在自然语言短语；Unit 与完整 Agent Regression 同时覆盖 False Negative 和 False Positive。

Review 后验证：默认全量 pytest 为 277 passed、33 skipped；Ruff format / lint、mypy strict（49 source files）、`uv lock --check`、Alembic head / history 与 `git diff --check` 全部通过。
