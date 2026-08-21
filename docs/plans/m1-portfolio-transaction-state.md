# M1 — Portfolio & Transaction State 执行计划

## 1. 状态与目标

本计划基于 M0 已验收的 FastAPI、SQLAlchemy、PostgreSQL、Alembic 和测试工具链，执行 M1 Structured State。

M1 的目标是在不依赖 LLM 的情况下，可靠维护并恢复 User、Transaction、Cash 和 Position，不实现 M2 市场数据或 M3 Agent 能力。

## 2. 已批准语义

- Transaction Ledger 与 User Initial Cash 是持久化事实。
- Cash 与 Position 从 Ledger 确定性重建，不建立冗余投影表。
- Transaction 写入只接收 price / shares，amount 只读派生并持久化。
- sequence 按 occurred_at 派生为经济顺序，不接受用户输入；历史补录会重新派生后续序号。
- commission 按版本化 IBKR Pro Tiered 美国股票第一档规则只读派生并持久化。
- 金融数值使用 Decimal 与 `NUMERIC(28, 8)`，最多 8 位小数。
- BUY 检查 Available Cash，SELL 检查同 Position Type 的 Shares。
- 部分 SELL 不改变 Average Cost，全部卖出移除 Position。
- `LONG_TERM` / `SWING` 按同一 Ticker 独立维护。
- 具体理由和 Trade-off 见 ADR 0003。

## 3. Scope

- 建立无 ORM 依赖的领域实体、枚举、异常和 Portfolio 重放计算。
- 建立不含 amount 输入字段的 Application Command 与 Portfolio Service。
- 建立 SQLAlchemy User / Transaction Model 与 Unit of Work。
- 通过 User 行锁保证同一用户 Transaction 写入的并发正确性。
- 创建非破坏性 Alembic Migration。
- 覆盖核心金融计算、错误处理、持久化恢复和 Position Type 隔离测试。
- 记录 M1 后的实际模块边界。

## 4. Non-Goals

- 不建立 Cash / Position 物化投影表。
- 不实现 REST Portfolio API、认证、前端或用户管理界面。
- 不处理 IBKR 月累计量跨档、第三方费用、税费、汇率、拆股、公司行动、转仓或多币种。
- 不实现 Market Data、LLM、Investment Agent、News 或 Agent Tool。
- 不进入 M2 或后续 Milestone。

## 5. Acceptance Criteria

- 同一 Ticker 的 `LONG_TERM` / `SWING` 可以独立 BUY / SELL。
- BUY / SELL 后 Shares、Cost Basis、Average Cost 和 Available Cash 正确。
- Transaction amount 只能由 price / shares 派生，写入 Command 不含 amount。
- Transaction commission 只能由已批准的费率规则派生，写入 Command 不含 commission。
- Transaction sequence 按经济时间连续派生，写入 Command 不含 sequence。
- Insufficient Cash、Oversell、非法数值和未知 User 有明确失败状态。
- Transaction 按稳定顺序可追溯，Portfolio 可从 PostgreSQL 持久化状态恢复。
- 两个真实 PostgreSQL Transaction 并发写入同一用户时，第二个写入等待 User 行锁，并在获取锁后基于最新 Ledger 重新校验。
- Database Schema 只通过 Alembic Migration 创建。
- pytest、Ruff format / lint、mypy 与 PostgreSQL 在线验证通过。
- 没有 M2 或未来能力。

## 6. 执行顺序

```text
T1 领域模型与确定性 Portfolio 重放
  ↓
T2 Application Service 与 Unit of Work Contract
  ↓
T3 SQLAlchemy Models / Repository / Migration
  ↓
T4 Unit 与 PostgreSQL Persistence Tests
  ↓
T5 全量 Tests / Quality Checks / 在线 Migration
  ↓
T6 主线程 Automated Review → 修复 → 再验证
  ↓
Atomic Commits → Human Acceptance
```

M1 的核心计算、应用写入和持久化接口互相依赖，默认由主线程串行实现，避免并行修改同一领域边界。

## 7. Completion Summary

**Status:** DONE（Human Acceptance：2026-08-21）

### Implemented

- Transaction Ledger 与 User Initial Cash 作为持久化 Source of Truth。
- `LONG_TERM` / `SWING` 独立 Position，以及确定性的 Cash、Shares、Cost Basis 和 Average Cost 重放。
- `amount = price × shares` 的只读派生、持久化和数据库约束。
- 按 `occurred_at` 派生的经济 sequence，以及历史交易补录后的稳定重新编号。
- 版本化 IBKR Pro Tiered 美国股票第一档基础佣金；BUY 手续费计入 Cost Basis，SELL 手续费从现金收入扣除。
- PostgreSQL User 行锁保护同一用户写入，并由真实双事务集成测试验证等待和提交后重新校验。
- 非破坏性 Alembic Migration、SQLAlchemy Unit of Work 和 PostgreSQL 持久化恢复。

### Plan Adjustments

- 原计划将手续费列为 Non-Goal；Human Review 后根据明确需求将版本化 IBKR 基础佣金纳入 M1。
- 原实现的 sequence 表示 Ledger 写入顺序；Human Review 后改为只读派生的经济交易顺序。
- 并发验证由仅检查 `for_update=True` 的 Unit Test 补强为真实 PostgreSQL transaction integration test。

### Deferred

- Cash Adjustment、税费、汇率、拆股、公司行动、转仓和多币种。
- IBKR 月累计量跨档、执行场所、清算、监管和 pass-through fees。
- Cash / Position 物化投影、Portfolio REST API、认证和用户管理界面。
- Market Data、LLM、Investment Agent、News 和 Agent Tool。

### Verification

- pytest：37 passed，包含 6 个 PostgreSQL integration cases。
- Ruff format：PASS。
- Ruff lint：PASS。
- mypy strict：PASS。
- Alembic：在线升级至 `20260821_0003`，offline SQL 生成通过，`alembic check` 无待生成变更。
- Docker Compose config 与 `uv sync --frozen`：PASS。
- 主线程 Automated Review findings 已修复并完成受影响检查的复验。

### Decision

- ADR 0003：Transaction Ledger、派生 Portfolio State、经济 sequence 与版本化基础佣金。
