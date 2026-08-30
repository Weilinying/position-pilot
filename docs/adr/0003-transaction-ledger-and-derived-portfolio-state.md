# ADR 0003：Transaction Ledger 与派生 Portfolio State

## 状态

已接受（2026-08-20，2026-08-21 与 2026-08-30 修订）

## 背景

M1 需要持久化 User、Transaction、Cash 和 Position，并保证 Shares、Average Cost 与 Available Cash 由确定性代码产生。`ROADMAP.md` 将 Position Persistence Strategy 留到 M1 决定。

M1 设计阶段发现，当时 `PROJECT.md` 的 Transaction 示例同时包含 `price`、`shares` 和 `amount`，但示例数值不满足 `amount = price × shares`。如果允许三者独立输入，Cash 与 Average Cost 将存在多个相互冲突的事实来源。接受本 ADR 后，`PROJECT.md` 示例已同步修正为派生金额。

M8 需要接收系统开始跟踪前已经存在的仓位。把这些仓位伪造成历史 BUY 会虚构交易时间、手续费和现金变化，因此 2026-08-30 修订引入独立 immutable Opening State，并允许仓位策略尚未分类。

## 候选方案

### Portfolio State 持久化

- Transaction Ledger 作为持久化 Source of Truth，Cash 与 Position 按需重建。
- 同时持久化 Transaction、Cash 和 Position，并在同一事务中维护投影。
- 只持久化当前 Cash / Position，不保留完整 Transaction Ledger。

### Transaction Amount

- 由 `price × shares` 派生，只读返回。
- 允许用户独立输入 amount，并校验与乘积一致。
- amount 作为现金变化的独立事实，price 与 shares 只描述成交信息。

### Transaction 顺序与手续费

- `sequence` 表示按交易发生时间排列后的经济顺序，并在历史交易插入后重新派生。
- `sequence` 表示数据库追加顺序，历史交易只能追加到 Ledger 尾部。
- 由调用方显式提供顺序，并把顺序正确性委托给调用方。

手续费采用用户确认的 [IBKR Pro Tiered 美国股票第一档公开费率](https://www.interactivebrokers.com/en/pricing/commissions-stocks.php)，并将计算结果与费率版本一同持久化。IBKR Tiered 的执行场所、清算、监管与 pass-through fees 依赖实际成交信息或可变化费率，不在 M1 推测。

## 决策

- User 持久化 `initial_cash`，Transaction 使用不可变 Ledger 持久化。
- Cash、Position、Shares、Cost Basis 和 Average Cost 从 User、Opening State 与经济 Ledger 确定性重建；不建立冗余 Cash / Position 投影表。
- Opening Position 只保存系统开始跟踪时的 ticker、shares、average cost、可选 position type 与后端记录时间；它没有经济 sequence、手续费或现金影响，也不是 Transaction。
- Opening State 只允许在尚无 Opening Position、Transaction 或 Cash Event 时，在 User Row Lock 下进行一次 1～100 行原子初始化；任何已有事实都会自然封闭该入口。
- 写入 Transaction 的 Command 只接收 `price` 和 `shares`，不接收 `amount`。
- `amount` 由 `price × shares` 计算，作为只读派生字段写入 Transaction Record，并可返回给后续 API、前端或用户展示。
- `sequence` 不属于用户输入；它是按 `occurred_at` 升序排列后的只读连续序号。同一时间的交易保持原 Ledger 相对顺序；插入历史交易时，后续序号允许重新派生。
- 金融数值使用 `Decimal`；数据库使用 `NUMERIC(28, 8)`。输入最多接受 8 位小数，派生结果按 8 位小数使用银行家舍入。
- `commission` 不属于用户输入。M1 使用版本化费率 `IBKR_PRO_TIERED_US_2026_08`：月交易量第一档的普通整股订单按每股 USD 0.0035、每单最低 USD 0.35、最高成交金额 1% 计算；含小数股的订单按成交金额 1% 与 USD 0.01 的较大值计算。
- M1 的 `commission` 只表示 IBKR 基础佣金，不包含执行场所、清算、监管、pass-through fee、税费或月累计量跨档。
- BUY 从 Available Cash 扣减 `amount + commission`，并将手续费计入 Cost Basis；SELL 增加 `amount - commission`，手续费不改变剩余 Position 的 Average Cost。
- BUY 不得超过 Available Cash；SELL 不得超过同一 Ticker、同一 Position Type 的 Shares。
- 部分 SELL 不改变剩余 Position 的 Average Cost；全部卖出后移除该 Position。
- `UNSPECIFIED`、`LONG_TERM` 与 `SWING` 按 `(ticker, position_type)` 独立维护；`UNSPECIFIED` 只表示用户未提供策略分类，不自动归入其他类型。
- 写入 Transaction 时锁定 User 记录，并在同一数据库事务中读取 Ledger、校验和追加 Transaction，串行化同一用户的资金与持仓变更。

## 理由

- 不保存冗余 Cash / Position 投影可以避免 Ledger 与投影形成两个可能漂移的 Source of Truth。
- Transaction Ledger 天然满足可追溯与持久化恢复要求，且 M1 数据规模不需要提前优化重放性能。
- 独立 Opening State 可以表达真实起始持仓而不虚构 BUY、手续费或现金历史，同时仍保留单一确定性 replay 路径。
- 不接受 amount 输入可以从接口结构上消除冲突，而不是依赖调用方始终正确传值。
- 经济顺序从交易发生时间派生，使历史补录可以触发正确的 Cash、Shares 与 Average Cost 重放，而不会把数据库写入时刻误当成交易事实。
- 将手续费与费率版本作为不可变派生事实持久化，可以避免未来费率变化改写历史 Portfolio。
- Decimal 和固定精度数据库字段可以避免浮点误差进入金融事实。
- 按 User 加锁比提前引入 Queue、事件系统或复杂并发控制更符合 M1 规模。

## Trade-off

- 读取 Portfolio 时需要重放该用户的 Transaction Ledger，数据量增长后可能需要可重建投影或快照。
- amount 与 price / shares 同时持久化存在派生数据重复，但能够保留稳定的只读交易金额并支持直接展示；写入路径必须始终由领域代码生成。
- M1 只模拟已批准的 IBKR Pro Tiered 第一档基础佣金，不重建券商实际账单；税费、汇率、拆股、转仓和公司行动仍需未来扩展 Ledger 事件类型与计算规则。
- 插入历史交易需要重放完整 Ledger 并重新派生后续 sequence；当前数据量下优先保证经济语义正确。
- User 级锁会串行化同一用户的 Transaction 写入，但不会阻塞不同用户，足以满足当前可靠性目标。
- Opening State 没有历史交易日期、税务 lot 或券商对账信息；它只能作为开始跟踪时的聚合起始事实。需要这些语义时应增加经过批准的新事件模型，而不是反向伪造 Transaction。

## 重新考虑条件

- Ledger 重放造成已测量的延迟或资源问题。
- 后续 Milestone 需要高频 Portfolio 查询，并证明可重建 Cash / Position Projection 有明确价值。
- 产品需要实际 IBKR 月累计量跨档、第三方费用、税费、公司行动、多币种或外部券商对账。
- 真实并发负载证明 User 级行锁成为瓶颈。
