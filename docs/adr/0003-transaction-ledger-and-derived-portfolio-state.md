# ADR 0003：Transaction Ledger 与派生 Portfolio State

## 状态

已接受（2026-08-20）

## 背景

M1 需要持久化 User、Transaction、Cash 和 Position，并保证 Shares、Average Cost 与 Available Cash 由确定性代码产生。`ROADMAP.md` 将 Position Persistence Strategy 留到 M1 决定。

`PROJECT.md` 的 Transaction 示例同时包含 `price`、`shares` 和 `amount`，但示例数值不满足 `amount = price × shares`。如果允许三者独立输入，Cash 与 Average Cost 将存在多个相互冲突的事实来源。

## 候选方案

### Portfolio State 持久化

- Transaction Ledger 作为持久化 Source of Truth，Cash 与 Position 按需重建。
- 同时持久化 Transaction、Cash 和 Position，并在同一事务中维护投影。
- 只持久化当前 Cash / Position，不保留完整 Transaction Ledger。

### Transaction Amount

- 由 `price × shares` 派生，只读返回。
- 允许用户独立输入 amount，并校验与乘积一致。
- amount 作为现金变化的独立事实，price 与 shares 只描述成交信息。

## 决策

- User 持久化 `initial_cash`，Transaction 使用不可变 Ledger 持久化。
- Cash、Position、Shares、Cost Basis 和 Average Cost 从 User 与 Transaction Ledger 确定性重建；M1 不建立冗余 Cash / Position 投影表。
- 写入 Transaction 的 Command 只接收 `price` 和 `shares`，不接收 `amount`。
- `amount` 由 `price × shares` 计算，作为只读派生字段写入 Transaction Record，并可返回给后续 API、前端或用户展示。
- 金融数值使用 `Decimal`；数据库使用 `NUMERIC(28, 8)`。输入最多接受 8 位小数，派生结果按 8 位小数使用银行家舍入。
- M1 不计算手续费。BUY 从 Available Cash 扣减 amount；SELL 增加 amount。
- BUY 不得超过 Available Cash；SELL 不得超过同一 Ticker、同一 Position Type 的 Shares。
- 部分 SELL 不改变剩余 Position 的 Average Cost；全部卖出后移除该 Position。
- `LONG_TERM` 与 `SWING` 按 `(ticker, position_type)` 独立维护。
- 写入 Transaction 时锁定 User 记录，并在同一数据库事务中读取 Ledger、校验和追加 Transaction，串行化同一用户的资金与持仓变更。

## 理由

- 不保存冗余 Cash / Position 投影可以避免 Ledger 与投影形成两个可能漂移的 Source of Truth。
- Transaction Ledger 天然满足可追溯与持久化恢复要求，且 M1 数据规模不需要提前优化重放性能。
- 不接受 amount 输入可以从接口结构上消除冲突，而不是依赖调用方始终正确传值。
- Decimal 和固定精度数据库字段可以避免浮点误差进入金融事实。
- 按 User 加锁比提前引入 Queue、事件系统或复杂并发控制更符合 M1 规模。

## Trade-off

- 读取 Portfolio 时需要重放该用户的 Transaction Ledger，数据量增长后可能需要可重建投影或快照。
- amount 与 price / shares 同时持久化存在派生数据重复，但能够保留稳定的只读交易金额并支持直接展示；写入路径必须始终由领域代码生成。
- M1 不处理手续费、税费、汇率、拆股、转仓和公司行动；这些能力出现真实需求后需要扩展 Ledger 事件类型与计算规则。
- User 级锁会串行化同一用户的 Transaction 写入，但不会阻塞不同用户，足以满足当前可靠性目标。

## 重新考虑条件

- Ledger 重放造成已测量的延迟或资源问题。
- 后续 Milestone 需要高频 Portfolio 查询，并证明可重建 Cash / Position Projection 有明确价值。
- 产品需要手续费、税费、公司行动、多币种或外部券商对账。
- 真实并发负载证明 User 级行锁成为瓶颈。
