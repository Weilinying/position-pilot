# ADR 0011：使用不可变 Position Reconciliation 校准已有持仓

**Status:** Accepted
**Date:** 2026-09-09

## Context

M9 原有 Opening Import 只能表达系统开始跟踪前的一次性起始事实。已有 Portfolio 的券商截图可能
显示与本地状态不同的当前 Shares 与 Average Cost，但把差额伪造成 BUY / SELL 会虚构成交价格、
手续费、时间和 Cash 变化；原地修改 Opening Position 或 Transaction 又会破坏历史可追溯性。

截图还是部分视图：没有出现某个持仓不能证明该持仓已经清仓。因此校准不能用截图集合覆盖完整
Portfolio，也不能自动推导缺失的交易历史。

## Decision

- 新增不可变 `PositionReconciliation` 事件，保存 `ticker`、`position_type`、`target_shares`、
  `target_average_cost`、`confirmed_at`、`source` 与可选 `broker / source_info`。
- 同一份用户确认的截图以一个数据库事务追加全部行；不修改 Opening Position、Transaction 或
  Cash Event 历史。
- Replay 把 Reconciliation 与 Cash Event / Transaction 按实际时间合并。遇到 Reconciliation 时，
  直接把对应 `(ticker, position_type)` 的 Shares 与 Cost Basis 校准为目标值；之后的 Transaction
  按原有规则继续生效。
- Reconciliation 不生成 BUY / SELL、不修改 Available Cash；截图中未出现的 Position Key 保持
  不变。
- 跨表时间相同时采用 `Cash Event → Position Reconciliation → Transaction` 的固定顺序，使 Replay
  保持确定性。
- Recognition 仍只生成 Browser Draft。用户必须确认字段与 Provider-validated Asset Binding 后，
  才能追加 Reconciliation。

## Consequences

- Portfolio State 仍可完全从不可变事实确定性重建，同时允许已有持仓被当前券商聚合值校准。
- Reconciliation 表达的是用户确认时的目标聚合状态，不是交易、tax lot、realized P&L 或券商持续
  同步记录；Cash 可能不会与券商账户的完整历史自动一致。
- 多次校准同一 Position Key 会按确认时间依次覆盖目标状态，历史事件仍可审计。

## Alternatives

- **生成差额 BUY / SELL：** 会虚构经济事实并错误影响 Cash，拒绝。
- **原地更新 Opening Position 或当前投影：** 失去历史可追溯性，并形成第二个不可 Replay 的
  Source of Truth，拒绝。
- **截图集合覆盖整个 Portfolio：** 无法区分“截图未包含”与“已经清仓”，拒绝。
- **接入 Broker Sync：** 需要外部账户身份、幂等、删除、更正和冲突语义，超出 M9。

## Reconsider When

只有当产品需要真实 Broker Connection、完整 Transaction / Tax Lot 导入、清仓表达或自动冲突
解决时，才重新评估事件结构；不得用这些未来需求反向改变当前截图校准的事实语义。
