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

修复后用户本地运行 `p4-4a-client-lifecycle / r1`，只选 AQ08、AQ20，Revision 为
`baf590341af60d2daeb717bd25ba235a93a2b888-dirty`。两例均 `COMPLETED / OK`、无 Tool Call、
无 Repair，请求成功率 `2 / 2`；Latency 分别为 `21224.5 ms`、`2592.55 ms`，Usage 仍为
`UNKNOWN`。这证明同一 Runtime 的两次连续 No-tool 在线调用可完成，**尚未验证**此前失败的
AQ07 / AQ10、Tool Loop、多轮历史或 r1 全量质量。两个回答仍保留 Human Rubric `PENDING`。

随后用户本地运行 `p4-4a-tool-history-smoke / r1`，选 AQ07、AQ10，Revision 为
`eddb467ebc0d615835ef982754ece711b210fca9-dirty`。AQ07 的 Turn 以
`TOOL_CALL_BUDGET_EXCEEDED` 结束（约 `5.67s`）；AQ10 首轮 `COMPLETED / OK`，第二轮以
`WALL_CLOCK_BUDGET_EXCEEDED` 结束（约 `30.01s`）。三个 Turn 中完成 1 个，两个 Case 均
`REQUEST_FAILED`；没有再观察到毫秒级 `PYDANTIC_AI_RUNTIME_FAILURE`。AQ07 / AQ10 第二轮的
Trace 均包含 Quote 后的两条 Market Context 记录：Application 在 discretionary Quote 时自动补取
Minimum Market Context，而模型另行请求了一次同名 Tool。FinancialToolExecutor 会复用同轮结果，
但额外的 Tool Invocation 仍占用 4 次 Tool Call Safety Ceiling。AQ07 还调用了 Price History；
AQ10 第二轮 Quote 为 `NO_DATA`，不能将其当作当前价格。两种失败分别属于预算上限与完成时限，
不是本轮已修复的异步客户端生命周期错误，也不能据此判定 PydanticAI 架构限制。

现有 4 Tool Call / 30 秒为已批准 Safety Ceiling，不在此报告中为了让 Eval 通过而提高；
需要先审查 Tool Loop 对自动补取 Context 的处理及模型最终回答路径。当前 4A Core Gate 仍未通过，
不启动完整 Primary / Repeat 付费重跑，也不进入 P4-T6～T8。

对上述系统性重复调用，Native Agent Prompt 现已补充最小契约说明：discretionary Quote Observation
中的 `required_market_context` 已包含本轮必要的 Market Context；同一问题不应再重复请求，失败时
仍保持 `UNKNOWN`。离线测试验证了该提示与自动补取结果同时存在，**尚未通过真实模型确认**它能减少
Tool Call 或使 AQ07 / AQ10 达标。该改动不回写任何历史 Artifact，也未调整已批准 Safety Ceiling。

用户随后仅重跑 AQ07（`p4-4a-native-context / aq07`，Revision
`cddab3473d31108408d38550a5507194ee4f0c0f-dirty`）：首次 Native Run 于 `21.24s`
形成候选，但候选未通过最终结构/引用校验而触发一次无 Tool Repair；Repair 在剩余约 `8.77s`
内耗尽总 30 秒，Case 仍为 `REQUEST_FAILED`。Trace 为显式 Market Context、Quote、随 Quote 自动
补取的 Market Context，说明 Prompt 澄清未阻止“先 Market Context、后 Quote”的重复记账。
当前 Artifact 未保存首次候选，尚不能确定 Repair 是 Source Ref、Citation 还是其他结构错误。

已在同一已批准预算内修正更窄的去重情形：**只有模型先显式调用 Market Context** 时，后续
discretionary Quote 复用该结果并将其包含在 Observation，不再额外记录自动 Tool Call；
模型未显式调用时，每次 Quote 仍按原 Contract 为 Quote + 必要 Market Context 预留两次调用。
原有预算回归与新增“显式先调用”回归均保留。Eval 记录器后续会保存固定 Fixture Run 的首次
Final Candidate，便于在不推测的情况下离线判定 Repair 原因；这不改变历史 Artifact。

用户在 `fee8331` 后运行 `p4-4a-aq07-rca / r1`，AQ07 仍为 `REQUEST_FAILED`。此次 Trace 恰为
Quote、自动 Market Context、News、Price History 四次调用，**没有**重复 Market Context 记账；
首次 Runtime 于 `23.88s` 返回 Final Candidate。Candidate 的 `source_refs` 对应本轮已取得来源，
inline Source ID 也与 Tool Trace 一致，但 `answer` 字符串中出现未转义的双引号，外层不是合法 JSON。
Application 因此正确触发一次无 Tool Repair；剩余 `6.13s` 耗尽 30 秒总预算，最终错误为
`WALL_CLOCK_BUDGET_EXCEEDED`（API 层映射为 `LLM_PROVIDER_UNAVAILABLE`）。这次直接触发
Repair 的是 JSON 语法错误，并非已观察到的 Source Identity 错误；也不能因 `pytest PASSED`
认定 AQ07 通过。固定 Fixture Raw Candidate 仅保存在新的
Artifact，不回写以前的 Run。

历史 M5 证据显示 Model Studio 上 `tools + response_format=json_object` 可能导致 Routing 不兼容，
因此不能简单对整个 Tool Loop 强制 JSON mode。当前结论是：自动补取重复记账已修复；
结构化 Final Candidate 的生成方式及 30 秒内 Repair 能否完成仍是独立未决项。不凭这一例直接修改
Provider 请求模式、延长已批准 Safety Ceiling 或判定 Framework 不可行。

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

已确认 AQ07 的首次候选为非法 JSON，且 Repair 耗尽剩余 Wall-clock；先评审现有
PydanticAI Final Output 能力与 M5 Provider Compatibility 证据，不再进行盲目付费复测。
必要的 Safety Ceiling 或 Tool Contract 调整须遵守已批准计划的 Human Review 边界。
之后完成必要的有效
`r1`、`r2`、`r3` 真实模型 Run；命令与 Artifact 结构见
[Evaluation README](../README.md#phase-4-4a-core-eval)。收到 `manifest.json`、`cases.jsonl`、
`summary.json` 后复核 Tool Selection / Arguments、Conversation 指代与预算更正、Source / Citation、
Provider Failure、Repair、逐 Case Rubric 和 Critical Gate，并填写质量分布、成功率、Latency 与
Usage / Cost。只有 4A Core Gate 达标并完成最终 Automated Review，才将报告更新为 Human Review
版本；在 Human Review 前不进入 P4-T6～T8。Research Provider 仍独立，Brave 缺少在线验证不阻止
Runtime / Conversation 的 Core 技术验收。
