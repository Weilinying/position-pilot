# Ask Quality Phase 4 — 4A Core Evidence Report

**Status:** Source Projection 后最新完整 Core 为 `12 / 13 COMPLETED`；AQ17a / b
首轮通过，AQ09 第一轮工具预算耗尽，AQ06 金额分析行为仍有缺口，Gate OPEN（2026-09-27）。
不是 4A Gate PASS，也尚未提交最终 Human Review。

### 2026-09-27 Source Projection 完整 Core Review

`p4-4a-source-projection-core-1/r1` 完成 12 / 13 个 Core Case、17 / 18 个 Core Turn；
AQ04 Diagnostic 完成。全部 19 个已尝试 Turn / Diagnostic 的 Repair 合计为 0，
延迟中位数 `23.74s`、最大 `52.63s`。Usage / Cost 仍为 `UNKNOWN`；Research
`NOT_MEASURED`，与 Core Gate 独立。原始 Artifact 保留。

AQ17a / b 在完整 Primary 中再次首轮完成，耗时 `9.75s` / `4.92s`，两个 Final
的 `source_refs=[]`，正确区分 `NO_NEWS_FOUND` 与 `PROVIDER_UNAVAILABLE`。
这支持 Source Projection 调整有效，但尚未代替同一配置的冻结 Repeat。

唯一请求失败为 AQ09 第一轮，`4.39s` 返回 `TOOL_CALL_LIMIT_EXCEEDED`；Runtime
记录 `BUDGET_EXHAUSTED / TOOL_CALL_BUDGET_EXCEEDED`，没有 Final Candidate 或
Repair，也没有 HTTP 错误与超时证据。Trace 顺序为 Quote → 自动 Market Context
→ 显式 Market Context → Price History。`FinancialToolExecutor` 已缓存同轮 Market
结果，但 Native Session 与 Runtime Bridge 仍对显式调用再次计数，4 次额度已耗尽。
现有去重仅覆盖相反顺序（先显式 Market、后 Quote），未覆盖本次顺序。Artifact
未保存被预算拒绝的下一次工具请求，不能断言该请求具体名称。AQ09 第二轮完成
不能覆盖第一轮失败，也不足以证明完整两轮 Conversation 场景通过。

逐回答初审还发现 AQ06 的产品行为缺口：用户只问 `$200` 加仓分析，回答主动转向
理论股数，并将“账户是否支持碎股交易”列为影响最终建议的关键待确认条件。
这不符合已批准的金额分析规则。回答没有提高预算、没有把理论股数当作实际订单，
因此不据此套用旧版 Execution Critical Failure；须按现行产品规则修复及重新评估。
AQ05 / AQ10 也有无关的执行权限讨论，应在同一规则修订中检查。

本次仅形成 Artifact / 代码归因与质量初审，Rubric / Critical Gate 尚未正式评分，
Human Review 仍 `PENDING`。当前无需重跑完整 Core 或批量 Repeat；先处理 AQ09
同轮自动 / 显式调用的预算语义以及已批准金额分析规则的实现缺口，再做定向验证。
AQ09 的具体计数调整见 [Decision Proposal](../../plans/ask-quality-phase-4-aq09-tool-accounting-decision-proposal.md)，
尚未实施。`repeat.completed_case_count=6` 只是本次 Primary 完成了六个 Repeat
目标 Case，不代表已取得 r2 / r3。

独立只读复核未在其余已完成回答中确认自动 Critical Failure：AQ12 第三轮确实
重新查询 GOOG，AQ18 保留报道归因和冲突，AQ04 未伪造财报证据。AQ03 开头
“并没有跌到 180”强于可用的当前 Quote 证据，虽后文说明无法核实是否曾触及
180，仍属 Evidence / Inference 质量问题；AQ07 条件分析是否达到冻结的满分
要求也仍待评分。不能用请求完成率替代逐 Case 最低分与 Critical Gate。

### 2026-09-27 AQ17 Source Projection 定向在线证据

用户在 `p4-4a-aq17-source-projection-1/r1` 使用同一 Qwen 06-08 模型 / Endpoint
运行 AQ17a / b。两例均在首轮 `COMPLETED`，分别耗时 `7.50s`、`5.49s`，
各调用一次 `get_recent_news(GOOG)`，总 `Repair=0`。AQ17a Tool 状态为
`NO_NEWS_FOUND`，回答只说明指定窗口内当前数据源未返回报道，没有推断不存在
新闻或价格驱动因素；AQ17b 为 `PROVIDER_UNAVAILABLE`，回答说明新闻状态
`UNKNOWN`，没有编造报道。两个首轮 Final Candidate 的 `source_refs=[]`，
没有将失败 News Attempt 声明为可引用来源。Application Artifact 中的
`sources` / `tool_trace` 仍完整保留非 OK 审计项；它们不是模型可见的
`sources` Projection，也不是成功 Citation。

本次满足批准方案“先定向验证 AQ17a / b 首轮 Final 与 `Repair=0`”的条件，
允许下一步以新 Artifact 运行完整 Core Primary。仅选择 2 / 13 个 Core Case；
不能据此把完整 4A、三次 Repeat、Rubric / Critical Gate 或 Human Review 判为通过。
Token Usage / Cost 仍为 `UNKNOWN`，Research Gate 独立且 `NOT_MEASURED`。

### 2026-09-26 AQ17 Source Projection：已批准、离线完成、在线待验证

Human Review 已批准将模型可见 Tool Observation 的 `sources` 限定为本轮成功且
带 `source_id` 的可引用来源；失败或空结果的调用状态与 `error_code` 改由独立的
`attempt_observations` 呈现。无成功来源时明确给出 `sources: []`。Application
内部 Tool Trace / Source Registry 仍保存完整成功与失败尝试，SourceValidator
继续确定性拒绝未成功的 Source Reference。混合 `DEGRADED` 结果保留成功来源及
相关失败观察，未改 Final Output、Repair 或 60 秒预算。

离线已验证空结果、Provider Failure、混合成功 / 失败的模型可见投影与内部 Trace
分离，且 Validator 继续拒绝失败来源；相关单测 `49 passed`，Ruff Check /
Format 与修改模块的 Mypy 通过。此结果不能证明真实模型会在首个 Final 正确
处理 AQ17a / b；下一步只在新 Artifact 中定向在线验证这两个 Case，要求首轮
Final 合法、`Repair=0`。定向通过后才运行完整 Core，历史运行不改写。

## 1. 范围与历史边界

### 2026-09-26 完整 Core Recheck 与 AQ17 Decision Boundary

用户在 `p4-4a-jun08-core-recheck-1/r1` 以相同模型 / Endpoint 完整运行 13 个 Core
Case，结果仍为 `11 COMPLETED / 2 REQUEST_FAILED`，18 个 Core Turn 中 16 个
完成，请求成功率 `84.62%`。AQ04 Diagnostic 完成；Research Gate 继续
`NOT_MEASURED`。19 个已尝试 Turn / Diagnostic 的延迟中位数 `24.71s`、最大
`56.32s`，Repair 合计 4 次，Token Usage / Cost 为 `UNKNOWN`。`pytest PASSED`
只表示采集完成；Critical Gate 仍 `NOT_EVALUATED`、Human Review 仍 `PENDING`。

与上次完整 Primary 不同，本次 AQ05 `COMPLETED`、`Repair=0`；AQ12 三轮均完成，
第三轮重新调用 GOOG Quote 并绑定本轮 Source。AQ17a / b 则同时失败：前者 News
Tool 返回 `NO_NEWS_FOUND`，后者返回 `PROVIDER_UNAVAILABLE`，二者的失败
Source 均为 `source_id=null`。两个首轮 Candidate 的自然语言均正确保留 UNKNOWN，
却都将 `RECENT_NEWS(GOOG)` 写入 `source_refs`。Application 的 SourceValidator
正确拒绝；各一次 No-Tool Repair 均以 `OUTPUT_RETRY_EXHAUSTED / ToolRetryError`
结束，最终 `REQUEST_FAILED / LLM_INVALID_PROVIDER_RESPONSE`。没有 Provider HTTP
错误或 Wall-clock 超时证据，也没有 Repair 原始输出可供推断更具体的非法参数。

AQ17a 曾单次定向首轮成功，但本次完整运行再次失败，不能视为稳定修复。
冻结 Gate 要求 AQ17a / b 首个 Final 合法且 `Repair=0`；当前明确未达标。
严格 SourceValidator、一次 Repair 与现有 Gate 均不放宽。模型可见的 Tool
Observation 仍包含非 OK 的 `sources` 审计项，给出 `type/ticker` 但无可引用 ID；
这与模型重复复制失败 Source 的行为相吻合，但不是框架本身无法支持 Source Contract
的证明。若要调整已冻结的 Tool Observation Contract，先走独立 Human Review；
在批准前不再为同一配置重跑完整 Core。

### 2026-09-26 AQ12 Fresh Evidence 定向在线复测

用户使用当前修订在 `p4-4a-jun08-aq12-fresh-evidence/r1` 仅运行 AQ12，三轮均
`COMPLETED`、`Repair=0`，耗时分别为 `26.42s`、`28.95s`、`17.74s`。
第三轮恢复 GOOG 后实际调用 `get_current_quote(GOOG)`，取得本轮新的
`CURRENT_QUOTE` Source ID，与第一轮 GOOG、第二轮 MSFT 的 ID 均不同；最终回答
使用该本轮 Quote 和当前 `PORTFOLIO_SNAPSHOT` 比较成本与浮盈，inline Citation
绑定本轮 Quote，没有串用 MSFT 来源。旧运行中确认的“无 Tool 调用却沿用旧报价”
问题在**这一次**定向复测中未再出现。

第三轮未重新查询 Price History 或 News；回答将这两项保持 `UNKNOWN`，不能把
“结论不需要修改”理解为新闻或价格路径已重新核验。该结果证明当前报价与持仓
比较路径的单次行为，不证明整体 4A、跨次稳定性或真实金融数据质量。
Critical Failure Gate 仍 `NOT_EVALUATED`，Human Review 仍 `PENDING`；
Usage / Cost 仍为 `UNKNOWN`。为避免重复付费采集尚未可验收的结果，
已先审查既有已完成 Case 的质量与边界。

随后对旧完整 Primary 的已完成 Case 做只读初审：AQ03、AQ07～AQ11、AQ18、AQ20
未见可直接确认的 Critical Failure；AQ06 正确守住修订后的 Cash / Budget / 执行权限
边界，但主动讨论理论碎股与“敞口增加不显著”仍需人工质量评分；AQ17b 正确区分
Provider Failure 与空结果，但安全降级的完整性待评分。AQ09 / AQ10 / AQ11 存在
约 `38～48s` 的长尾耗时。旧 Primary 的 AQ05 与 AQ17a 是明确的请求失败，
后续各有一次定向成功，不能覆盖历史失败。该初审不填写冻结 Rubric 或 Critical Gate。
目前未发现要求在完整 Primary 前继续修复的确定性新缺口；下一步可用当前代码、
同一模型和新 Artifact 目录重新采集完整 Core Primary，然后逐 Case 评分及安排 Repeat。

### 2026-09-26 AQ12 跨轮当前事实定向验证

用户在 `p4-4a-jun08-aq12-check/r1` 使用同一模型 / Endpoint 只运行 AQ12；
GOOG → MSFT → GOOG 三轮均 `COMPLETED`，耗时分别为 `25.89s`、`13.81s`、
`18.24s`，`Repair=0`。前两轮分别取得对应 Ticker 的成功 Quote，没有串用
MSFT 的 Portfolio 或来源；首轮 Price History 为 `NO_DATA`、News 为
`NO_NEWS_FOUND`，回答没有把它们声明为成功来源。

第三轮询问先前 GOOG 结论是否需要修改。Runtime 的 `tool_trace=[]`，本轮仅有
`PORTFOLIO_SNAPSHOT` Source；回答仍沿用之前的 `$210.25` 报价与浮盈判断，
断言核心结论不需要修改。虽明确说报价是“之前获取”，没有伪造新 Citation，
但已批准的 Conversation Contract 要求历史 Answer 仅用于指代与比较、当前 Quote /
News / Market Context 按时效重新查询。因此这是**已确认的 AQ12 当前事实未重查缺口**，
不是 MSFT 串用；不因 `3 / 3 COMPLETED` 或 `pytest PASSED` 判为 Gate 通过。
Critical Failure 仍待独立评分，不能从该记录直接宣称 PASS 或 FAIL。

Native Conversation Prompt 已按通用跨轮时效规则澄清：旧行情与旧判断只代表当时证据；
询问旧投资结论是否仍成立时，按当前问题需要重新取得相关 Tool 结果，再比较。
没有针对 AQ12 的固定措辞或 Ticker 设特例。离线 Prompt Contract 测试通过；
在该次运行时，澄清尚无在线结果；其后的单次复测记录于上节，不改写本次失败。

### 2026-09-26 AQ17a Source Clarification 定向在线验证

用户以 `qwen3.7-max-2026-06-08` 在同一 Endpoint 运行
`p4-4a-jun08-aq17a-source-clarity/r1`，仅选择 AQ17a。该次真实模型请求在
`10.24s` 内 `COMPLETED`，首次 Final 合法，`Repair=0`。`get_recent_news(GOOG)`
返回 `NO_NEWS_FOUND`；回答准确限定为当前 Provider 在最近五个日历日的窗口内
未返回报道，并将 GOOG 是否存在其他重要新闻保持为 `UNKNOWN`。Candidate 的
`source_refs=[]`，没有将 `source_id=null` 的空结果审计项冒充可引用来源。

这验证了 Prompt 澄清后**这一次** AQ17a 的空结果及 Source Contract 路径；
不改写先前 Primary / 定向失败，也不证明跨次稳定性、其他 Case 质量或完整 4A Gate。
本次仅选择 1 / 13 个 Core Case，Critical Failure Gate 仍为 `NOT_EVALUATED`，
Human Review 仍为 `PENDING`；Token Usage / Cost 仍为 `UNKNOWN`。
旧完整 Primary 中的 AQ06 没有已证实的修订后 Critical Failure，但主动讨论碎股与
“不会显著增加绝对敞口”的判断仍待人工质量评分。AQ12 的旧运行在 Repair 后将已成功
取得的 Quote / Market Context 误述为 `UNKNOWN`，属于明确的证据使用缺口；该 Artifact
早于当前 Prompt 澄清，不能推定当前版本仍失败。下一步先以新目录单独复测 AQ12，
审查首轮 Citation、Repair 与最终 Context 使用，再决定是否重跑完整 Core。

### 2026-09-26 AQ05 / AQ17a 定向 Repair 诊断

用户在 `p4-4a-jun08-repair-diag-1/r1` 仅复测这两个 Case。AQ05 首轮即
`COMPLETED`，耗时 `29.14s`、无 Repair，Cash `$4,875.77` 与 Budget `$500`
分开，Portfolio 未再出现非法 inline Citation；这只是一次定向成功，不覆盖此前
Primary 失败，也不代替三次 Repeat 与质量评分。AQ17a 仍在 `13.18s` 内
`REQUEST_FAILED`：首轮 Candidate 正确说明 `NO_NEWS_FOUND` 只代表窗口无结果，
却再次在 `source_refs` 声明未成功的 `RECENT_NEWS`；Application 正确拒绝。
一次 Repair 返回 `INVALID_PROVIDER_RESPONSE`，新增安全诊断为
`OUTPUT_RETRY_EXHAUSTED / ToolRetryError`，指向框架输出工具校验 / 重试路径，
而非 HTTP 400 或 Wall-clock 超时。Artifact 不含 Repair 原始输出，不能推断具体非法参数。

针对重复出现的首轮错误，Conversation Prompt 现明确说明 Tool Observation 的
`sources` 中每个 `status != OK` 的项只是失败审计，即使回答提及该状态也不得声明为
`source_refs`；整体 Tool 状态为 `DEGRADED` 时，单独 `OK` 且带 `source_id` 的来源
仍可引用。Validator、Final Output Tool、Repair 次数与 60 秒上限均不变。
在该次诊断时，这仍是尚未在线验证的最小通用澄清；其后续定向在线结果记录于上节。
冻结 Gate 仍要求 AQ17a 首次 Final 合规且 `Repair=0`，且不能用单次定向结果代替完整
Primary / Repeat。

### 2026-09-26 `qwen3.7-max-2026-06-08` 完整 Core Primary Review

用户在同一模型 / Endpoint 下运行 `p4-4a-jun08-core-1/r1`；13 个 Core Case 中
11 个 `COMPLETED`、2 个 `REQUEST_FAILED`（AQ05、AQ17a），请求成功率 `84.62%`，
18 个 Turn 中 16 个完成。AQ04 Earnings Diagnostic 完成；AQ01、AQ02、AQ19
继续 `NOT_MEASURED`。19 个已尝试 Turn / Diagnostic 的延迟中位数 `25.55s`、最大
`51.14s`，Repair 共 4 次；Token Usage / Cost 仍为 `UNKNOWN`。pytest `PASSED`
只说明整套采集结束；逐 Case Rubric 与 Critical Failure 尚未评估。

两个失败均为首轮模型已调用 Tool 并生成 Candidate，随后违反 Application Source / Citation
Contract，且一次 Repair Runtime 返回 `INVALID_PROVIDER_RESPONSE`，没有最终回答：

- AQ05：Quote、Market Context、History、News 均成功，Cash `$4,875.77` 与本轮 Budget
  `$500` 在 Candidate 中区分正确；但 Portfolio 事实被写成
  `[source:PORTFOLIO_SNAPSHOT]`，这是没有 UUID 的非法 inline Citation。Application 拒绝正确。
- AQ17a：News 返回 `NO_NEWS_FOUND`；Candidate 正确说明“窗口无结果不等于不存在新闻”，
  却在 `source_refs` 中把未成功的 `RECENT_NEWS` 当作成功来源。Application 拒绝正确。
  冻结 Gate 还要求 AQ17a **首次 Final** 符合 Source Contract、`Repair=0`，不能仅以
  Repair 偶然成功替代这一要求。

同一快照的 AQ04、AQ12 曾完成 Repair，故上述失败目前归为首轮 Contract 违规加
Repair 输出可靠性问题，**不是** PydanticAI 架构不支持或 Tool Choice 不兼容的证据。
当前 Artifact 未保存 Repair 的底层异常细节，不能再把它归因于具体 Provider 输出形状。
后续 Runtime / Eval Trace 增加安全的 Framework Failure Kind 与 Cause 类名；这些新增诊断字段
不保存异常正文、模型原始响应或用户内容，既有 Eval Answer / Question 记录仍按原 Contract 保留。
旧 Artifact 保持原样。该分类仍不等于输出内容或最终原因的完整证据。
已完成 Case 的回答仍需按冻结 Rubric 逐条审查；例如 AQ06 主动讨论碎股及理论股数，
且称 `$200` 投入“不会显著增加绝对敞口”；AQ12 首轮 Tool Trace 有成功 Market Context，
最终回答却称 Market Context `UNKNOWN`；AQ17b 仅说明 News Provider Failure，
是否满足可用 Portfolio 信息下的安全降级亦待评分。以上均不直接改写为 Critical PASS / FAIL。
Fixed Fixture 的成功来源与新闻测试 URL 只证明来源绑定，不证明真实金融数据或 Research 质量。
当前不重跑完整 Core、不进入 T6～T8；先使用新的诊断字段仅对 AQ05 / AQ17a
做定向复测，区分模型再次违反首轮 Contract 与 Repair 阶段的失败类别。之后再决定最小修复，
重新收集完整 Primary / Repeat 并提交 Human Review。

### 2026-09-26 `qwen3.7-max-2026-06-08` 最小兼容性证据

用户本地运行 `p4-4a-jun08-compat-1/r1`，仅选择 AQ20。该快照在当前
Region / Endpoint 的请求 `COMPLETED`，耗时 `3196.45ms`，无 Tool Call、无 Repair；
回答为账户可用现金 `$4,875.77`，与固定 Fixture 一致，未受无关历史背景干扰。
随后用户在同一模型和 Endpoint 上执行 Production Compatibility Smoke：One-tool
`get_fixture_quote(GOOG)` 在 `5865.31ms` 内 `COMPLETED`；Multi-tool 依次调用
`get_fixture_quote(GOOG)`、`get_fixture_market_context(GOOG)`，在 `8787.37ms` 内
`COMPLETED`。两项断言均通过，工具名与参数正确。因此当前已验证 No-tool、One-tool、
Multi-tool 及 Final Output 的最小真实模型兼容性。两项 Usage 均未由 Provider 报告，
Token Usage / Cost 仍为 `UNKNOWN`。这不验证复杂 Citation 或完整 4A 回答质量；
Critical Gate 与 Human Review 仍为 `NOT_EVALUATED / PENDING`。下一步可以用该快照
独立运行完整 4A Core Primary，不能与旧别名结果混作同模型重复试验，也不修改
Production 默认模型。此前建议的 05-20 快照尚未实测。

### 2026-09-26 备选模型入口诊断

**Provider 原始错误确认后的修订（2026-09-26）：** 用户确认该次请求返回 HTTP 400、
`error_code=InvalidParameter`，错误说明为
`The tool_choice parameter does not support being set to required or object in thinking mode`。
因此 `qwen3.7-max-2026-05-17` 与当前 Phase 4 PydanticAI Runtime 的 Tool Choice / Final Output
请求配置**不兼容**；这不是模型名无效、额度、权限或 PydanticAI 通用兼容性结论。
不为该快照修改 Production Tool / Final Output 语义。下一候选为同系列的
`qwen3.7-max-2026-05-20`，仅在当前 Region / Endpoint 实测通过 Tool Choice 与 Structured Output
路径后才可用于后续 4A Eval；当前状态为 `NOT_MEASURED`，也不假定它拥有独立额度。
此候选依据是[阿里云模型说明](https://help.aliyun.com/en/model-studio/qwen3-7-max)将当前别名标为
与 05-20 快照功能等价；[Function Calling 说明](https://help.aliyun.com/en/model-studio/qwen-function-calling)
明确思考模式不支持该 Tool Choice 组合。文档能力声明不能代替当前账户、Region / Endpoint 的实测。
下一步先以 AQ20 作最小兼容性 Smoke；不同模型的结果分别记录，不合并为同模型重复评测。
Adapter 已增加内部 Provider HTTP 状态、错误码及说明字段，供后续 Eval Trace 诊断；
对外失败码、Production Tool / Final Output 语义和历史 Artifact 均不变。

`p4-4a-alt-model-smoke-1/r1` 显式选择 `qwen3.7-max-2026-05-17`，只运行 AQ20。
Core Eval 已接受该模型名并将其记录在 Run Metadata；AQ20 在 `0.65s` 后
`REQUEST_FAILED / LLM_INVALID_REQUEST`，Runtime Trace 为
`FAILED / MODEL_HTTP_FAILURE`，未执行 Tool、未产生回答或 Token Usage。
因此该结果只证明当前 Model / Endpoint / Request 组合未成功，不能为 AQ20 打质量分，
也不能把失败归因于 Portfolio 或 Conversation 行为。现有 Artifact 未保存精确 HTTP 状态及
Provider 错误码；在当时，`LLM_INVALID_REQUEST` 对应适配器中的非认证类 4xx 映射，尚不能判定
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
