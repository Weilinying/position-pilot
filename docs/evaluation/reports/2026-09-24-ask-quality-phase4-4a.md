# Ask Quality Phase 4 — 4A Core Evidence Report

**Status:** EVIDENCE COLLECTION IN PROGRESS（2026-09-24）；不是 4A Gate PASS，也尚未提交最终 Human Review。

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

## 3. 尚未取得的 4A 证据

| Gate / 指标 | 当前状态 | 收口要求 |
|---|---|---|
| 13 个 Core Primary Case 请求、逐 Case Rubric | `NOT_RUN / NOT_EVALUATED` | 用户本地真实模型 Run 后按批准最低分人工审阅 |
| AQ03、AQ05、AQ06、AQ07、AQ17a / b 的 r2 / r3 | `NOT_RUN` | 每次独立过线，不取最佳结果 |
| AQ12、AQ18 Protected；AQ04 Diagnostic | `NOT_EVALUATED` | 保留未解冲突及 Earnings 能力边界 |
| Critical Failure | `NOT_EVALUATED`，不是 0 | 完成逐 Case Human Gate，任何 FAIL 阻止 4B |
| Latency median / max、Usage、Cost | 4A Core `NOT_MEASURED` | 从真实运行 Artifact 汇总；Usage 缺失保持 UNKNOWN |
| Open Research AQ01 / AQ02 / AQ19 | `NOT_MEASURED` | T4R 独立决策；不阻塞 Core，不需要 Brave Key |

AQ06 按 [金额分析规则修订](../ask-quality-policy-revision-2026-09-20.md) 审阅：普通金额建议不以
碎股权限验证为前提；Cash 与本轮 Budget 分开，不提高 Budget，不把理论股数声称为账户实际可执行
订单，也不修改 Ledger。历史 Phase 2 / Phase 3 评分不因此回写。

## 4. 下一步与 Human Gate

用户在本地完成 `r1`、`r2`、`r3` 真实模型 Run；命令与 Artifact 结构见
[Evaluation README](../README.md#phase-4-4a-core-eval)。收到 `manifest.json`、`cases.jsonl`、
`summary.json` 后复核 Tool Selection / Arguments、Conversation 指代与预算更正、Source / Citation、
Provider Failure、Repair、逐 Case Rubric 和 Critical Gate，并填写质量分布、成功率、Latency 与
Usage / Cost。只有 4A Core Gate 达标并完成最终 Automated Review，才将报告更新为 Human Review
版本；在 Human Review 前不进入 P4-T6～T8。Research Provider 仍独立，Brave 缺少在线验证不阻止
Runtime / Conversation 的 Core 技术验收。
