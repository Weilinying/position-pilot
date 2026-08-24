# PositionPilot Architecture

## 1. 当前范围

本文档描述 M3 实现中的实际系统结构。当前系统包含工程基础、Portfolio Structured State、最小 Market Data，以及 Single Investment Agent 的第一个端到端 Vertical Slice。

## 2. 依赖方向

```text
FastAPI /health

POST /v1/investment/questions
      ↓
Application / InvestmentAgent
  ├── PortfolioService → SQLAlchemy UoW → PostgreSQL Ledger
  ├── MarketDataService → AlpacaMarketDataProvider
  └── LLMProvider → AliyunLLMProvider

Portfolio callers
      ↓
Application / PortfolioService
      ↓
Domain / deterministic Portfolio replay
      ↑
Infrastructure / SQLAlchemy Unit of Work
      ↓
PostgreSQL User + Transaction Ledger

Market data callers
      ↓
Application / MarketDataService + Provider Protocol
      ↓
Integrations / Alpaca REST Adapter
      ↓
Alpaca Market Data API v2
```

- `domain/` 不依赖 FastAPI、SQLAlchemy 或具体数据库。
- `application/` 定义 Use Case、Unit of Work、LLM 与 Tool Contract，只依赖 Domain 和 Provider-neutral Schema。
- `infrastructure/` 实现 SQLAlchemy Model、映射与 Unit of Work，依赖 Application Contract 所需的 Domain 类型。
- `integrations/` 实现外部 Provider Adapter，只向 Application 返回稳定 Market Data 或 LLM Schema。
- `alembic/` 是唯一正常 Database Schema 变更路径。
- `main.py` 暴露独立的 `GET /health` 与开发用投资问答 API；外部依赖只在投资请求发生时延迟装配。

## 3. Portfolio Source of Truth

M1 使用以下持久化事实：

```text
User.initial_cash
        +
ordered Transaction Ledger
        ↓ deterministic replay
CashBalance + Position[]
```

PostgreSQL 只保存 `users` 与 `transactions`。Cash、Position、Shares、Cost Basis 和 Average Cost 不保存冗余投影，而是在读取时按每个 User 的连续经济 sequence 重建。sequence 由 `occurred_at` 派生；历史补录会在同一事务内重新编号后续记录。

同一 Ticker 的 `LONG_TERM` 与 `SWING` 使用独立 Position Key。BUY / SELL、Available Cash、Oversell 与 Average Cost 都由普通 Python / Decimal 代码计算，不依赖 LLM。

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

## 5. 主要模块

- `backend/position_pilot/domain/portfolio.py`：领域实体、枚举、Decimal 规则和 Ledger 重放。
- `backend/position_pilot/domain/errors.py`：明确的领域失败状态。
- `backend/position_pilot/application/portfolio_service.py`：Use Case、写入 Command 和 Unit of Work Contract。
- `backend/position_pilot/application/llm.py`：Provider-neutral Message、Tool、Completion 与 Failure Contract。
- `backend/position_pilot/application/investment_agent.py`：Portfolio Snapshot、单轮 Native Function Calling、Source Tracking 与 Request Failure。
- `backend/position_pilot/infrastructure/models.py`：User / Transaction SQLAlchemy Model 与数据库约束。
- `backend/position_pilot/infrastructure/unit_of_work.py`：同步 SQLAlchemy 持久化实现和领域映射。
- `backend/position_pilot/integrations/aliyun_llm.py`：阿里云 Model Studio OpenAI-compatible Adapter。
- `backend/position_pilot/bootstrap.py`：Portfolio、Market Data 与 LLM Provider 的依赖装配。
- `alembic/versions/`：M1 Schema、金额舍入与手续费约束 Migration。

## 6. 当前限制

- 投资问答 API 由调用方提供 `user_id`，当前没有 Authentication / Authorization，只适合本地或开发环境。
- 当前没有 Cash / Position Projection；只有实际性能问题出现后才考虑可重建投影或快照。
- 手续费只实现 `IBKR_PRO_TIERED_US_2026_08` 第一档基础佣金，不模拟月累计量跨档、执行场所、清算、监管或 pass-through fees。
- 不处理税费、多币种、拆股、公司行动、转仓或外部券商同步。
- Current Quote 默认来自 Alpaca Basic 的实时 IEX feed，只代表单一交易所覆盖；Historical Daily OHLCV 来自至少延迟 15 分钟的 SIP feed。
- 不包含 WebSocket、行情缓存或持久化、技术指标、VIX、Market Regime、News 或 Fundamentals。
- Portfolio Snapshot 是 M3 必定注入的完整当前持仓集合，不默认包含 Transaction History。
- 发给 LLM 的 Snapshot 不包含内部 User ID，并提供由代码计算的 Ticker 数量、总持仓历史成本和按 Ticker 聚合、保留两位小数的历史成本权重百分比。历史成本权重不包含 Available Cash，也不表示当前市值权重；原始 `LONG_TERM` / `SWING` Position 继续独立保留。
- Quote 成功后，Application 自动提供 Cash 与单股价格、当前价格与各 Position Average Cost 的确定性关系；真实可执行购买数量始终保持 `UNKNOWN`。LLM 不自行计算未提供的金融数值。
- 每次请求注入结构化 Context Capability Manifest。M3 只有 Current Quote 数据来源可用；Price History、News、Earnings、Fundamentals、Market Context、Technical Analysis、Asset Metadata 和 Sector Classification 均不可用。
- Agent 每个请求只允许一个 Tool Round，每轮最多三个 Current Quote；不支持 Conversation Memory 或多阶段检索。
- 同一轮内大小写或空白不同的重复 Ticker 共用一次 Market Provider Result，但每个 Native Tool Call 都获得对应 Tool Message。
- 超出 Portfolio Snapshot 与 Current Quote 的当前事实保持 `UNKNOWN`。
- M3 尚无 Trading / Asset Metadata Context；未来 Capability 扩展点为确定性的 `tradable` 与 `fractionable`。当前不得由 LLM 假设整股或碎股资格，也不由 LLM 计算具体可购买股数。

## 7. Market Data Boundary

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

## 8. Investment Agent 与 LLM Boundary

```text
PortfolioState
      ↓ deterministic Snapshot
InvestmentAgent
      ↓ LLMProvider Contract
AliyunLLMProvider
      ↓ OpenAI-compatible HTTPS
Alibaba Cloud Model Studio
```

- Snapshot 明确声明 Positions 是完整当前集合；未出现的 Ticker 表示当前无持仓。M3 不额外执行确定性 Ticker Extraction。
- `LLMProvider` 的 Message、Tool Definition、Tool Call 与 Result 均为项目自身 Schema；Aliyun/OpenAI-compatible Payload 只存在于 Adapter。
- `qwen3.7-plus` 是可通过 `LLM_MODEL` 覆盖的默认配置，不是 Domain 或 Application 类型。
- Market Data Failure 会作为缺失事实返回 LLM，安全 Final Answer 由 Application 标记为 `DEGRADED`；LLM Failure 无法形成 Final Answer，返回 Request Failure。
- `FACT`、`INFERENCE`、`UNKNOWN` 是回答的语义约束，不强制固定输出标题。
- 默认测试使用 Fake LLM；Opt-in Behavioral Eval 使用真实 Aliyun LLM 与固定 Fake Market Data，真实 LLM + 真实 Market Data 只用于 Smoke Test。
