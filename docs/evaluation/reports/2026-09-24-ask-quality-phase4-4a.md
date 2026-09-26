# Ask Quality Phase 4 — 4A Core Evidence Report

**Status:** AQ07 REQUEST COMPLETED / ANSWER QUALITY OPEN（2026-09-26）；
不是 4A Gate PASS，也尚未提交最终 Human Review。

## 1. 范围与历史边界

### 2026-09-26 备选模型入口诊断

`p4-4a-alt-model-smoke-1/r1` 显式选择 `qwen3.7-max-2026-05-17`，只运行 AQ20。
Core Eval 已接受该模型名并将其记录在 Run Metadata；AQ20 在 `0.65s` 后
`REQUEST_FAILED / LLM_INVALID_REQUEST`，Runtime Trace 为
`FAILED / MODEL_HTTP_FAILURE`，未执行 Tool、未产生回答或 Token Usage。
因此该结果只证明当前 Model / Endpoint / Request 组合未成功，不能为 AQ20 打质量分，
也不能把失败归因于 Portfolio 或 Conversation 行为。现有 Artifact 未保存精确 HTTP 状态及
Provider 错误码；`LLM_INVALID_REQUEST` 对应适配器中的非认证类 4xx 映射，尚不能判定
是模型权限、具体请求字段还是快照兼容性。该模型是仅支持思考模式的早期快照；
与 `qwen3.7-max` 历史运行分别归因，不合并成功率。继续完整 Core 前须先确认实际
Provider 错误码及该快照在当前 Region / Endpoint 下的请求兼容性。

同一轮 Review 发现 `p4-4a-core-progress/r1` 的 AQ04 Record 已正确写成
`REQUEST_FAILED / MEASURED`，但旧 Summary 仅按完成数量判断，误标 `NOT_RUN`。
现已修复后续汇总：Earnings Diagnostic 分别记录完成、请求失败和未运行数量；
已尝试而失败时 `evidence_status=MEASURED`。旧 Artifact 原样保留，不回填历史结果。

AQ09 的两个 Turn 均未完成，但阶段不同：首轮 Quote / History 为 `NO_DATA`，News 为
`NO_NEWS_FOUND`，模型仍把这些无结果来源放入 `source_refs`；Application 正确触发一次
无 Tool Repair，Repair 由 Runtime 返回 `INVALID_PROVIDER_RESPONSE`，没有可复核的候选输出。
第二轮初始模型请求耗时约 `44.18s`，候选缺少已成功 Market Context 的 inline Citation；
Repair 在剩余约 `15.82s` 内超时。无法从现有 Artifact 推定首轮 Repair 的 Provider 原始
响应形状。针对可确定的 Source 干扰，Native 失败 / 空结果 Observation 不再生成可引用
`source_id`，但保留失败状态与内部审计记录；一次 Repair 和拒绝失败来源的规则不放宽。
该修复只有离线验证，不能据此声称 AQ09 在线通过。

### 2026-09-26 Native Context 修复（待在线验证）

**后续证据与第二次修复：** `p4-4a-aq07-context-fix/r1` 在 `32.78s` 内完成，无 Repair。
实际回答已纠正浮盈 / Thesis 与 100% 成本占比推论，也包含 LONG_TERM / 假设 SWING 条件分析；
但仍把固定执行数量 UNKNOWN 列为暂缓因素，故不能认定 AQ07 质量通过。
Native Quote 现在不再输出 `executable_purchase_quantity`：行情本身不能提供账户执行事实，
无需新建意图分类器或按关键词裁剪。用户明确问执行权限时，仍遵守无可靠依据则 UNKNOWN、
不得从 Quote 声称可执行的 Prompt / Contract。Cash / 成本关系与旧 Runtime 保持不变。
普通行情、权限提问及加仓自动 Market Context 路径的实际 Observation 已有离线断言；
Native / 旧 Runtime 定向测试共 97 项通过，Ruff / Format / mypy 通过。
新的在线验证目录为 `p4-4a-aq07-quote-scope/r1`；此前 Artifact 不覆盖。

集中审查发现 Native 复用的 Quote Observation 仍含
`required_purchase_execution_status: UNKNOWN`，与普通金额分析不要求执行权限的产品规则
存在指令冲突。Native 在构造 Observation 时移除该强制报告要求，改为仅在用户询问执行能力或
账户权限时报告；执行能力 UNKNOWN、禁止无依据订单执行结论、Cash / Budget 与来源边界均保留。
Current Runtime 的序列化与 Prompt 不变。不增加意图分类器、重试或超时。

同时明确浮盈不证明用户长期 Thesis 正确，以及排除 Cash 的持仓成本占比不等于全部资产占比；
成本占比已为 100% 时，不得把绝对敞口增加说成该口径比例继续提高。离线测试检查实际 Native
Quote Observation，而非只检查 Prompt 文本；真实模型是否遵守这些语义仍须单独验证。
本次不修改历史 Artifact、Rubric 或 Critical Gate，也不将来源身份校验等同于推论质量通过。

下一次定向 Run 使用新目录 `p4-4a-aq07-context-fix/r1`，选择 AQ07，保持既有固定模型及 60 秒
预算。验收同时检查请求完成、Repair、耗时、来源和实际回答：无无关执行权限前置、无虚构 Thesis、
无占比口径混淆，并有实质条件分析而非只把判断退回用户。定向结果通过后再补完整 Core / Repeat；
本修复不代表 AQ07 或 4A Human Gate 已通过。

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
完整 AQ07 中结构化 Final Candidate 的生成方式及 30 秒内 Repair 能否完成仍是独立未决项。不凭这一例直接修改
Provider 请求模式、延长已批准 Safety Ceiling 或判定 Framework 不可行。

用户随后在本地运行独立的 `p4-final-output-spike / r1`（Artifact：
`build/evaluation-runs/p4-final-output-spike/r1/report.json`）。该配对实验只使用固定 GOOG Quote
Fixture、一个只读 Tool 和最小 `answer / source_refs` Schema；不是 AQ07 的完整 Prompt、Portfolio / Market
Context 或 Production Agent 路径。两臂均实际调用 `get_fixture_quote(GOOG)`，模型均未报告 Token Usage，
因此 Cost 仍为 `UNKNOWN`。

| 输出方式 | 首次候选 | Repair | 最终校验 | 模型请求 | 总耗时 |
|---|---|---|---|---:|---:|
| JSON 文本 | `InvalidStructuredAnswer`：外层有 Markdown JSON 围栏 | 触发一次；Repair 又在 `source_refs` 增加 Contract 不允许的 `uuid` | FAIL | 3 | 17.81s |
| PydanticAI Final Output Tool | 金融 Tool → Output Tool；Source / inline Citation 均通过 | 未触发 | PASS | 2 | 5.84s |

这证明固定 Qwen Endpoint 在此最小场景中接受 Output Tool Schema，且能先调用金融 Tool，再返回合法
结构化结果；不证明完整 AQ07 已修复，也不足以据单次样本断言长期可靠性、性能或成本优势。
两臂逐模型请求及 Repair 耗时均保留在原始 Artifact。当前 30 秒 Production Ceiling 不变；
只有 Production 输出方式另行通过 Human Review 并实现后，才能以完整 AQ07 回归检验该候选。

Output Tool Adapter 提交 `3d43d23` 后，用户运行 `p4-4a-aq07-output-tool / r1`（原始 Artifact：
`build/evaluation-runs/p4-4a-aq07-output-tool/r1/`）。AQ07 仍为 `REQUEST_FAILED`；
首个 Runtime 在 `24.02s` 完成，Tool Trace 为 Quote、自动 Market Context、Price History、News，
均成功且没有重复计账。Final Candidate 的 JSON 语法与 `source_refs` 对本轮 Source 的绑定均通过，
但 `answer` 把 Portfolio Snapshot 写成两处 `[source:PORTFOLIO_SNAPSHOT]`。Portfolio Snapshot
没有 inline Citation UUID，因此 `validate_citations` 明确报 `Source ID 格式无效`；这不是
Output Tool Schema 或 Provider 拒绝。一次无 Tool Repair 在剩余约 `5.99s` 内耗尽总 30 秒。
Usage / Cost 仍为 `UNKNOWN`，Human Rubric 与 Critical Gate 仍为 `NOT_EVALUATED`。
该原始结果不改写。后续仅澄清现有 Prompt 与 Repair 指令：Portfolio 事实可在 `source_refs`
声明，但不得使用伪造的 inline Source Token；Citation Validator 和 Safety Ceiling 不变。

用户随后运行 `p4-4a-aq07-citation-fix / r1`（原始 Artifact：
`build/evaluation-runs/p4-4a-aq07-citation-fix/r1/`）。AQ07 请求 `COMPLETED / OK`，
Tool Trace 为 Quote、自动 Market Context、Price History、News 共 4 次，所有来源引用有效；
没有 Repair，耗时 `25.63s`，Usage / Cost 仍为 `UNKNOWN`。这是完整 AQ07 技术链路的单次成功，
不代表回答质量或 4A Gate 通过；其余 12 个 Core Case 在此定向 Run 均为 `NOT_RUN`。
本轮回答正确区分了已知事实与 UNKNOWN，也未伪造 Strategy，但在列出事实后主要要求用户自行
判断是否加仓，缺少已批准 AQ07 目标要求的 LONG_TERM / 假设性 SWING 条件分析。
AU / EI / CP 的正式 Human Rubric 仍为 `PENDING`，不能将该质量缺口写成已通过。
后续仅在 Production Native Agent Prompt 增加通用条件分析要求，不修改冻结的 Current Runtime
Prompt、Confirmed Strategy 权威或交易建议持久化规则；原始在线结果保持不变。

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

AQ07 的 Citation Prompt 澄清已通过一次真实请求回归，但回答质量仍需复核。
通用条件分析 Prompt 的离线 Contract 测试已通过；下一步只定向复测 AQ07，审查其是否在
保留 UNKNOWN 与不创建 Strategy 的前提下完成 LONG_TERM / 假设性 SWING 的条件判断。
若请求再次失败，继续按 Model / Tool / Validation / Repair 阶段归因；只有确有必要时才在 Eval
做 30/60 秒对照，不调整 Production 超时。

用户在 `p4-4a-aq07-conditional-analysis / r1` 定向复测后，AQ07 再次 `REQUEST_FAILED`：
四次 Fixture Tool 均返回 `OK`，但完整 Native Run 在 `30.04s` 达到
`WALL_CLOCK_BUDGET_EXCEEDED`，没有 Final Candidate，`repair_count=0`。
因此该次没有可评价的回答，不能把失败归因为 Source/Citation 或输出格式，也不能以此前
`25.63s` 的单次成功证明 30 秒预算稳定足够。原始 Artifact 保持不变。
已增加仅限 Eval 的 AQ07 30/60 秒诊断入口，逐次记录 Model 请求、Tool 执行、Final Output
Tool 是否出现及耗时；它使用独立 Artifact，不能计入 4A Primary 成功率，也不会修改 Production
30 秒 Ceiling。Quote 内自动获取的 Market Context 计入 Quote 的聚合执行耗时，单独的关联
Tool 名称会记录，但不伪称有独立的内部耗时。

用户已运行 `p4-4a-aq07-timeout-diagnostic/60s`：AQ07 `COMPLETED / OK`，无 Repair，
Native Case 耗时 `29.01s`；首次模型请求 `6.17s` 后调用 Quote、History、News，
Quote 自动携带 Market Context，三个外层 Tool 执行均少于 `1ms`；工具返回后的第二次模型
请求耗时 `22.80s`，成功调用 Final Output Tool。说明这一轮主要耗时在第二次模型生成，
不是 Fixture Tool、Source Validation 或 Repair。Usage / Cost 仍为 `UNKNOWN`。
该 Run 配置的是 **Eval-only 60 秒**，虽在 30 秒内完成，但不能证明 Production 30 秒
Ceiling 稳定足够；此前同模型同 Case 的 30 秒失败仍保留。诊断回答已给出支持与暂缓加仓的
条件，并保持策略缺失为 UNKNOWN；但只讨论现有 LONG_TERM 追加，没有完成计划要求的
假设性 SWING 分支，且“LONG_TERM 持仓逻辑尚未被破坏”缺少已确认 Thesis 依据。
因此正式 AQ07 Human Rubric 与 4A Gate 继续 `PENDING`，不得把诊断成功计作 Primary PASS。
同一诊断入口的 30 秒配对观察随后完成；Production 预算和 Output Contract 暂不改变。

同一诊断入口的 `p4-4a-aq07-timeout-diagnostic/30s` 已完成：AQ07
`REQUEST_FAILED / WALL_CLOCK_BUDGET_EXCEEDED`，Native Case 耗时 `30.04s`，
无 Final Candidate、无 Repair。首次模型请求耗时 `17.53s` 并选择 Quote、History、News；
三个外层 Fixture Tool 均少于 `1ms`，Quote 包含自动 Market Context；第二次模型请求在
剩余约 `12.47s` 时被总预算取消。与 60 秒臂的首次 `6.17s`、第二次 `22.80s`
对照，当前两次请求耗时存在明显波动。该失败不应归因于 Tool、Citation Validator 或
Final Output 结构错误；第二次请求尚未返回，无法评价其候选输出。
现有 30 秒 Ceiling 对 AQ07 的真实模型路径已出现重复超时；60 秒臂只有一次成功，
不足以证明提高上限后的可靠性。此处停止 Production 预算修改，先提交 Human Decision
Proposal。AQ07 回答质量中的 SWING 分支及未证实 Thesis 问题仍是独立待办，不能靠延长预算解决。

**2026-09-24 Human Decision：** 用户批准把 PydanticAI Production Native 总 Wall-clock
与单次 Provider Request Timeout 调整为 60 秒；Model / Tool 次数及无隐式 Retry 不变，
Current Runtime 仍为 30 秒回归基线。以上原始 30/60 诊断结果不改写；本报告仍非 4A PASS，
需要在新上限下重新运行真实 AQ07 并单独解决回答质量缺口。

用户已运行 `p4-4a-aq07-native60 / r1`：AQ07 `COMPLETED / OK`，`25.94s`、无 Repair，
Quote、自动 Market Context、History、News 共 4 次 Tool Trace；Source / inline Citation
通过，Usage / Cost 仍为 `UNKNOWN`。这仅是 13 个 Core Case 中选定的 1 个，其他 12 个
`NOT_RUN`，Critical Gate 与 Human Rubric 仍未评估。回答已包含 LONG_TERM 追加与假设性
SWING 新仓的条件比较，没有把 SWING 误记为现有仓位；但它把“账户是否支持碎股”列为普通
加仓分析的关键待确认条件，并以实际可执行股数 UNKNOWN 支持暂缓，超出了已批准 AQ06
金额分析规则的必要前置条件。它还把账户 Cash“充裕”作为加仓支持条件，但用户没有提供
本轮 Budget，不能视为资金约束已满足。仅在 Production Native Prompt 澄清：未请求股数或
账户权限时不把该权限作为建议前置；Cash 不代替本轮 Budget。Portfolio / Ledger 事实、
交易写入校验和旧 Runtime Prompt 不变。该 Prompt Contract 的离线测试不能代替真实
AQ07 复测，4A Gate 继续 `PENDING`。

`p4-4a-aq07-policy / r1` 唯一落盘 Artifact 显示 AQ07 再次 `COMPLETED / OK`，
耗时 `28.05s`、4 次 Tool Trace、无 Repair，Source / Citation 通过，Usage / Cost
仍为 `UNKNOWN`；其余 12 个 Core Case 未执行。回答已将 Cash 与本轮 Budget 明确区分，
不再要求用户确认碎股权限，但仍把与提问无关的“实际可执行数量 UNKNOWN”列为暂缓条件。
它还将短期浮盈说成用户长期判断“得到价格验证”，虽没有已确认 Investment Thesis；
LONG_TERM / 假设性 SWING 仅作为待用户选择的问题出现，未完成两分支的实质条件分析。
这些是基于原始回答的待评分质量缺口，不回写历史结果，也不据 `pytest PASSED` 宣称
AQ07 或 4A Gate 通过。Tool Observation 中仍固定提供执行数量 UNKNOWN；是否按用户意图
裁剪该事实涉及 Tool / Context Contract，须先单独审查，不能仅为当前 Case 随意改写。

用户提到可能重复运行同一命令。当前只找到该目录的一份 Artifact，不能据此断定第二次
模型请求是否发生；旧 Harness 的目录占用检查位于模型调用之后，可能造成重复付费但不会覆盖
旧文件。已将目录冲突预检提前到模型调用前，并用离线测试确认重复执行不再调用 Runtime。

Output Tool 基本参数形状不合法时，Framework 没有可交给 Application Repair 的候选；
该失败明确记录为 `INVALID_PROVIDER_RESPONSE`，不添加隐藏重试或 JSON 文本兜底。
必要的 Safety Ceiling 或 Tool Contract 调整须遵守已批准计划的 Human Review 边界。
之后完成必要的有效
`r1`、`r2`、`r3` 真实模型 Run；命令与 Artifact 结构见
[Evaluation README](../README.md#phase-4-4a-core-eval)。收到 `manifest.json`、`cases.jsonl`、
`summary.json` 后复核 Tool Selection / Arguments、Conversation 指代与预算更正、Source / Citation、
Provider Failure、Repair、逐 Case Rubric 和 Critical Gate，并填写质量分布、成功率、Latency 与
Usage / Cost。只有 4A Core Gate 达标并完成最终 Automated Review，才将报告更新为 Human Review
版本；在 Human Review 前不进入 P4-T6～T8。Research Provider 仍独立，Brave 缺少在线验证不阻止
Runtime / Conversation 的 Core 技术验收。
