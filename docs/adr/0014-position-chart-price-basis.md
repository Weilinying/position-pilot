# ADR 0014：持仓图表的价格与成本口径

**Status:** Accepted
**Date:** 2026-09-12

## Context

M13 需要把 Portfolio 交易记录放到历史日 K 上。现有 Alpaca 历史行情明确使用 `ALL` 复权，
而 Portfolio Ledger 保存用户录入或券商导入的实际成本。系统尚未记录拆股、分红等公司行动，
因此仅凭行情的 `adjustment` 无法证明历史 K 线价格与账本成本可以直接比较。

如果把未经对齐的 Average Cost 画到复权 K 线上，拆股等场景会产生错误位置和误导性的视觉结论。
M13 的目标是查看走势和自己的交易日期，不扩展公司行动核算。

## Decision

- Chart Application 继续通过 Provider-neutral `MarketDataService` 读取日 K；Alpaca Adapter 明确发送
  `adjustment=all`，Chart API 返回实际 `adjustment`、source、feed、coverage、currency、行情时间与
  `fetched_at`，前端不建立第二套行情来源。
- `1M / 3M / 6M / 1Y` 是由 Application 层解析的日历范围。`anchor_date` 是纽约市场日历日期的
  查询窗口锚点；它不要求当天存在 Bar，也不移动到最近交易日。
- BUY / SELL Marker 只使用有效交易的纽约市场日期，并放在对应 K 线上下；记录的成交价或含费
  买入成本只出现在详情中，不决定 Marker 的 Y 轴位置。缺少对应 Bar 时保留原日期并明确标记，
  不移动到相邻交易日。
- Opening Position 与 Reconciliation 不冒充真实 BUY Marker。BUY Correction 使用 Replay 所采用的
  当前有效交易；SELL 详情继续使用同一 ReplayResult 的分配结果。
- Average Cost Line 只有在 Portfolio Cost Basis 与 Chart Price Basis 有明确对齐依据时才允许显示。
  当前系统没有该依据，因此有持仓时返回 `cost_basis_comparable=false` 与
  `UNVERIFIED_PRICE_BASIS`；完全清仓时返回 `NO_CURRENT_POSITION`。前端仅把 Shares、Average Cost
  与 Cost Basis 显示为记录成本，不叠加到价格轴，也不提供手工强制开启。
- Chart ticker 身份沿用 M9 Asset Identity。访问权限必须由当前 Session 用户已有的 Portfolio 或
  Transaction 事实证明；Chart Service 不维护第二套 symbol identity，也不提供任意股票浏览。

## Alternatives / Trade-off

- 改用 `RAW` 日 K 仍不能修复账本未记录公司行动的问题，也会失去现有系统统一的复权历史口径。
- 根据当前价格或拆股比例猜测历史成本会新增无法审计的金融事实，因此不采用。
- 现在实现 Corporate Action Accounting 会显著扩大范围，并涉及新的事实来源、Replay 事件与迁移；
  M13 不为成本线引入这些能力。
- 完全隐藏成本会丢失用户已有的持仓事实。单独显示“记录成本”保留有用信息，同时避免把它与图表
  价格轴表示成已验证可比。

## Reconsider When

系统引入可审计的 Corporate Action Facts、券商同步提供明确的调整后成本，或行情服务能返回与
特定 Portfolio Cost Basis 一一对应且可验证的价格口径时，重新定义可比性证明并增加成本线测试。
若以后开放任意股票浏览，应另建产品入口与访问语义，不扩张当前 Portfolio Chart Contract。
