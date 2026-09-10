# ADR 0012：来源事件派生持仓批次并显式分配卖出

**Status:** Accepted
**Date:** 2026-09-10

## Context

M9 需要在一个 ticker 下展示真实的剩余购买批次，并允许用户调整每批的策略类型。系统仍需保留
交易与资金历史，为后续已实现盈亏和账户收益率提供事实。现有 replay 只按
`(ticker, position_type)` 聚合，部分卖出按聚合成本同比例减少，无法说明卖掉了哪一批。

当前处于本地开发测试阶段，没有需要迁移的正式用户数据。为旧测试持仓推断历史批次既不可靠，
也会增加双重核算路径。

## Decision

- Position Lot 是从不可变来源事件派生的当前视图，不建立可任意覆盖的 Lot Snapshot 表。
- BUY Transaction、Opening Position 和 Position Reconciliation 的 ID 同时作为其来源 Lot ID。
  BUY 的购买时间来自 `occurred_at`；Opening / Reconciliation 未提供真实时间时保持 `UNKNOWN`。
- Reconciliation 在其生效时替换同一 `(ticker, position_type)` 的当前 Lot 集合，并生成一个新的
  聚合来源 Lot。为了避免汇总值覆盖详细购买历史，写入只允许目标当前为空或只有一个
  Opening / Reconciliation Lot；它继续不改变 Cash，也不伪造交易。
- SELL 必须显式携带一个或多个 Lot Allocation；分配股数之和必须等于成交股数。Replay 按每个
  Lot 的单位成本释放成本，不再使用聚合仓位同比例扣减。
- 用户可以调整整个剩余 Lot 的 `UNSPECIFIED / SWING / LONG_TERM` 类型。调整以不可变
  `LotClassificationChange` 记录，保留生效时间；它不改变 Cash、Ticker、股数、成本和来源交易。
- 本次不增加“批次内部分转类型”。用户需要不同策略时，通过新的买入批次或后续明确的拆分能力
  表达；当前没有必要引入 parent / child Lot 图。
- 原始成交记录保持不可变。M9 的 BUY 录入错误通过 `BuyTransactionCorrection` 引用原
  Transaction 形成有效版本并完整 replay；Correction 不作为普通买卖重复记账。SELL 更正暂不实现。
- M9 实施时重置本地测试持仓数据，从新模型重新录入，不编写旧聚合状态到 Lot 的推断迁移。

## Consequences

- 当前持仓、类型小计和 ticker 总体能从同一组事实确定性重建，交易历史仍可用于后续收益核算。
- 类型修改不会改变历史成交当时的分类；Agent 的当前 Context 使用 Lot 当前类型，历史页面仍显示
  原交易事实及其后续调整。
- 卖出录入需要用户选择批次。页面从具体批次发起卖出时自动预选该批，股票级卖出允许用户明确
  分配，系统不猜 FIFO。
- 本地开发数据库需要重建到新 Migration Head；正式发布前若出现不可清理的数据，再单独设计
  可验证的数据迁移。
- 汇总校准不能直接调整已有详细 BUY Lot；用户需在购买批次上更正成交字段，或通过新的交易表达
  持仓变化。

## Alternatives

- 直接修改聚合持仓：无法保留交易历史，也无法可靠计算已实现盈亏。
- 持久化可编辑 Lot Snapshot：会与 Transaction / Opening / Reconciliation 形成第二份事实来源。
- 默认 FIFO：用户并未选择该成本归属，且不同券商或账户的税务处置可能不同。
- 为每次类型调整拆分 Lot：当前只要求整批改类型，额外关系和校验没有已存在的需求。

## Reconsider When

当产品需要部分批次转类型、Broker Tax Lot 同步、Wash Sale、税务成本或完整 Corporate Action 时，
重新评估 Lot Split 与外部 Lot Identity；不得通过改写历史交易来补足这些能力。
