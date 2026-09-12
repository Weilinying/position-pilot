# ADR 0013：由统一 Replay 派生已实现盈亏

**Status:** Accepted
**Date:** 2026-09-12

## Context

M9 已提供不可变交易、含费买入成本、实际卖出费用与显式 SELL 批次分配。M11 需要知道每次卖出
释放的成本、实际净收入与收益。当前持仓不包含已卖完的批次，不能从当前余额反推历史收益。
Human 已确认暂缓 M10 导入，M11 直接使用已有手工交易事实。

## Decision

- 唯一 `replay_portfolio()` 返回 `ReplayResult(portfolio, sell_allocation_results)`；
  `rebuild_portfolio()` 仅取 `.portfolio`，不维护另一套重放。
- SELL 分配结果包括来源批次、卖出时类型、股数、`allocated_gross_proceeds`、`allocated_fee`、
  `allocated_net_proceeds`、`released_cost` 与 `realized_pnl`。这些都是派生结果，不另存核算事实表。
- 分配金额与费用按股数占比分摊；稳定按 Lot ID 排序，最后一个分配承担 8 位 Decimal 舍入余数。
- 释放成本使用本次扣减前后 Lot 成本之差；全卖时释放全部剩余成本。保留 M9 的剩余成本算法，
  不用另外乘算的值引入尾差或重算历史手续费版本。
- 已实现盈亏 = 净收入 − 释放成本；收益率 = 已实现盈亏 / 释放成本 × 100%，分母为 0 时为空。
  聚合百分比以汇总成本作分母，仅作为卖出成本回报指标，不作为账户历史收益率。
- 收益按卖出时 Lot 的类型归属。后来的分类变更不移动历史收益；BUY 成交更正按有效事实重放，
  相关 SELL 成本与收益同时更新。保留 M9 的更正入口范围，不在此扩展 SELL Correction / Void。
- Opening、Reconciliation、出入金本身不产生交易收益。校准前 SELL 沿用当时成本，之后 SELL
  使用校准后的确认成本，不把校准差额称为盈利，不推断导入前缺失的成交历史。
- `GET /v1/portfolio/accounting` 只提供已实现收益；`/valuation` 保持行情估值；`/summary` 为首页
  聚合，同一份 ReplayResult 上计算两类结果，每个当前 ticker 只读取一次行情。
- 已实现不依赖行情成功；任一当前持仓所需行情缺失时，组合未实现、市值和交易盈亏合计为空，
  而不是返回部分总额。全清仓时未实现为 0，不请求已清仓 ticker 的行情。

## Alternatives / Trade-off

- 独立 Accounting Replay 容易与持仓在分类、生效时间、校准和舍入上分歧，因此共用 ReplayResult。
- 把收益与行情都放入 accounting API 会混合职责；独立读取保留简单边界，summary 只承担首页组合。
- 直接累计卖出量乘单位成本，可能与当前剩余成本的舍入结果不守恒；前后成本差保证原成本完整释放。
- 每次读取重新派生符合当前本地数据量；尚无性能证据要求缓存、每日快照或冗余投影。

## Reconsider When

需要账户 TWR / MWR、每日收益曲线、税务批次、公司行动或真实 Broker Sync 时，重新定义对应的
资金、历史估值及事实覆盖边界。需要 Agent 回答收益问题时复用本服务增加按需 Context，不让 LLM
自行从聊天或截图计算。
