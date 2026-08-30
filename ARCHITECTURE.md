# PositionPilot Architecture

## 1. 当前范围

本文档描述 M8 Local Portfolio Management 当前已实现的系统结构。系统包含 immutable Opening State、Transaction / Cash Event Ledgers、Provider-neutral Market / News Data，以及可按问题选择 Current Quote、固定近期 Daily Price History、attributed Recent News 或 SPY Market Context 的 Single Investment Agent；Agent Context 同时包含由同一 State Read 生成的当前 Portfolio 与有界历史 BUY Facts。M8 在同源静态 Web Interface 中增加本地创建、恢复、起始仓位和不可变 Ledger Entry，并保持确定性 Source of Truth。

## 2. 依赖方向

```text
GET /app/ + /static/*
      ↓
Vanilla HTML / CSS / ES Modules
  ├── POST /v1/portfolios
  ├── GET /v1/portfolios/{user_id}
  ├── POST + GET /v1/portfolios/{user_id}/opening-positions
  ├── POST /v1/portfolios/{user_id}/transactions
  ├── GET /v1/portfolios/{user_id}/transactions
  ├── POST /v1/portfolios/{user_id}/cash-events
  ├── GET /v1/portfolios/{user_id}/cash-events
  └── POST /v1/investment/questions

FastAPI /health

POST /v1/investment/questions
      ↓
Application / InvestmentAgent
  ├── PortfolioService → current State + bounded historical BUY Facts
  │     ↓ SQLAlchemy UoW → PostgreSQL Ledger
  ├── Current Quote / Recent Price History Tools
  │     ↓ MarketDataService → AlpacaMarketDataProvider
  ├── Market Context Tool
  │     ↓ MarketContextService → SPY Daily Bars → deterministic V1 Heuristic
  ├── Recent News Tool
  │     ↓ NewsService → AlpacaNewsProvider → Benzinga reporting
  └── LLMProvider → AliyunLLMProvider

Portfolio callers
      ↓
Application / PortfolioService
      ↓
Domain / deterministic Portfolio replay
      ↑
Infrastructure / SQLAlchemy Unit of Work
      ↓
PostgreSQL User + Opening State + Transaction Ledger + Cash Event Ledger

POST /v1/portfolios/{user_id}/cash-events
      ↓
PortfolioService.record_cash_event
      ↓
User row lock → combined ledger replay → append Cash Event

Market data callers
      ↓
Application / MarketDataService + Provider Protocol
      ↓
Integrations / Alpaca REST Adapter
      ↓
Alpaca Market Data API v2

News callers
      ↓
Application / NewsService + NewsProvider Protocol
      ↓
Integrations / Alpaca News REST Adapter
      ↓
Alpaca `/v1beta1/news` → attributed Benzinga reporting
```

- `domain/` 不依赖 FastAPI、SQLAlchemy 或具体数据库。
- `application/` 定义 Use Case、Unit of Work、LLM 与 Tool Contract，只依赖 Domain 和 Provider-neutral Schema。
- `infrastructure/` 实现 SQLAlchemy Model、映射与 Unit of Work，依赖 Application Contract 所需的 Domain 类型。
- `integrations/` 实现外部 Provider Adapter，只向 Application 返回稳定 Market Data 或 LLM Schema。
- `alembic/` 是唯一正常 Database Schema 变更路径。
- `main.py` 暴露独立的 `GET /health`、本地 Portfolio 管理 API 与投资问答 API；外部 Provider 只在投资请求发生时延迟装配。

## 3. Portfolio Source of Truth

M4 在 M1 Transaction Ledger 基础上使用以下持久化事实：

```text
User.initial_cash
        + Opening Position Starting Facts
        + ordered Transaction Ledger
        + ordered Cash Event Ledger
        ↓ combined deterministic replay
CashBalance + Position[]
```

PostgreSQL 保存 `users`、`opening_positions`、`transactions` 与 `cash_events`。Opening Position 是系统开始跟踪时的 immutable Starting Fact，只有 `(ticker, shares, average_cost, position_type, recorded_at)`，没有经济 sequence、手续费或现金影响。Cash、当前 Position、Shares、Cost Basis 和 Average Cost 不保存冗余投影，而是在读取时合并重建。Transaction 与 Cash Event 各自维护由 `occurred_at` 派生的连续 sequence；历史补录会在同一事务内重新编号同类后续记录。跨表按 `occurred_at` 排序，同一时间固定先处理 Cash Event，再处理 Transaction。

同一 Ticker 的 `UNSPECIFIED`、`LONG_TERM` 与 `SWING` 使用独立 Position Key；`UNSPECIFIED` 只表示用户尚未提供策略分类，Agent 不得把它推断成长期仓或波段仓。BUY / SELL、DEPOSIT / WITHDRAWAL、Available Cash、Oversell 与 Average Cost 都由普通 Python / Decimal 代码计算，不依赖 LLM。Cash Event 只改变 CashBalance，不改变 Position。

## 4. Transaction 写入流程

```text
RecordTransactionCommand（无 amount / commission / sequence）
        ↓
锁定 User 数据库行
        ↓
读取完整 Ledger
        ↓
按 occurred_at 派生经济 sequence
        ↓
领域层派生 amount 与版本化 IBKR 基础佣金
        ↓
重放并校验 Cash / Position
        ↓
同一数据库事务追加 Transaction
```

User 行锁串行化同一用户的写入，避免两个并发请求基于相同旧 Cash 或 Shares 同时通过。不同 User 不共享该锁。

## 5. Cash Event 写入流程

```text
RecordCashEventCommand（DEPOSIT / WITHDRAWAL + amount + optional occurred_at）
        ↓
锁定 User 数据库行
        ↓
读取完整 Transaction 与 Cash Event Ledger
        ↓
重放并校验当前 Cash / Position
        ↓
按 occurred_at 重新派生 Cash Event sequence
        ↓
合并重放；Withdrawal 不足时失败且不追加
        ↓
同一数据库事务追加 Cash Event
```

Cash Event amount 必须为正数且最多 8 位小数。Transaction 与 Cash Event 省略 `occurred_at` 时均使用同一次 Application Clock 读数；显式时间必须带时区、规范化到 UTC，并拒绝晚于当前时间的值。Browser Clock 不作为默认 Ledger 时间来源；预约资金调整不属于当前 Ledger Contract。`initial_cash` 不在该流程中更新；Application 没有 Cash Event 更新或删除接口，领域记录使用 frozen dataclass 保持 immutable ledger semantics。

## 6. 主要模块

- `backend/position_pilot/domain/portfolio.py`：领域实体、枚举、Decimal 规则以及 Transaction / Cash Event combined replay。
- `backend/position_pilot/domain/market_context.py`：SPY Daily Price Stress 指标、确定性 Market Regime 与 V1 Heuristic 元数据。
- `backend/position_pilot/domain/news.py`：Provider-neutral News Article、归因、时间、稳定排序与 Failure Status。
- `backend/position_pilot/domain/errors.py`：明确的领域失败状态。
- `backend/position_pilot/application/portfolio_service.py`：Opening State、Transaction / Cash Event Use Case、写入 Command、Unit of Work Contract，以及同一 State Read 的 Agent Portfolio Context。
- `backend/position_pilot/application/llm.py`：Provider-neutral Message、Tool、Completion 与 Failure Contract。
- `backend/position_pilot/application/investment_agent.py`：Portfolio Snapshot、单轮 Native Function Calling、Structured Source Validation、Source Tracking 与 Request Failure。
- `backend/position_pilot/application/investment_answer.py`：自由文本 Answer 外层 JSON、统一 Source Reference Schema 与真实性校验。
- `backend/position_pilot/application/investment_context.py`：Portfolio、Quote 与 Recent Price History 的确定性事实和响应边界。
- `backend/position_pilot/application/market_context_service.py`：固定 SPY Daily 查询、completed-bar 过滤、Provider 语义校验与 Regime 计算入口。
- `backend/position_pilot/application/news_service.py`：Recent News Query 校验与 NewsProvider Contract。
- `backend/position_pilot/infrastructure/models.py`：User / Opening Position / Transaction / Cash Event SQLAlchemy Model 与数据库约束。
- `backend/position_pilot/infrastructure/unit_of_work.py`：同步 SQLAlchemy 持久化实现和领域映射。
- `backend/position_pilot/integrations/aliyun_llm.py`：阿里云 Model Studio OpenAI-compatible Adapter。
- `backend/position_pilot/integrations/alpaca_news.py`：Alpaca News beta JSON、attribution 与 Failure Mapping Adapter。
- `backend/position_pilot/bootstrap.py`：Portfolio、Market Data 与 LLM Provider 的依赖装配。
- `backend/position_pilot/demo_seed.py`：通过正式 Application Service 创建隔离本地 Demo Portfolio 的显式命令。
- `frontend/`：由 FastAPI 同源托管的无构建静态产品界面，只负责输入、状态协调和安全展示。
- `alembic/versions/`：M1 Schema、金额舍入、手续费约束、M4 Cash Event 与 M8 Opening State Migration。

## 7. 当前限制

- Portfolio 与投资问答 API 由调用方提供 `user_id`，当前没有 Authentication / Authorization；M8 推荐服务器只绑定 `127.0.0.1`，仅适合本地或受控开发环境，不应暴露到公网或不受控局域网。
- 当前没有 Cash / Position Projection；只有实际性能问题出现后才考虑可重建投影或快照。
- Cash Event 只支持 `DEPOSIT` 与 `WITHDRAWAL`；不支持 Dividend、Fee、Interest、Tax、Margin、多币种、Broker Synchronization 或投资收益率计算。
- Transaction 与 Cash Event 还没有跨表全局 sequence；相同 `occurred_at` 使用 Cash Event 优先的固定重放顺序。只有后续现金流类型或对账需求证明必要时才重新评估全局 Event Store。
- 手续费只实现 `IBKR_PRO_TIERED_US_2026_08` 第一档基础佣金，不模拟月累计量跨档、执行场所、清算、监管或 pass-through fees。
- 不处理税费、多币种、拆股、公司行动、转仓或外部券商同步。
- Current Quote 默认来自 Alpaca Basic 的实时 IEX feed，只代表单一交易所覆盖；Historical Daily OHLCV 来自至少延迟 15 分钟的 SIP feed。
- 不包含 WebSocket、行情 / 新闻缓存或持久化、通用技术指标、VIX、市场宽度、宏观 Context、News 全文抓取、Earnings 或 Fundamentals；Market Regime 仅为已批准的 SPY Daily Price Stress V1 Heuristic。
- Portfolio Snapshot 是 Agent 必定注入的完整当前持仓集合，并包含当前 Positions 对应的有界历史 BUY Facts；它不包含完整 Transaction Ledger 或 Cash Event History。每个 `(ticker, position_type)` 只保留最近 5 条 BUY，并显式声明总数与截断状态。
- 发给 LLM 的 Snapshot 不包含内部 User ID，并提供由代码计算的 Ticker 数量、总持仓历史成本和按 Ticker 聚合、保留两位小数的历史成本权重百分比。历史成本权重不包含 Available Cash，也不表示当前市值权重；原始 `LONG_TERM` / `SWING` Position 继续独立保留。
- Quote 成功后，Tool Result 向 LLM 提供实际 last / bid / ask price、Source Metadata、统一的 `CURRENT_QUOTE(ticker)` Source Reference，以及代码派生的 Cash/Quote、Quote/Average Cost 关系。Cash/Quote 关系是纯数值比较，不能支持交易执行结论，真实可执行购买数量保持 `UNKNOWN`。Portfolio Context 继续提供同 Ticker 股数汇总，并将现金权重、总组合价值、当前市值权重和缺少策略阈值时的集中度结论标为 `UNAVAILABLE` 或 `UNKNOWN`。
- 每次请求注入结构化 Context Capability Manifest。Current Quote、Price History、News、Market Context 与 Historical Buy Facts 可用；Earnings、Fundamentals、Technical Analysis、Asset Metadata 和 Sector Classification 仍不可用。
- Decision Context 将 Trading Plan、Exit Conditions 与 Risk Budget 显式标记为 `UNKNOWN`；它们不是 Conversation Memory，也不由模型从通用知识补足。
- Agent 每个请求只允许一个 Tool Round，Current Quote、Recent Price History、Recent News 与 Market Context 合计最多四个调用；仍按问题实际需要选择 Tool，不默认调用全部 Context Tools。不支持 Conversation Memory 或多阶段检索。
- Recent Price History 的窗口由 Application 固定为截至当前时间至少 15 分钟前的最近 45 个日历日、最多 30 根 Daily Bars。Adapter 使用 Provider `sort=desc` 取得窗口内最新 N 根，再反转为 Domain 要求的 timestamp 严格升序，避免较早的 N 根冒充 Recent History。LLM 只能选择 Ticker，不能控制 start、end 或 limit。Application 只提供 Bar 数量、首尾时间与收盘价、区间高低、首尾涨跌额/幅和 `UP / DOWN / FLAT` 方向；最新历史收盘价不等于 Current Quote，Price History 不提供移动平均、RSI、支撑阻力、交易信号或预测。
- Recent News 的窗口固定为截至当前时间至少 15 分钟前的最近 5 个日历日、最多 5 篇，且请求 `include_content=false`。文章只保留有界 headline、可选 summary、author、URL、reporting source、symbols 与时间戳；Provider Response 也必须服从窗口和条数上限。News Result 是 attributed reporting，不是 PositionPilot 独立验证事实。回答必须保留“来源报道声称”的归因，新闻与价格变化的关系最多是条件式 `INFERENCE`，不能确认用户的价格变化前提、唯一原因或结构化财报事实。
- `NO_NEWS_FOUND` 只表示当前 Provider 在指定 ticker 和时间窗口内没有返回文章，不表示不存在相关新闻、事件或股价驱动因素。它与认证、限流、Provider 不可用和非法响应保持不同状态。
- 所有 Final Completion 使用内部 `{answer, source_refs}` JSON。`answer` 是 LLM 自由文本，Backend 不解析其中的数字、ticker、关系或自然语言 Claim；`source_refs` 统一支持 Portfolio Snapshot、Current Quote、Price History、Recent News 与 Market Context。每个声明来源必须绑定本轮成功取得的同类型、同 ticker Context，否则进入一次 Repair / Failure。Public API 继续返回 `answer: str` 与已验证的 `sources`，不增加 inline citation 或 claim-to-evidence mapping。
- Current Quote 正确性不再依赖自然语言 Regex、同义词表或确定性 Renderer。Backend 强约束 Portfolio / Ledger / Derived Facts 和 Tool / Source 真实性；最终自然语言是否准确使用这些事实由 Prompt、Behavioral Eval 与 Human Review 衡量。成功取得但未声明使用的 Context 不进入 Final Source Tracking；失败 Tool Attempt 仍保留原 status 以维持降级可观测性，但不能被声明为成功 Source。
- 同一轮内大小写或空白不同的重复调用按 `(tool_name, ticker)` 共用一次 Provider Result，但每个 Native Tool Call 都获得对应 Tool Message。Quote、History 与 News 即使 Ticker 相同仍是三个独立来源。
- 超出 Portfolio Snapshot、成功 Current Quote、成功 Price History、attributed Recent News 与成功 SPY Market Context Tool Result 的事实保持 `UNKNOWN`；新闻报道不得自动升级为系统验证事实，Market Context Failure 时不得从其他来源补造 Regime。
- 当前仍无 Trading / Asset Metadata Context；未来 Capability 扩展点为确定性的 `tradable` 与 `fractionable`。不得由 LLM 假设整股或碎股资格，也不由 LLM 计算具体可购买股数。

## 8. Local Product Interface Boundary

```text
首次访问 / 无有效 Pointer
        ↓
Start / Recover Onboarding
        ↓ Create 或 Load 成功
Application Shell
        ├── Decision Questions：当前标签页内的独立 Question / Answer
        └── Portfolio Workspace：Positions / Transactions / Cash Activity

userIdInput ──成功 Load──> loadedUserId
     │                         │
     └──发生变化──> stale/null └──唯一允许用于 Question Request 的身份

Portfolio / Question Read Request
        ↓ capture User ID + Request Generation
Response only updates DOM when both still match current state

Mutation
        ↓ capture loadedUserId + lock identity controls
POST immutable Ledger Record
        ↓ success
GET latest deterministic Snapshot
        ↓ failure or ambiguous result
stale / refresh_required; never automatic retry
```

- `GET /app/` 与 `/static/*` 由同一 FastAPI 进程提供，Browser 调用相对路径 API，不需要 CORS、Reverse Proxy 或独立 Frontend Service。
- Browser 使用无构建的 Client-side Screen 切换：首次无有效身份时显示 Start / Recover；成功加载后进入带侧栏的 Application Shell。Decision Questions 与 Portfolio Workspace 是同一 Document 内的互斥 View，不新增前端 Router、Framework 或服务端页面。
- Decision Questions 将当前浏览器标签页内的多个 Question / Answer 作为纯 Presentation State 依次追加，并提供 Question History 跳转列表。该列表与 Answer 不写入 `localStorage`，刷新页面或切换 Portfolio Context 即清空；每个 Question 仍是独立的 Agent Request，不携带先前问答，因此不构成 Conversation Memory 或多轮模型上下文。
- Portfolio Workspace 将 deterministic Snapshot、Opening State Setup、Trade Entry 与 Cash Entry 分成 Positions / Transactions / Cash Activity 三个 Panel。Positions 在三个 Record List 都为空时提供一次性 Existing Positions Draft；Skip 只隐藏当前 UI，不持久化或封闭 Opening State。三个 Panel 同时展示完整只读记录。Initial Cash 的 UI 默认值为 `0`，表单示例带 `e.g.` / “例如”前缀；逐字段错误只负责输入可用性，最终 Ledger Validation 仍以后端为准。
- `GET /v1/portfolios/{user_id}` 直接映射 `PortfolioService.get_portfolio()` 的 Ledger Replay Result；Response 只包含 User ID、Available Cash、完整性声明和按 `(ticker, position_type)` 稳定排序的当前 Positions。Decimal 保持字符串，不返回实时价格、收益、Ledger History 或风险结论。
- `POST /v1/portfolios/{user_id}/opening-positions` 在 User Row Lock 下执行一次性 1～100 行批量写入；只有 Opening Position、Transaction 与 Cash Event 都为空时才允许，并在一个事务中全部成功或全部失败。三个对应 GET List API 返回完整只读记录；Opening Position 按 `(ticker, position_type)`，经济记录按 sequence 升序。
- Browser 显式区分输入框的 `userIdInput` 与已成功加载的 `loadedUserId`。Question 与 Ledger Mutation 只能使用后者；输入变化会立即使 Context 失效。Portfolio 与 Question 各自维护 Request Generation，旧 User 或旧 Generation 的 Read Response 不得更新 DOM。
- `POST /v1/portfolios` 只是 `PortfolioService.create_user()` 的薄 API Adapter。M8 API 中的“Portfolio”仍是现有单一 `User → Portfolio State` 模型的产品呈现，不新增独立 Portfolio Entity；Multiple Portfolios 的 Ownership / Resource Boundary 留到 V2 重新评估。
- Browser 只在成功 Create 或成功 GET 后，把最近一个 `user_id` 保存为 versioned `localStorage` pointer，并同步到 URL。pointer 不是 Credential，不保存 Snapshot、Ledger、Question、Answer 或 Secret；Forget 只清理本地引用。
- `POST /transactions` 与既有 `POST /cash-events` 都追加不可变记录。Mutation 期间 Create、Load、Forget、User ID 与重复提交被禁用；成功 Response 不用于前端推算金融状态，而是立即重新 GET Snapshot。
- Mutation Failure、连接中断或 POST 后 GET Failure 会进入 `refresh_required`。Browser 不自动 Retry；Reload 只能重新取得当前 State，无法在没有 Transaction History、Mutation ID 或 Idempotency 的 M8 中精确识别某一次不确定 POST。
- 所有 API、LLM、Provider 与用户输入产生的动态文本使用 `textContent`、DOM Property 或等价安全接口。静态 Template 之外不使用动态 HTML 字符串，也不执行 Markdown HTML。
- Source Cards 只展示后端已经验证绑定的 Source Identity / Status 和失败 Tool Attempt；Ticker、Provider、Feed、Market Time 与 Fetched At 使用显式字段标签，不等价于逐 Claim Citation，也不返回完整 Tool Payload。
- Browser 提供不持久化的中文 / 英文显示模式。切换只重绘静态标签、状态文案和本地化时间格式，不改变 `userIdInput`、`loadedUserId`、Request Generation、Agent Answer 或 Provider 原始值。
- M8 使用固定 Checklist 的 Human Browser Smoke 作为界面 Evidence，不把它描述为自动化 E2E，也不将其纳入默认 Regression Gate。Network Ambiguity、POST 后 GET Failure、XSS Payload 与 delayed stale read 属于定向 Engineering Verification / Automated Review。

## 9. Market Data Boundary

```text
Ticker / HistoricalBarsQuery
        ↓ Application validation
MarketDataProvider Protocol
        ↓
AlpacaMarketDataProvider
        ↓
MarketDataResult[MarketQuote | HistoricalBars]
```

- `domain/market_data.py` 保存 Provider-neutral Quote、OHLCV、Coverage 和 Result Status，不包含 Alpaca JSON 或 HTTP 状态码。
- `application/market_data_service.py` 校验 Ticker、时间范围和 limit，只依赖 Provider Protocol。
- `integrations/alpaca_market_data.py` 负责 Credential、REST、IEX / SIP feed、分页以及 HTTP / Payload Failure 映射。
- 正常空结果使用 `NO_DATA`；认证、限流、Provider 不可用和非法响应具有不同状态，失败结果不携带伪造数据。

## 10. News Data Boundary

```text
NewsQuery
    ↓ Application validation
NewsProvider Protocol
    ↓
AlpacaNewsProvider
    ↓
NewsResult[RecentNews]
```

- `domain/news.py` 只保存有来源归因的不可变文章事实和稳定 News Status，不包含 Alpaca JSON、Credential 或 HTTP 状态码。
- `NewsService` 校验 ticker、时区、时间范围和 limit；Agent 负责创建固定 5 日 / 5 篇窗口。
- Adapter 只请求 Metadata、headline 与 summary，不请求 `content`，并拒绝窗口外、超上限或缺少 attribution 的 Provider Response。
- `NO_NEWS_FOUND` 是局部查询结果，不是世界状态；它不会被解释成没有相关新闻、事件或驱动因素。

## 11. Market Context 与 Regime Boundary

```text
get_market_context() 无模型参数
      ↓
MarketContextService
      ↓ fixed SPY / 90 calendar days / max 60 Daily Bars / 15-minute end lag
MarketDataService → Alpaca Historical SIP
      ↓ exclude current uncompleted New York session bar
      ↓ reject latest completed bar older than 7 calendar days as NO_DATA
latest 21 completed SPY Daily Closes
      ↓ deterministic Decimal calculations
5-session Return + 20-session Close Drawdown + 20-return Annualized Volatility
      ↓ highest-severity V1 thresholds
NORMAL / ELEVATED_VOLATILITY / HIGH_STRESS / EXTREME_STRESS
```

- `domain/market_context.py` 使用固定 50 位 Decimal 中间精度，最终指标统一为百分比 4 位 Half-even，并用相同量化值分类。
- Result 保留全部原始指标、Trigger Rule、Threshold Table、Period、Observation Count、Provider、Feed、Coverage、Adjustment 与 Fetched At。
- Methodology 固定为 `V1_HEURISTIC` / `1.0`：阈值不是行业标准、未经历史回测验证，也不是投资信号；Regime 不直接生成 BUY / HOLD / SELL。
- SPY 只代表美国大盘股代理，不代表完整美股市场、VIX、市场宽度、宏观环境或个股特有风险。
- 交易时段内保守剔除仍可能变化的当前 New York Session Daily Bar；早收盘日也等到常规收盘后才纳入，优先避免把盘中数据伪装成 completed Daily Fact。
- 最新 completed Bar 超过 7 个日历日时视为明显陈旧并返回 `NO_DATA`；该工程 Freshness Heuristic 容纳正常周末和交易所假期，不尝试替代精确 Market Calendar。
- 少于 21 根 completed Bars 同样为 `NO_DATA`；认证、限流、Provider 不可用与非法成功 Payload 继续保持独立状态。
- 决策、阈值、局限与重新考虑条件见 ADR 0007。

## 12. Investment Agent 与 LLM Boundary

```text
Transaction + Cash Event Ledgers
      ↓ same-UoW deterministic Portfolio Context
Current PortfolioState + bounded Historical BUY Facts
      ↓ deterministic Snapshot
InvestmentAgent
      ↓ LLM native optional tool selection
validate minimum context floor
      ↓ only declared discretionary current risk action may add Market Context
      ↓ LLMProvider Contract
AliyunLLMProvider
      ↓ OpenAI-compatible HTTPS
Alibaba Cloud Model Studio

Final LLM {answer, source_refs}
      ↓ provider-neutral JSON_OBJECT → Aliyun response_format=json_object
      ↓ strict outer JSON parser + Source Reference validation
Free-form answer + validated Context Sources
      ↓ no natural-language claim parsing
Pass → existing answer:string API
Fail → one no-tool Repair → parse / validate sources
      ↓ still fails
LLM_INVALID_PROVIDER_RESPONSE
```

- Snapshot 明确声明 Positions 是完整当前集合；未出现的 Ticker 表示当前无持仓。Historical BUY Facts 只投影当前 Position、保持 `LONG_TERM` / `SWING` 独立并声明截断，不能用于重算当前 Shares、Average Cost、Cash 或收益。Agent 不额外执行确定性 Ticker Extraction。
- `LLMProvider` 的 Message、Tool Definition、Tool Call 与 Result 均为项目自身 Schema；Aliyun/OpenAI-compatible Payload 只存在于 Adapter。
- `deepseek-v4-pro-0813` 是可通过 `LLM_MODEL` 覆盖的默认配置，不是 Domain 或 Application 类型。
- Current Quote、Recent Price History、Recent News 或 Market Context Failure 会作为缺失事实返回 LLM，安全 Final Answer 由 Application 标记为 `DEGRADED`；LLM Failure 无法形成 Final Answer，返回 Request Failure。
- Native Function Calling 可选择四类 Context Tool，LLM 仍是 primary router，单轮总调用预算保持为 4。Market Context 是 Portfolio Risk Context / risk modifier；只有没有明确既定交易规则、并要求判断当前是否应该增加或减少风险暴露时才是 minimum context。购买能力、纯事实查询和既定规则/已决定动作的确认执行不机械调用。
- Current Quote Native Tool Call 通过 `request_purpose` 结构化声明事实查询、discretionary current risk action 或既定规则/执行检查。模型声明 discretionary action 且漏选 Market Context 时，Application 在同一 Tool Round 补足一次无参数调用；这是 model-declared floor，不解析问题关键词，也不替代模型的 Intent 判断或接管 Quote / History / News 的自主选择。
- 首轮 Native Tool Selection 通过参数校验后记录一次结构化 Trace，区分模型选择的 Tool、模型声明的安全 purpose 枚举、Required Context Floor 补足的 Tool、最终有效 Context、匹配当前持仓的 Position Type、未持有标的数量与 Routing Latency；日志不保存问题正文、User ID 或 ticker。
- 首轮 Routing Completion 使用 `LLMResponseFormat.TEXT`，允许选择 Tool 或直接形成无 Tool Answer；Tool Result 后的 Final 与 Repair 使用 `LLMResponseFormat.JSON_OBJECT`。Aliyun Adapter 映射 Provider-native JSON Mode；Parser、Source Validation 和一次 No-Tool Repair 继续作为防御层。Tool Call、Provider Failure 与 Source Contract 均未交给 JSON Mode 代替验证。
- `FACT`、`INFERENCE`、`UNKNOWN` 是回答的语义约束，不强制固定输出标题。
- 默认测试使用 Fake LLM；Opt-in Behavioral Eval 使用真实 Aliyun LLM 与固定 Fake Market Data，真实 LLM + 真实 Market Data 只用于 Smoke Test。
