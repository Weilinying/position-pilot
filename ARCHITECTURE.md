# PositionPilot Architecture

## 1. 当前范围

本文档描述 M1 完成后的实际系统结构。当前系统只包含工程基础与 Portfolio Structured State，不包含 REST Portfolio API、Market Data、LLM 或 Investment Agent。

## 2. 依赖方向

```text
FastAPI health endpoint

Portfolio callers
      ↓
Application / PortfolioService
      ↓
Domain / deterministic Portfolio replay
      ↑
Infrastructure / SQLAlchemy Unit of Work
      ↓
PostgreSQL User + Transaction Ledger
```

- `domain/` 不依赖 FastAPI、SQLAlchemy 或具体数据库。
- `application/` 定义写入 Command、Use Case 和 Unit of Work Protocol，只依赖 Domain。
- `infrastructure/` 实现 SQLAlchemy Model、映射与 Unit of Work，依赖 Application Contract 所需的 Domain 类型。
- `alembic/` 是唯一正常 Database Schema 变更路径。
- `main.py` 目前只暴露不耦合数据库的 `GET /health`。

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
- `backend/position_pilot/infrastructure/models.py`：User / Transaction SQLAlchemy Model 与数据库约束。
- `backend/position_pilot/infrastructure/unit_of_work.py`：同步 SQLAlchemy 持久化实现和领域映射。
- `alembic/versions/`：M1 Schema、金额舍入与手续费约束 Migration。

## 6. 当前限制

- M1 没有 Portfolio REST API 或认证；后续调用方通过 Application Service 使用 Structured State。
- 当前没有 Cash / Position Projection；只有实际性能问题出现后才考虑可重建投影或快照。
- 手续费只实现 `IBKR_PRO_TIERED_US_2026_08` 第一档基础佣金，不模拟月累计量跨档、执行场所、清算、监管或 pass-through fees。
- 不处理税费、多币种、拆股、公司行动、转仓或外部券商同步。
- 不包含 Market Data、Agent Routing、LLM 或投资建议生成。
