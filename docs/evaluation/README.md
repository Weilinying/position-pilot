# PositionPilot V1 Evaluation

## Purpose

M6 Evaluation 验证 PositionPilot V1 核心 Agent Behavior 是否能稳定、重复地满足产品边界，并为基础 Model Selection 提供证据。它不评估投资收益，也不是通用 LLM Benchmark 或历史回测平台。

## Evaluation Layers

### Deterministic / Automated Checks

pytest 负责验证 Tool Selection / Trace、参数与预算、Response Status、Structured Output、Repair、Invalid Tool Call、Source Contract、Provider Failure 与 Request Failure。Fake Portfolio、Market、News 和 Market Regime Fixtures 隔离实时数据波动。

### Human Factual Grounding Checks

Human Review 负责判断自由文本是否：

- 越过 `UNKNOWN` 或 Source Boundary；
- 未请求数量时主动比较 Cash / Budget 与单股价格，或据此推断实际购买能力；
- 正确使用 Historical BUY Facts 与 `LONG_TERM` / `SWING`；
- 把 Market Regime 或 Position Type 转化成过强建议；
- 出现自动规则无法低误报识别的事实错误或推荐强度问题。

`Automated Pass != Human Grounding Pass`。合法 `source_refs` 只证明来源声明满足 Application Contract，不证明每个自然语言 Claim 正确。

2026-10-03：成功 Quote 不再自动提供 Cash / 单股价格的派生关系，也不再允许复述该旧字段。
Cash 和 Quote 分别保留；显式数量请求仍须使用 Application 提供的可靠确定性结果。
旧 Behavioral Dataset 因输入/评审口径变更升级为 1.1；Phase 4 AQ Dataset 0.2 与固定行情 Fixture 不变。
历史 Artifact 不回写，详见[清理决策](../engineering-notes/phase4-cash-quote-context-interference.md)。

## Dataset

当前 Dataset Version 为 `1.1`，定义在 `tests/evaluation/test_real_model_behavior.py`。每个 `BehavioralCase` 包含固定问题、Portfolio 与 Provider Fixtures、Automated Tool / Status Expectations、Human Checks，以及存在时的 Case-specific Known Limitation。

Coverage Matrix 与 Controlled Contrast 也保存在同一文件。pytest 继续作为唯一 Execution Engine；Harness 不重新实现测试发现或断言。

## Execution

默认 deterministic tests 不需要真实 Credential：

```bash
uv run pytest
```

全量 opt-in Real-model Behavioral Eval：

```bash
RUN_REAL_LLM_BEHAVIORAL_EVAL=1 \
EVAL_RUN_ID=<stable-run-id> \
EVAL_REPETITION_INDEX=1 \
LLM_MODEL=<model-id> \
uv run pytest tests/evaluation/test_real_model_behavior.py -s
```

单个 Case 或 Case Subset 使用 pytest `-k`：

```bash
RUN_REAL_LLM_BEHAVIORAL_EVAL=1 \
EVAL_RUN_ID=<stable-run-id> \
EVAL_REPETITION_INDEX=1 \
LLM_MODEL=<model-id> \
uv run pytest tests/evaluation/test_real_model_behavior.py -s \
  -k 'cash_only_no_tool or low_cash_personalization'
```

必要环境变量：

- `LLM_API_KEY`：本地 Credential，不得进入报告或 Git；
- `LLM_PROVIDER`：本轮 Provider 标签；默认 `ALIYUN_MODEL_STUDIO`，跨 Provider 比较时必须显式设置；
- `RUN_REAL_LLM_BEHAVIORAL_EVAL=1`：显式启用真实模型；
- `LLM_MODEL`：本轮实际候选模型；
- `EVAL_RUN_ID`：同一实验的稳定标识；
- `EVAL_REPETITION_INDEX`：从 1 开始的正整数。
- `EVAL_ROUTING_RESPONSE_FORMAT`：Evaluation-only RCA 开关，支持 `text`（默认）或 `json_object`；只覆盖带 Tool 的 Routing Completion。

`LLM_BASE_URL` 和 `LLM_REQUEST_TIMEOUT_SECONDS` 可覆盖当前 Adapter 默认配置。Harness 记录每次
Completion 的统一 model / latency / token usage；Provider 未返回完整 Usage 时保持 `UNKNOWN`。
Harness 不读取 Repository `.env`。

### Ask Quality Discovery Baseline

新 Dataset `ask-quality-discovery` / `0.1` 使用独立入口
`tests/evaluation/test_ask_quality_baseline.py`。默认运行只检查 Manifest、Fixtures、Reporter 与
Fake Model 路径：

```bash
uv run pytest tests/evaluation/test_real_model_behavior.py \
  tests/evaluation/test_ask_quality_baseline.py -q
```

真实模型首次运行覆盖 21 个唯一执行变体，构成 Primary Baseline，并将不含 HTTP Secret 的
Provider-neutral 记录写到 Git 忽略目录。Dataset 与 Rubric 不绑定 Provider / Model，实际模型以
该次 Run Manifest 为准：

```bash
RUN_REAL_ASK_QUALITY_EVAL=1 \
EVAL_RUN_ID=<stable-run-id> \
EVAL_REPETITION_INDEX=1 \
ASK_QUALITY_ARTIFACT_DIR=build/evaluation-runs/<stable-run-id>/r1 \
LLM_MODEL=<model-id> \
uv run pytest -p no:cacheprovider tests/evaluation/test_ask_quality_baseline.py -s -q
```

关键重复集 AQ03、AQ05、AQ07、AQ17a、AQ17b 的第二、三次运行分别使用新的 Artifact 目录；这
10 次额外执行只用于 Repeat Consistency，不混入 Primary Baseline 的质量分布：

```bash
RUN_REAL_ASK_QUALITY_EVAL=1 \
EVAL_RUN_ID=<stable-run-id> \
EVAL_REPETITION_INDEX=2 \
ASK_QUALITY_CASE_IDS=AQ03,AQ05,AQ07,AQ17a,AQ17b \
ASK_QUALITY_ARTIFACT_DIR=build/evaluation-runs/<stable-run-id>/r2 \
LLM_MODEL=<model-id> \
uv run pytest -p no:cacheprovider tests/evaluation/test_ask_quality_baseline.py -s -q
```

将 repetition 改为 `3`、目录改为 `r3` 即完成第三次。调用方必须先在自己的 Shell 中注入
`LLM_API_KEY`；Harness 不读取或解析 `.env`。每个目录生成 `manifest.json`、`cases.jsonl` 与
`summary.json`。`ASK_QUALITY_CASE_IDS` 未设置时执行全部变体，未知或重复 ID 会作为配置错误退出。

## Reproducibility

每个 Case Report 与 Session Summary 记录：

- Dataset Version、Provider、Model、Routing Response Format；
- Production Revision、Harness Revision、Run ID、Repetition Index、Started At；
- 脱敏后的 LLM Endpoint、Request Timeout 与 Prompt / Tool / Fixture 摘要；
- Status、Tool Trace、Repair / Invalid JSON、Request Failure；
- Retrieved / Declared Sources、Answer、Human Checks 与现有诊断指标。

Harness Revision 无法读取时记录 `UNKNOWN`，不阻断 Eval；存在任何未提交修改时追加 `-dirty`。
正式 Model Comparison 应使用相同 Dataset、Production / Harness Revision、Prompt、Tool Contract、
Fixtures 和 Evaluation Rules，并保持工作区干净。

## Failure Classification

- `TOOL_SELECTION`：遗漏、过度或不稳定 Tool Selection；
- `GROUNDING`：自由文本越过 Fact / Source / `UNKNOWN` 边界；
- `HISTORICAL_CONTEXT_USE`：Historical BUY Facts 未使用或使用错误；
- `RECOMMENDATION_BOUNDARY`：Market Regime / Position Type 被转化成过强建议；
- `STRUCTURED_OUTPUT`：JSON、Schema、Source Reference 或 Repair 信号；
- `REQUEST_FAILURE`：请求未形成最终 Answer；
- `PROVIDER_FAILURE`：真实模型或外部 Provider 不可用；
- `HARNESS_FAILURE`：Fixture、Metadata、断言或运行配置错误。

该 Taxonomy 用于报告与人工归类，不引入 LLM-as-a-Judge 或复杂评分代码。

虚构 Source、突破 Tool Budget、错误 Status、混淆 Provider Failure 与 `NO_DATA` / `NO_NEWS_FOUND`、补造 `UNKNOWN`，或 Repair 后仍未恢复 Structured Contract，属于 Hard Contract Failure。先保留 Trace / Diagnostics 并完成 Root Cause Analysis，再决定修复层级，不预设增加 Guard。

成功 Repair、路由波动、Context Over-call、Source 漏报、Latency 异常与回答差异不足属于 Quality Signal。它们应进入报告，但不自动触发 Production 修改。

## Acceptance 与历史结果

2026-10-03 Human Review 允许 Gemini Phase 4 Core 的传输重试：`httpx.ConnectError` 或 `httpx.ReadError`
自动重发同一个模型请求一次（最多两个 Provider attempts）；明确 TLS 证书校验错误不重试。
timeout、401/403、429、5xx、Schema、Tool quota 和 Behavioral failure 不触发此策略。
重试使用原 Tool Result、History 与 Native Schema，不重新执行 Tool 或整个 Case，也不重置
30s per-turn wall-clock。SDK / PydanticAI / Output 重试仍为0；Production不启用此测试策略。

`model_request_count` 继续计 Agent Loop 的模型 step，最多8；物理 Provider 请求尝试另计
`provider_model_request_attempt_count`，最多16（不含原配置 Application Repair 的独立请求）。
Trace 的 `request_index` 是 Run 内物理尝试序号；`model_request_index` 是当前 Runtime Call
内模型 step，`attempt_index` 为该 step 的第1/2次尝试。首次错误不删除；重试后成功明确记录
`transport_retry_count` 和 `transport_retry_recovered_count`，不能表述为首次请求成功。
更改 Retry Policy 后使用新 Candidate / 独立 Run，不改写冻结 V4 的 Retry=0 历史证据。

8-Case Model Comparison 只选择值得进入完整 Dataset 的候选，不代表 M6 完成。候选必须继续完成全量 Dataset、Automated Evaluation 与 Human Factual Grounding，才能进入 M6 Human Acceptance。

真实 Alpaca Market / News、Investment Agent Online Smoke 与 PostgreSQL Integration 可作为 Human Acceptance Evidence；受 Credential 或第三方服务状态影响的 Online Smoke 不作为常规 CI Gate。

当前实验方法见 `docs/evaluation/model-selection.md`；正式报告保存在 `docs/evaluation/reports/`。M3 / M6 早期结果与边界演进保存在 `docs/engineering-notes/m3-agent-evaluation-and-grounding-boundaries.md` 和 M6 Plan，旧结果不在缺少 Run Metadata 时伪装成可直接比较的正式报告。

## V1 Scope Boundary

M13 后的 Answer Quality Discovery 方向于 2026-09-13 获批，使用独立的 [整体路线](../plans/ask-quality-discovery.md) 与 [阶段一基线计划](../plans/ask-quality-phase-1-baseline.md)。新案例分别覆盖 Domain / Strategy / Conversation / Long-term Memory / Runtime 行为；Runtime、Model / Provider、Research Provider、Memory / Persistence 分开评分，4A 与 4B 分别留存评测证据。新集以 scope=FULL / DIAGNOSTIC 表示目标场景能否完整测试，以 execution_status 的 COMPLETED / REQUEST_FAILED / NOT_RUN 表示实际执行结果；DIAGNOSTIC 保留适用维度的局部评分，但不进入完整场景质量。报告首页展示能力覆盖率、完整场景回答质量、请求成功率与 Critical Failure 次数。Critical Gate 对关键事实 / 来源错误、未经确认把 Strategy / Long-term Memory 提升为有效状态、覆盖有效记录、用于后续决策或复用失效策略记 FAIL；保持 `PENDING` 且不参与决策的 Candidate 本身不触发。未经证据确认的关键事实前提，只有在 Agent 未标记未验证或先行核验、仍将其当真继续给出因果分析、风险判断或交易建议时触发 Gate Fail。当前 Dataset `1.0`、历史结果和运行入口保持原义。

Ask Quality Dataset `0.1`、固定 Fixture、能力标签、Reporter 与真实模型 opt-in 入口已经实现；当前
`qwen3.7-max` 正式 Baseline、关键重复与 Human Rubric Calibration 已完成，结果见
[2026-09-15 正式报告](reports/2026-09-15-ask-quality-baseline-qwen37max.md)。阶段一没有修改 Production
Prompt、路由、工具或 State 能力。

Phase 4 使用派生 Manifest `ask-quality-discovery / 0.2`，定义在
`tests/evaluation/ask_quality_phase4_manifest.py`。它复用 `0.1` 的 21 个执行变体、固定 Fixture 与
Rubric `0.1`，只冻结 4A Core、独立 Open Research Gate、AQ04 Earnings Regression 与 4B Strategy 的
目标 Scope、Checkpoint 顺序与连续 Ask Script。Manifest 保存 `0.1` Fixture Digest 以检测历史漂移；
`0.1` 的 Case 定义、Artifact、Hash 和历史结果保持不变。T4R 延后时 AQ01、AQ02、AQ19 继续记录为
`DIAGNOSTIC / NOT_MEASURED`，不伪装成 Runtime Failure，也不阻塞 4A Core。

### Phase 4 4A Core Eval

入口实时打印每轮 `STARTED` / `TURN_FINISHED`（Case、轮次、状态、耗时），不是每个 Case 一个
pytest item。60 秒预算按每轮回答计算，整套串行测试可能运行十几分钟；两条进度之间仍需等待模型。
`progress.jsonl` 从 Run 开始创建，每轮结束立即追加完整固定 Fixture 证据；Ctrl+C 会在当前轮
记录 `INTERRUPTED` 并保留已完成轮次。没有 `RUN_FINISHED` 的日志不是完整验收结果；正式
manifest / cases / summary 仍在全部完成后写入。进度文件包含回答，不应公开分享。
Provider HTTP Failure 的本地 Runtime Trace 还保留 HTTP Status、Provider Error Code 与 Error Message，
仅用于诊断；对外 API 仍返回稳定失败码。诊断信息可能包含敏感请求细节，不要公开分享 Artifact。
PydanticAI 的 `UnexpectedModelBehavior` 只记录安全的 Framework Failure Kind 和底层异常类名，
不记录原始异常正文或 Provider 响应；这能辅助区分输出重试耗尽与响应形状异常，不能还原模型原文。
已有部分进度的目录也禁止重复使用，避免意外重新付费；当前不提供自动续跑。

`tests/evaluation/test_phase4_core_online.py` 是新的 pytest opt-in 入口。它复用 `0.1` 固定 Financial
Fixtures，但实际 Ask 走 `NativeInvestmentAgent → PydanticAIRuntime`，多轮 Case 注入已发生的 User 与
已完成的 Assistant 历史；不复用旧 `execute_case()` 的 Current Runtime 路径。每轮保存 Native Tool Trace、
Source、Citation 文本、Repair 调用、Latency 和 Usage 或 `UNKNOWN`。Portfolio / Market / News 为固定
Fixture，真实模型只用于 Agent 行为评估。它不验证真实金融 Provider 的时效与可用性。
固定 Fixture 的 Runtime Final Candidate（包括 Repair 前未通过校验的候选）保存在 Artifact 中，
用于区分 Source / Citation / Structured Output 问题；不要把 Artifact 当作可公开分享的脱敏日志。
2026-09-24 Human Review 后，Production Native 和此 4A 入口的总 Wall-clock、单次模型请求上限
均为 60 秒；Production 的 `NATIVE_LLM_REQUEST_TIMEOUT_SECONDS` 默认 60 秒且可在
`0～60` 秒内配置，4A 固定为 60 秒以保持各次 Run 可比较。
旧 `LLM_REQUEST_TIMEOUT_SECONDS` 仍用于 Current Runtime 回归路径，默认 30 秒。
此前的 30/60 秒诊断与 Final Output 独立 Spike 保持历史原貌，不回写 Artifact。

调用者先在自己的本地 Shell 导出 `LLM_API_KEY`、与当前 Region 对应的 `LLM_BASE_URL`，并显式设置
`LLM_MODEL` 为本次实际可用的模型；`LLM_PROVIDER` 应为 `ALIYUN_MODEL_STUDIO`（未设置时使用该值）。
一次完整 Run 的 r1 / r2 / r3 必须使用同一模型及 Endpoint，切换模型须使用新的 `EVAL_RUN_ID`
和 Artifact 目录，并在报告中分开列出结果。既有 `qwen3.7-max` Artifact 保留为历史证据；
其他模型的运行不自动替代其质量基线，也不改变 Production Model。Agent 不读取 `.env`。
Primary 执行 13 个 Core FULL Case 与 AQ04 Diagnostic：

```bash
RUN_PHASE4_EVAL=1 \
EVAL_RUN_ID=<same-run-id> \
EVAL_REPETITION_INDEX=1 \
PHASE4_ARTIFACT_DIR=build/evaluation-runs/<same-run-id>/r1 \
PYTHONPATH=backend:tests/evaluation \
.venv/bin/pytest tests/evaluation/test_phase4_core_online.py -m online -s -q
```

重复运行只需分别改为 `EVAL_REPETITION_INDEX=2/3`、Artifact 目录 `r2/r3`，保持相同的 `EVAL_RUN_ID`；
默认 Repeat 集为 AQ03、AQ05、AQ06、AQ07、AQ17a、AQ17b。每个目录生成 `manifest.json`、
`cases.jsonl`、`summary.json`；若目标目录已有 Artifact，会在模型调用前拒绝，不覆盖旧结果，
也不会为了发现目录冲突再次付费调用。`PHASE4_CASE_IDS` 仅用于显式选取
Core / AQ04 子集；正式 Primary 不设置它。AQ01、AQ02、AQ19 在 T4R 未批准时始终作为独立 Research Gate
的 `NOT_MEASURED` 记录，不要求 Brave Key。pytest 的执行成功只证明请求与记录完成；逐 Case Rubric、
Critical Failure、Protected Set 与 Repeat Gate 必须根据 Artifact 人工复核，不得把 `PENDING` 写成 PASS。
Artifact 的 Manifest 包含 0.1 完整 Case / Rubric Fixture、0.2 Target Manifest、固定模型与 Endpoint
元数据；Run Record 另外保存实际 Conversation Citation-mode System Prompt 的 Hash。

### Phase 4 Final Output Tool 独立能力实验

`tests/evaluation/test_phase4_final_output_spike_online.py` 是测试专用的配对入口，不修改 Production
Agent、当前 JSON 输出路径或 30 秒 Wall-clock Ceiling。它在同一固定 GOOG Quote Fixture、模型、
Endpoint 与预算下，依次测试与当前机制同类的 JSON 文本输出协议和 PydanticAI `ToolOutput`；
它不是完整 Production Agent 路径的 A/B Eval。两臂都必须先调用只读
`get_fixture_quote`；PositionPilot 的 Source / inline Citation 校验保持独立。`ToolOutput` 会改变
Provider Request 中的输出工具 Schema / Tool Choice，因此本实验仅比较可观察结果，不主张两条路径
内部 Payload 完全相同。单次配对 Smoke 也不是可靠性或成本统计结论。
输出工具仅使用最小 `answer / source_refs` Schema；它通过不证明完整生产 Schema 与 AQ07 Prompt 兼容。
本实验显式设置 `ToolOutput.max_retries=0`，使两臂都只使用 Application 层一次 Repair；
`framework_output_retry_count` 仅用于确认没有隐藏重试，不代表已评估框架原生 Retry 策略。

在本地先按既有流程把 `.env` 中的 Credential 导入当前 Shell；Agent 不读取该文件。使用未存在的
Artifact 目录执行：

```bash
RUN_PHASE4_FINAL_OUTPUT_SPIKE=1 \
LLM_PROVIDER=ALIYUN_MODEL_STUDIO \
LLM_MODEL=qwen3.7-max \
FINAL_OUTPUT_ARTIFACT_DIR=build/evaluation-runs/p4-final-output-spike/r1 \
PYTHONPATH=backend:tests/evaluation \
.venv/bin/pytest tests/evaluation/test_phase4_final_output_spike_online.py -m online -s -v
```

进程环境还须已有 `LLM_API_KEY` 与当前 Region 的 `LLM_BASE_URL`。每臂上限 30 秒、最多一次
Application Repair，输出 `report.json`；标准输出只显示摘要。Artifact 记录首次输出合法性与错误类别、
Repair 是否触发及其耗时、Framework Output Retry 次数、模型请求次数及各次耗时、工具调用、Token Usage
（未报告则 `UNKNOWN`）、总耗时、成本 `UNKNOWN` 和原始固定 Fixture 候选。请勿把原始 Artifact 当作
公开脱敏日志。`pytest PASSED` 只表示实验执行和记录完成；人工先核对金融 Tool → Final Output
Tool 顺序、Source / Citation 合法性、两臂首次输出与最终输出、Repair、Latency、Token / Cost 可测性和
Provider 错误。独立成功不代表 AQ07 修复或 4A Gate PASS。
只有两个路径均产生有效首个输出且观测到正确 Tool 顺序，才能说该固定场景兼容；
若 Usage 为 `UNKNOWN`，成本也保持 `UNKNOWN`，不据耗时推断费用。可测 Token 仅作为相对成本线索，
正式费用比较仍需确定相同计费口径与重复样本。

2026-09-24 的独立 r1 中，`ToolOutput` 首次输出通过，JSON 文本及其一次 Repair 均未通过；
这不是完整 AQ07。受限 Production Adapter 调整已获 Human Approval 且离线验证通过。
下一步使用原 `PHASE4_CASE_IDS=AQ07` 入口作完整 AQ07 回归，核对真实 Tool Trace、首次候选、
Repair、Source / Citation 与 30 秒预算。若 AQ07 仍失败，先定位 Provider Schema / Tool Choice、
模型提前结束、结构格式、Source 校验或超时；只有确有必要时才做仅限 Eval 的 30/60 秒对照，
分别记录首个模型输出、工具调用与 Repair 耗时，不直接提高 Production 上限。

Ask Quality 的 Research Capability 指 Runtime 真实向 Agent 提供并允许使用的外部事实获取机制，
可以是自定义 Search Tool、Provider / Model Native Web Search、Page Fetch 或 Multi-round Research
Loop；模型训练知识不算 Search。Research Sufficiency 只评价本次 Runtime 实际可用能力的使用情况，
缺失的产品能力单独进入 Capability Coverage。AQ04、AQ12、AQ18、AQ19 已在 Phase 1 被观察，后续
称为 Protected Evaluation Set：不得按具体 wording 直接调优，但可用于 Regression；真正 unseen
holdout 需在后续另建。

以下能力推迟到 V1 完成后再评估：Large-scale Dataset、Paraphrase / Prompt Variation、Adversarial Evaluation、Historical Market Scenario Dataset、Investment Backtesting、Statistical Confidence Analysis、Automated LLM-as-a-Judge、Large-scale Regression Benchmark、Latency / Token / Cost Optimization Benchmark、Recommendation Consistency Benchmark 与 Multi-model Ensemble Evaluation。


### Phase 4B / T7 有限 Strategy Eval

入口 `tests/evaluation/test_phase4_strategy_online.py`，显式 `RUN_PHASE4_STRATEGY_EVAL=1`；
只接受 GOOGLE_GEMINI / gemini-3.8-flash 和 AQ13–AQ16，不自动运行 Repeat / Research / Earnings。
候选配置通过 `PHASE4_CANDIDATE_CONFIG` 指定，在线请求前核对 clean commit 与实际 Native
Prompt / Schema / Tool Policy / 四案例脚本。API Key 仍只读进程 `GEMINI_API_KEY`，无 Base URL 要求。

四个 Case 共 6 次 Ask；每个 Case 独立 SQLite 数据库，真实 Conversation / Strategy Service / UoW
处理确认、失效、过期与版本。Seed User/Assistant 属于明确的 Fixture Setup，不是模型生成证据。
AQ13 从独立 Thread / 重建 Service 读取确认的 Thesis / Horizon；AQ14 使用真实 INVALIDATED 与
过期 Pending；AQ15 模型提出目标配置的 INVALIDATE Candidate，再由确定性测试步骤模拟显式确认，
最后在新 Thread 重新提问；AQ16 同 Thread 验证未确认建议。详见独立 `phase4b-strategy-v1` Overlay，
不改写 Dataset 0.1 或历史 4A Artifact。旧分批计划不是允许的持久 Payload，ACTIVE 也没有自动过期
状态，Overlay 如实表达当前 Contract，而不是伪造删除 / STALE 已完成。

COMPLETED / pytest pass 仅代表 Runtime 与流程执行；Behavioral、Critical Gate 和 Rubric 等待
Human Review。没有合法失效 Candidate 时后续步骤 NOT_RUN，记录 INCOMPLETE / Behavioral finding，
不填补草案；传输失败仍是 NOT_EVALUATED。Memory Production / online 使用 NoOp，背景过滤与
Ledger 不被覆盖只用离线 Fixture 验证。本轮不接数据库 Memory 或 Web Search。
