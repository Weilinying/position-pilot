# Conversation 租约与 Native wall-clock 的测试盲区

## Problem

Native 正式 wall-clock 已调整为 60s，但 ConversationService 构造默认仍是 30s，Production
Bootstrap 也未覆盖。模型在 35s 或 57.32s 内成功返回后，完整 Thread Ask 仍可能因
`run_deadline_at` 到期而收敛为 `AGENT_RUN_ABANDONED`，不保存成功回答。

既有 4B StrategyFixture 的 Conversation Clock 固定为 `store.now`，实际模型耗时则由
`monotonic()` 统计。它可以验证策略生命周期，却不能证明完整 Ask 的真实超时正确性。
Gemini 有限回归 AQ14 的 57.32s 是该边界值得修复的证据，不是在生产已观察到丢失回答的证明。

## Decision

正式 Native 总预算 60s 提取为 Application-owned 共享常量。Conversation 默认和 Production
装配都采用总预算加明确的 5s 准备/收尾余量，当前租约 65s。该余量不增加 Model Request / Tool
次数、不提供 Retry，也不延长 Native 或 Provider HTTP 的预算；HTTP Timeout 可小于总预算，
因此不作为 Turn 租约来源。65s 是有界的中断恢复租约，不是 Production SLO，也不保证任意
数据库阻塞或系统时钟调整下仍能完成。

补充推进 Clock 的确定性离线测试：35s / 57.32s 的慢成功可保存 Answer 与 Sources，运行期间
Thread 读取和并发提交不能提前 abandon；60s / 64.99s 覆盖收尾区间；65s 及之后仍拒绝迟到
回答，不写 Assistant / Sources。已完成结果按原 request id 幂等返回，显式短租约覆盖保留。
Production 装配测试独立确认单次 HTTP Timeout 为 10s / 60s 时 Turn 都为 65s。

## Alternatives / Trade-off

只改成 60s 会消除 30s 截断，却让从 Turn 创建开始的计时与稍后开始的 Runtime 计时贴边竞争。
不移除超时判断、不接受已被收敛的迟到结果，避免破坏每个 Thread 单一 RUNNING Turn 及中断
恢复语义。本次不增加心跳、数据库迁移或新的配置入口，不回写已创建 Turn 的 deadline。

## Trigger / Future

历史 Phase 4 / Gemini 报告、分数、Artifact 与冻结 Candidate 保留，不以本次补测改写历史结论。
本次源码修复不属于旧冻结 Candidate；未来若批准新的在线验收，需基于新源码另行冻结。
固定 Clock 的 Eval 不宣称覆盖真实 deadline；新增超时行为必须由推进 Clock 的确定性测试证明。
如真实运行证明 5s 准备/收尾余量不足，再依据实际耗时调整租约设计，不预先扩展 Runtime。
Research 保持 `DEFERRED`，本次不执行在线请求。
