# M4 Cash Adjustment Ledger 延伸

## Problem

M1 建立 Portfolio 时只保存 `initial_cash` 与不可变 Transaction Ledger，并将 Portfolio 创建后的追加投资预算需求延期。进入 M4 前，真实使用需要支持后续入金与资金取出；如果直接修改 `initial_cash`，历史上的 Portfolio 起点会随当前操作变化，无法回答资金何时进入或离开，也会破坏 ledger replay 的可追溯性。

## Decision

保留 `initial_cash` 的创建时语义，新增独立、不可变的 Cash Event Ledger。当前只允许 `DEPOSIT` 与 `WITHDRAWAL`，每条记录保存正数金额和实际发生时间。Available Cash 从 Initial Cash、Cash Events 与 Transactions 确定性重建，Cash Event 不改变 Position。

“实际发生时间”表示写入时已经发生的 Ledger Fact。Application 使用可注入 Clock 拒绝未来 `occurred_at`，因此 future-dated DEPOSIT 不会提前增加当前购买力，future-dated WITHDRAWAL 也不会提前减少现金。预约入金或出金若未来需要，应建立独立 Scheduled Cash Adjustment 概念，不能把计划记录写成已经发生的 immutable Cash Event。

现有 Transaction 佣金语义继续有效，因此实际计算为：

```text
available_cash
= initial_cash
+ total_deposits
- total_withdrawals
- total_buy_amount
- total_buy_commission
+ total_sell_amount
- total_sell_commission
```

Cash Event 与 Transaction 按 `occurred_at` 合并重放。同一时间戳缺少跨表全局 sequence；当前采用 Cash Event 先于 Transaction 的固定顺序，各自 Ledger 内继续使用稳定 sequence。这一规则只解决确定性重放，不表示两类业务事实被合并成同一记录类型。

## Alternatives / Trade-off

- 修改 `initial_cash` 实现简单，但会覆盖历史事实并失去资金流可追溯性，因此不采用。
- 把 DEPOSIT / WITHDRAWAL 表示成 BUY / SELL 会污染交易语义、制造虚假 Ticker / Position，因此不采用。
- 建立单表全局 Event Store 可以天然提供跨类型顺序，但需要迁移或重写 M1 Transaction Contract，超出当前 Slice 的最小范围。
- 独立 Ledger 需要 combined replay；当前数据规模尚不证明需要 Cash Projection、Event Bus 或快照。

## Trigger / Future

当需要 Dividend、Interest、Tax、Fee、Broker Synchronization、多币种或收益率计算时，应重新评估 Cash Event taxonomy、跨类型全局顺序与现金流分类；不得在本 Slice 中提前加入这些类型。只有 combined replay 出现已测量性能问题时，才评估可重建 Projection 或 Snapshot。
