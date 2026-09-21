# PositionPilot V1 Evaluation

## Purpose

M6 Evaluation 验证 PositionPilot V1 核心 Agent Behavior 是否能稳定、重复地满足产品边界，并为基础 Model Selection 提供证据。它不评估投资收益，也不是通用 LLM Benchmark 或历史回测平台。

## Evaluation Layers

### Deterministic / Automated Checks

pytest 负责验证 Tool Selection / Trace、参数与预算、Response Status、Structured Output、Repair、Invalid Tool Call、Source Contract、Provider Failure 与 Request Failure。Fake Portfolio、Market、News 和 Market Regime Fixtures 隔离实时数据波动。

### Human Factual Grounding Checks

Human Review 负责判断自由文本是否：

- 越过 `UNKNOWN` 或 Source Boundary；
- 把 Cash / Quote 数值关系错误解释为实际购买能力；
- 正确使用 Historical BUY Facts 与 `LONG_TERM` / `SWING`；
- 把 Market Regime 或 Position Type 转化成过强建议；
- 出现自动规则无法低误报识别的事实错误或推荐强度问题。

`Automated Pass != Human Grounding Pass`。合法 `source_refs` 只证明来源声明满足 Application Contract，不证明每个自然语言 Claim 正确。

## Dataset

当前 Dataset Version 为 `1.0`，定义在 `tests/evaluation/test_real_model_behavior.py`。每个 `BehavioralCase` 包含固定问题、Portfolio 与 Provider Fixtures、Automated Tool / Status Expectations、Human Checks，以及存在时的 Case-specific Known Limitation。

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

Ask Quality 的 Research Capability 指 Runtime 真实向 Agent 提供并允许使用的外部事实获取机制，
可以是自定义 Search Tool、Provider / Model Native Web Search、Page Fetch 或 Multi-round Research
Loop；模型训练知识不算 Search。Research Sufficiency 只评价本次 Runtime 实际可用能力的使用情况，
缺失的产品能力单独进入 Capability Coverage。AQ04、AQ12、AQ18、AQ19 已在 Phase 1 被观察，后续
称为 Protected Evaluation Set：不得按具体 wording 直接调优，但可用于 Regression；真正 unseen
holdout 需在后续另建。

以下能力推迟到 V1 完成后再评估：Large-scale Dataset、Paraphrase / Prompt Variation、Adversarial Evaluation、Historical Market Scenario Dataset、Investment Backtesting、Statistical Confidence Analysis、Automated LLM-as-a-Judge、Large-scale Regression Benchmark、Latency / Token / Cost Optimization Benchmark、Recommendation Consistency Benchmark 与 Multi-model Ensemble Evaluation。
