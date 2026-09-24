# Ask Quality Phase 4 — 4A Core Evidence Report

**Status:** R1 ROOT CAUSE ANALYSIS IN PROGRESS（2026-09-24）；不是 4A Gate PASS，也尚未提交最终 Human Review。

## 1. 范围与历史边界

本报告使用 `ask-quality-discovery / 0.2` 目标 Manifest、既有 `0.1` 固定 Fixture 和 Rubric `0.1`；
Phase 1～3 的 Baseline、评分与原始 Artifact 不改写。4A Core 为 AQ03、AQ05～AQ12、AQ17a / b、
AQ18、AQ20，共 13 个执行变体。AQ04 保持 Earnings `DIAGNOSTIC`。独立 Open Research Gate 的
AQ01、AQ02、AQ19 因 T4R 未批准而为 `DIAGNOSTIC / NOT_MEASURED`，不计入 Core 分母，也不归因于
PydanticAI Runtime 失败。4B Strategy AQ13～AQ16 未进入本阶段。

## 2. 已验证的工程能力

- Production Bootstrap 使用 PydanticAI；用户在本地执行的固定模型 `qwen3.7-max` No-tool、One-tool、
  Multi-tool Compatibility Smoke 为 `3 / 3`，但 Provider 未报告 Token Usage，按 `UNKNOWN` 记录。
- Conversation 的 Account Ownership、Revision、Idempotency、失败 Turn、History、Source 与 Citation
  边界已通过定向自动测试；隔离 PostgreSQL Integration `2 / 2`。旧单问 API 与 Portfolio / 确定性金融
  计算相关回归 `93 / 93`。这些证据不能替代真实模型回答质量评分。
- Dataset 0.2 Eval 入口的离线 Contract `6 / 6`；它使用固定金融 Fixture 与 Native Agent 路径，
  不复用旧 `0.1` Current Runtime 执行器。未显式 Opt-in 时 Core 为 `NOT_RUN`，Research 为
  `NOT_MEASURED`，Usage 保持 `UNKNOWN`。
- 浏览器工程 Smoke 使用标明 `ENGINEERING_SMOKE_FAKE_AGENT` 的本地替身，实际检查了注册、
  Portfolio 初始化、两轮 Thread Ask、刷新恢复、切换会话与 Citation 展示。删除 API 生命周期由
  TestClient 检查；浏览器删除确认弹窗中断了 UI 自动化，不能声称 UI 删除已通过。工程替身不模拟
  PostgreSQL 并发、真实模型或 Research 质量。

## 3. R1 真实模型证据与待排查失败

用户在本地执行 `p4-4a-local / r1`，固定 `qwen3.7-max`、Alibaba Model Studio 北京 Endpoint，
Artifact 位于 `build/evaluation-runs/p4-4a-local/r1/`。Run Revision 为
`0b904615a76c91cb3ae2e410fef182f67a2a3046-dirty`；原始 `manifest.json`、`cases.jsonl`、
`summary.json` 保持不变。`pytest PASSED` 仅表示采集器完成并写入 Artifact，不是质量 Gate PASS。

13 个 Core Primary Case 中，4 个 `COMPLETED`、9 个 `REQUEST_FAILED`；Core 请求成功率为
`4 / 13 = 30.77%`，Turn 成功率为 `5 / 18 = 27.78%`。AQ04 Earnings Diagnostic 亦为
`REQUEST_FAILED`。已完成的 Core 为 AQ06、AQ08、AQ17b、AQ20；它们仍需逐 Case Rubric 与
Critical Gate 人工审阅，不能据此认定回答质量通过。全部 19 个已执行 Turn 的 Latency 中位数
`8146.5 ms`、最大值 `30013.05 ms`；Usage / Cost 为 `UNKNOWN`，Repair 总数为 4。

失败不能笼统归因为框架：逐 Turn 有 13 次 `LLM_PROVIDER_UNAVAILABLE`、1 次
`TOOL_CALL_LIMIT_EXCEEDED`；底层 Runtime Call 记录有 10 次
`PYDANTIC_AI_RUNTIME_FAILURE`、3 次 `WALL_CLOCK_BUDGET_EXCEEDED`、1 次
`TOOL_CALL_BUDGET_EXCEEDED`。部分 `PYDANTIC_AI_RUNTIME_FAILURE` 在约 5～8 ms 内发生，
不符合普通在线模型延迟。当前 Adapter 将底层未分类异常收敛为错误码，Artifact 不能对这 10 次失败
逐一精确归因。本地无模型调用的 HTTP 实验复现了同一 Async Client 跨 `asyncio.run` 复用时的
`Event loop is closed`，与毫秒级失败且随后可能恢复的模式吻合。Production Adapter 已改为每次
Run 在同一 Event Loop 内创建、使用并关闭 Provider Client；连续调用离线回归通过。这是已验证的
客户端生命周期修复，不等于 r1 所有失败均已定因或在线问题已解决。30 秒 Wall-clock 和 Tool-call
Budget 仍需分别评估；先做最小定向在线复测，暂不进行 r2 / r3 或完整 Primary 重跑，也不把
Adapter Bug 判为 PydanticAI 架构限制。

## 4. 尚未取得的 4A 证据

| Gate / 指标 | 当前状态 | 收口要求 |
|---|---|---|
| 13 个 Core Primary Case 请求、逐 Case Rubric | r1 已运行；`4 COMPLETED / 9 REQUEST_FAILED`，Rubric `NOT_EVALUATED` | 先完成失败 RCA 与有效 Primary，再按批准最低分人工审阅 |
| AQ03、AQ05、AQ06、AQ07、AQ17a / b 的 r2 / r3 | `NOT_RUN` | 每次独立过线，不取最佳结果 |
| AQ12、AQ18 Protected；AQ04 Diagnostic | `NOT_EVALUATED` | 保留未解冲突及 Earnings 能力边界 |
| Critical Failure | `NOT_EVALUATED`，不是 0 | 完成逐 Case Human Gate，任何 FAIL 阻止 4B |
| Latency median / max、Usage、Cost | r1 已测 Latency `8146.5 / 30013.05 ms`（全部 19 Turn）；Usage / Cost `UNKNOWN` | 失败 RCA 后复核可比性；Usage 缺失保持 UNKNOWN |
| Open Research AQ01 / AQ02 / AQ19 | `NOT_MEASURED` | T4R 独立决策；不阻塞 Core，不需要 Brave Key |

AQ06 按 [金额分析规则修订](../ask-quality-policy-revision-2026-09-20.md) 审阅：普通金额建议不以
碎股权限验证为前提；Cash 与本轮 Budget 分开，不提高 Budget，不把理论股数声称为账户实际可执行
订单，也不修改 Ledger。历史 Phase 2 / Phase 3 评分不因此回写。

## 5. 下一步与 Human Gate

先由用户在本地做连续调用的最小定向在线复测，确认客户端生命周期修复；再对残留的
30 秒 Wall-clock、Tool-call Budget 和其他失败做分层 RCA。之后完成必要的有效
`r1`、`r2`、`r3` 真实模型 Run；命令与 Artifact 结构见
[Evaluation README](../README.md#phase-4-4a-core-eval)。收到 `manifest.json`、`cases.jsonl`、
`summary.json` 后复核 Tool Selection / Arguments、Conversation 指代与预算更正、Source / Citation、
Provider Failure、Repair、逐 Case Rubric 和 Critical Gate，并填写质量分布、成功率、Latency 与
Usage / Cost。只有 4A Core Gate 达标并完成最终 Automated Review，才将报告更新为 Human Review
版本；在 Human Review 前不进入 P4-T6～T8。Research Provider 仍独立，Brave 缺少在线验证不阻止
Runtime / Conversation 的 Core 技术验收。
