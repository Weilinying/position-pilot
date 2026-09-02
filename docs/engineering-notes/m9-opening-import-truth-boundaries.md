# M9 Opening Import Truth Boundaries

## Problem

Text / Screenshot Recognition、Asset Search 与 Portfolio Write 会同时产生“识别建议、外部
Asset Fact、用户确认和 Domain Fact”四种不同可信度的信息。如果不明确边界，系统容易把高
Confidence 识别结果直接当作 Portfolio Truth，或把一次性 Opening Import 扩大成需要持续
同步、冲突处理和 Reconciliation 的外部账户集成。

## Decision

- Asset Identity 以 Asset Metadata Provider 验证后的 canonical symbol 表示；Portfolio 只保存
  当前业务所需的 canonical symbol，不复制或持续同步完整 Asset Master。
- Provider-specific Asset Metadata 只存在于 Integration Adapter；Application / Domain 使用
  Provider-neutral Schema 与明确 Failure Status。
- M9 只规范化 Asset Selector 所需的 canonical symbol、display name 与 exchange；Provider exact
  validation 成功只表示能够识别并规范化 symbol，不把未明确提供的 active / inactive 状态推断为
  Domain Truth。其他 Metadata 只有出现当前界面需求时才增加，不设计通用证券主数据模型。
- Recognition 只生成可编辑 Draft。Confidence 只作为 Human Review Signal，不进入 Portfolio
  Domain，也不单独允许或阻止写入。
- 最终写入只接受用户确认后的确定字段，并重新执行 Asset Validation 与 deterministic Domain
  Validation；识别结果、Browser Suggestion 或高 Confidence 均不能绕过它们。
- Import 只复用 M8 一次性 Opening State Gate，不支持已初始化 Portfolio 的增量 Import、外部
  Account Sync、Diff、Conflict Resolution 或 Reconciliation。
- Asset Metadata Provider 与 Vision / OCR Capability 先通过短 Spike 回答 M9 的最小可行性问题，
  经 Human Review 批准选型与图片隐私边界后立即实现，不扩展成长期 Provider 研究。
- Recognition 输出始终是 Structured Draft 数据，不进入 PositionPilot Agent 的 System / User
  Instruction；通过架构边界和定向测试保证，不为此建设独立安全框架。

## Alternatives / Trade-off

- 本地完整 Asset Master 可减少 Provider Read，但会引入数据许可、同步、staleness、Corporate
  Action 与 Identifier Mapping 责任，当前 M9 不需要。
- Confidence Threshold 自动阻止或自动写入实现简单，但把 Provider-specific 概率误当作业务
  真实性，且不同 Recognition Provider 的分数不可直接比较。
- 增量 Import / Reconciliation 对已存在 Portfolio 更便利，但需要外部账户身份、幂等、冲突、
  删除 / 更正和 Accounting 语义，显著超出 Opening State 初始化闭环。

## Trigger / Future

只有出现以下真实需求时才重新评估：Asset Provider 成本或稳定性证明本地可重建 Cache / Master
必要；用户需要 Broker Sync 或周期性账户对账；Recognition Eval 证明某类 Confidence 能在已
定义 Provider / Dataset 下支持额外 UX Policy。任何演进仍不得把 Recognition Confidence 直接
升级为 Portfolio Domain Truth。
