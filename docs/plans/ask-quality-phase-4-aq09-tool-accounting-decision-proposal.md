# Phase 4 AQ09 Tool Accounting Decision Proposal

**Status:** PROPOSED — HUMAN REVIEW REQUIRED（2026-09-27）

## 1. Evidence

`p4-4a-source-projection-core-1/r1` 为 `12 / 13 COMPLETED`，Repair 总计 0。
AQ09 第一轮在 `4.39s` 以 `TOOL_CALL_LIMIT_EXCEEDED` 失败。Trace 为 Quote →
自动 Market Context → 显式 Market Context → Price History；未形成 Final。
Market Provider 结果已由 `FinancialToolExecutor` 在同轮缓存，但自动取得与随后
显式请求分别消耗预算。现有代码仅处理“先显式 Market、后 Quote”的顺序。

## 2. Proposed Minimal Change

明确同轮自动补取 Market Context 与随后**第一次**显式请求该已取得结果的计数关系：

- 同一 Market Context 获取只占一次 Application Tool 预算；已自动记账的结果在首次
  显式请求时复用，不再追加第二次获取额度。相反顺序继续沿用现有行为。
- 显式模型调用与自动获取仍完整保留在 Trace 中，并明确复用关系；不能删除尝试来
  美化调用次数，也不声称缓存命中是新的 Provider 访问。复用同一 Source 身份。
- PydanticAI 的显式工具调用上限仍为 4；Application 的实际获取预算仍为 4。
  例外仅合并本轮已自动计费的 Market Context 与其首次显式复用，不能让模型任意
  重复请求免费，也不能免除新的 Quote / History / News / Market 获取的预算检查。
- 授权必须先于访问或复用；失败 / 空结果同样保留原状态，不重试获取，不跨 Run 复用。

这是对已冻结 Tool Call Accounting 的澄清，虽不提高数值上限，仍需 Human Review。
不调整模型、Provider、60 秒时限、Repair、SourceValidator 或 4A Gate。

## 3. Alternatives / Trade-off

继续依赖 Prompt 避免重复调用改动较小，但当前 Prompt 已说明 Quote 包含必要
Market Context，本次仍发生失败。直接提高工具次数会掩盖顺序相关的重复计账，
不采用。拟议方案需让 Application 与 Bridge 的预算计数一致，并保留可审计的
尝试次数与实际获取次数；不引入新缓存服务或通用调度框架。

## 4. Minimum Verification

1. 离线覆盖自动→显式、显式→自动两种顺序，成功与失败 Market 结果均保留；
   同轮真实 Provider 调用一次，显式复用有完整 Trace / Source 身份。
2. 验证第五次新的工具获取、重复显式调用及未授权调用仍受上限 / 授权约束；
   Application / Bridge / PydanticAI 计数一致，不豁免任意调用。
3. AQ06 已批准金额分析规则的实现修复不改变产品语义，可独立执行；合并必要的
   通用修复后，用户本地定向运行 AQ09 两轮与 AQ06，检查首次回答、Budget、
   失败降级及 Source；定向达标后才重新采集完整 Core 与冻结 Repeat。

**Approval requested:** 是否批准上述仅针对同轮自动 / 首次显式 Market Context
复用的预算记账澄清？
