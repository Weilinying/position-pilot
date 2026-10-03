# Phase 4：删除自动 Cash / 单股价格比较

2026-10-03，用户批准清理；基于 V6 AQ12 第二、三轮的真实回答证据。

## Problem

Native Amount Rule 已禁止未请求的现金/单股价格比较，但每次成功 Quote 都自动计算并输出
`cash_vs_one_share_price`，Tool Result 的 `cash_quote_relation_allowed_use=repeat_relation_only`
又允许复述。基础 Prompt、Quote / Market Tool description 和旧 Behavioral Eval 也提到该关系。
AQ12 因而在没有数量请求时仍复述 ABOVE，虽没有给出错误价格或可执行数量，仍违反 Amount Rule。
这些输入是可观察的冲突引导，不能单凭一次输出证明唯一模型 Root Cause。

## Decision

删除该内部派生字段的计算、序列化、允许复述口径及 Prompt / Tool description 正向引导。
同步清理旧 Eval 的比较要求；低/高 Cash 场景仍保留真实现金事实与个性化分析。
同一 Quote formatter 被 Legacy 与 Native 使用，两条路径一起移除，而不是按模型/Case 过滤。

该字段没有交易执行、账户 Ledger、API / UI 或独立数量计算消费者，不属于 Portfolio Source of Truth。
保留原始 Cash、Quote、按 Position Type 的 Quote / Average Cost 关系、可靠 Source、明确数量请求规则。
不新增 Prompt、数量工具、自然语言 Guard、Repair、Provider 分支或确定性 Intent Router。

## Alternatives / Trade-off

再追加禁止语句会继续让输入同时包含“应比较”和“不应比较”，因此选择减少不相关 Context。
删除字段不保证模型以后不会自行比较；自然语言质量仍须真实模型 Review。
显式数量请求仍只允许使用 Application 提供的确定性结果；Native 既有本轮预算理论数量缺口
没有在本补丁中实现，也不能由模型心算补齐。

## Verification / Future

离线验证现金高于、等于、低于 Quote 时均不注入该字段；有/无对应持仓时仍保留正确成本关系。
验证 Native Quote 与显式数量请求入口收到的 Tool Result 无旧复述口径，并保留当前数量边界。
历史计划、Artifact 和冻结 Commit 保留原状；不能把旧版本成功结果改写为新版本 Baseline。
Runtime Prompt 与 Tool description digest 随实际输入变化；后续在线验证须新建 Run，等待 Human Review。
