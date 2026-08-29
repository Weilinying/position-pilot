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
- `RUN_REAL_LLM_BEHAVIORAL_EVAL=1`：显式启用真实模型；
- `LLM_MODEL`：本轮实际候选模型；
- `EVAL_RUN_ID`：同一实验的稳定标识；
- `EVAL_REPETITION_INDEX`：从 1 开始的正整数。
- `EVAL_ROUTING_RESPONSE_FORMAT`：Evaluation-only RCA 开关，支持 `text`（默认）或 `json_object`；只覆盖带 Tool 的 Routing Completion。

`LLM_BASE_URL` 和 `LLM_REQUEST_TIMEOUT_SECONDS` 可覆盖当前 Adapter 默认配置。Harness 不读取 Repository `.env`。

## Reproducibility

每个 Case Report 与 Session Summary 记录：

- Dataset Version、Provider、Model、Routing Response Format；
- Git Revision、Run ID、Repetition Index、Started At；
- Status、Tool Trace、Repair / Invalid JSON、Request Failure；
- Retrieved / Declared Sources、Answer、Human Checks 与现有诊断指标。

Git Revision 无法读取时记录 `UNKNOWN`，不阻断 Eval；存在已跟踪未提交修改时追加 `-dirty`。正式 Model Comparison 应使用相同 Dataset、Git Revision、Prompt、Tool Contract、Fixtures 和 Evaluation Rules，并保持工作区干净。

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

以下能力推迟到 V1 完成后再评估：Large-scale Dataset、Paraphrase / Prompt Variation、Adversarial Evaluation、Historical Market Scenario Dataset、Investment Backtesting、Statistical Confidence Analysis、Automated LLM-as-a-Judge、Large-scale Regression Benchmark、Latency / Token / Cost Optimization Benchmark、Recommendation Consistency Benchmark 与 Multi-model Ensemble Evaluation。
