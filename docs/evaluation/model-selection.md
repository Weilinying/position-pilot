# M6 Model Selection

## Status

**DECISION APPLIED — DeepSeek default；M6 Human Accepted**

本实验只比较模型，不修改 Production 默认模型、Prompt、Tool Contract、Agent Architecture 或 Dataset。

## Frozen Comparison Contract

```text
Same Dataset
Same Git Revision
Same Prompt
Same Tool Contract
Same Fixtures
Same Evaluation Rules
Only Model changes
```

候选模型：

- `qwen3.7-plus-2026-05-26`
- `qwen3.8-max`
- `deepseek-v4-pro-0813`

Harness 当前使用阿里云 Model Studio `AliyunLLMProvider`。如果当前 Account / Provider 不支持某个 Model ID 或其 JSON / Function Calling Contract，应记录 `PROVIDER_FAILURE` 并停止该候选，不修改 Adapter 强行适配。

## Initial Comparison Dataset

本阶段的原始结果保留，但 Model Ranking 因 Routing Response Format Confound 已标记为 Superseded。

第一阶段固定以下 8 个已受影响 Cases，每个 Model × Case 重复 3 次：

- `cash_only_no_tool`
- `positions_only_no_tool`
- `missing_position_is_absence`
- `market_context_normal`
- `low_cash_personalization`
- `high_cash_personalization`
- `position_reduction_discretionary`
- `unspecified_ticker_no_tool`

上限为 `8 cases × 3 repetitions × 3 models = 72 case runs`。不使用 `pass@3`；一次成功不能抵消同模型其他 Repetition 的失败。

## Execution

Human Review 批准实验后，在相同 Commit 和干净工作区中逐个候选执行。先运行 Repetition 1：

```bash
export EVAL_RUN_ID=2026-08-27-model-comparison
export CASE_FILTER='cash_only_no_tool or positions_only_no_tool or missing_position_is_absence or market_context_normal or low_cash_personalization or high_cash_personalization or position_reduction_discretionary or unspecified_ticker_no_tool'
export MODEL=qwen3.7-plus-2026-05-26

RUN_REAL_LLM_BEHAVIORAL_EVAL=1 \
LLM_MODEL="$MODEL" \
EVAL_REPETITION_INDEX=1 \
uv run pytest tests/evaluation/test_real_model_behavior.py -s -k "$CASE_FILTER"
```

确认该 Model ID 受当前 Provider / Account 支持后，再完成 Repetition 2 / 3：

```bash
for repetition in 2 3; do
  RUN_REAL_LLM_BEHAVIORAL_EVAL=1 \
  LLM_MODEL="$MODEL" \
  EVAL_REPETITION_INDEX="$repetition" \
  uv run pytest tests/evaluation/test_real_model_behavior.py -s -k "$CASE_FILTER"
done
```

对三个 Candidate 分别执行上述流程。Credential 只保留在本地 Process Environment。普通 Behavioral Case Failure 仍继续三次；只有确认是 `PROVIDER_FAILURE` 或 Model ID 不受支持时，才停止该候选并记录实际错误。pytest 非零退出本身不等同于 Provider Failure。

## Function Calling RCA

三个 Candidate 完成后，Qwen 3.8 Max 与 DeepSeek V4 Pro 在全部 Tool-required Cases 上均未产生 Native Tool Calls。为区分 Model Capability 与 `tools + response_format=json_object` 兼容性，只对同一 `market_context_normal` Case 做 Evaluation-only 对照：

```bash
export MODEL=deepseek-v4-pro-0813

for format in json_object text; do
  RUN_REAL_LLM_BEHAVIORAL_EVAL=1 \
  LLM_MODEL="$MODEL" \
  EVAL_RUN_ID="2026-08-27-function-calling-rca-$MODEL-$format" \
  EVAL_REPETITION_INDEX=1 \
  EVAL_ROUTING_RESPONSE_FORMAT="$format" \
  uv run pytest tests/evaluation/test_real_model_behavior.py -s \
    -k market_context_normal
done
```

开关只覆盖带 Tool 的首轮 Routing Completion；Final Answer 与 Repair 继续使用 `JSON_OBJECT`。RCA 期间默认值为 `json_object`；Human Decision 批准后，Production 与 Evaluation 默认均已同步为 `text`，`json_object` 仅保留为回归对照。

DeepSeek 对照结果：

- `JSON_OBJECT`：原 Model Comparison 三次与 RCA 对照一次均为 0 Tool Calls，Automated 0 / 4；
- `TEXT`：3 / 3 调用 GOOG Quote 与 SPY Market Context，随后 Final Completion 固定使用 `JSON_OBJECT`，0 Repair，Automated 3 / 3。

Qwen 3.8 Max 在原 Model Comparison 的默认 `JSON_OBJECT` 中 Automated 0 / 3；相同 Case 改为 `TEXT` 后同样 3 / 3 调用 GOOG Quote 与 SPY Market Context，Final 使用 `JSON_OBJECT`，0 Repair并通过。

跨模型证据进一步支持 Routing Format Compatibility RCA。Production 首轮同时承担 No-Tool Final Answer，因此使用 `cash_only_no_tool` 比较 `TEXT` 与各模型默认基线的 Invalid JSON、Repair 与 Request Failure；该检查只覆盖代表性 Cash Case。

```bash
for model in qwen3.7-plus-2026-05-26 qwen3.8-max deepseek-v4-pro-0813; do
  for repetition in 1 2 3; do
    RUN_REAL_LLM_BEHAVIORAL_EVAL=1 \
    LLM_MODEL="$model" \
    EVAL_RUN_ID="2026-08-28-no-tool-text-rca-$model" \
    EVAL_REPETITION_INDEX="$repetition" \
    EVAL_ROUTING_RESPONSE_FORMAT=text \
    uv run pytest tests/evaluation/test_real_model_behavior.py -s \
      -k cash_only_no_tool
  done
done
```

No-Tool `TEXT` 结果：三个模型 Automated 均为 3 / 3，且没有 Tool Call 或 Request Failure。Qwen 3.7 Repair 3 / 3，与默认 `JSON_OBJECT` 基线一致；Qwen 3.8 Repair 0 / 3，与基线一致；DeepSeek Repair 1 / 3，相比基线 0 / 3 轻微退化但均成功恢复。

该代表性 Case 未发现阻断性 No-Tool Regression，但不能外推全部 No-Tool 场景。Production 默认模型 Qwen 3.7 在 `market_context_normal + TEXT` 中 Automated 3 / 3，每次都取得 GOOG Quote 与 SPY Market Context，0 Repair / Invalid JSON / Request Failure。其中 2 / 3 由模型选择 Market Context，1 / 3 由 Required Context Floor 补齐；一次回答把 `300 < 210.25` 误述为真，记为 Human Factual Grounding Quality Signal。

Human Decision 已批准并应用最小修改：Production 首轮 Routing Completion 改为 `TEXT`，Final 与 Repair 保持 `JSON_OBJECT`；不更换默认模型，不修改 Prompt、Tool Contract 或 Agent Architecture。

修改后 Qwen 3.7 Full Dataset 已运行一次：Automated 18 / 24，Request Success 24 / 24，2 次可恢复 Repair，0 Hard Failure。6 个失败均为 Tool Routing Quality Signal。下一步只重复代表性 Contrast、历史不稳定与当前 Failure Cases，不重复全量 Dataset。

## Corrected-contract Comparison

原 Comparison 受 `tools + JSON_OBJECT` 兼容性影响，不再用于模型选型。新 Comparison 固定 Routing `TEXT`、Final / Repair `JSON_OBJECT`，复用三模型已完成的 `cash_only_no_tool` 与 `market_context_normal` TEXT Controlled Evidence，并对以下 5 个 Case 重新运行三模型各 3 次：

- `unspecified_ticker_no_tool`
- `market_context_high_stress`
- `low_cash_personalization`
- `high_cash_personalization`
- `position_reduction_discretionary`

新增上限为 `5 cases × 3 repetitions × 3 models = 45 case runs`。初期 Adaptive Evaluation 先完成 Qwen 3.8 / DeepSeek 各 15 Case Runs；目标明确为可对外解释的三模型完整比较后，再补齐 Qwen 3.7 的 15 Case Runs。运行时不显式设置 `EVAL_ROUTING_RESPONSE_FORMAT`，以验证 Production 默认 `TEXT` Contract。

```bash
unset EVAL_ROUTING_RESPONSE_FORMAT

export CASE_FILTER='unspecified_ticker_no_tool or market_context_high_stress or low_cash_personalization or high_cash_personalization or position_reduction_discretionary'
export MODEL=qwen3.7-plus-2026-05-26

RUN_REAL_LLM_BEHAVIORAL_EVAL=1 \
LLM_MODEL="$MODEL" \
EVAL_RUN_ID="2026-08-28-corrected-contract-model-comparison-$MODEL" \
EVAL_REPETITION_INDEX=1 \
uv run pytest tests/evaluation/test_real_model_behavior.py -s \
  -k "$CASE_FILTER"
```

确认该 Model ID 受当前 Provider / Account 支持且未出现候选级 `PROVIDER_FAILURE` 后，再完成 Repetition 2 / 3：

```bash
for repetition in 2 3; do
  RUN_REAL_LLM_BEHAVIORAL_EVAL=1 \
  LLM_MODEL="$MODEL" \
  EVAL_RUN_ID="2026-08-28-corrected-contract-model-comparison-$MODEL" \
  EVAL_REPETITION_INDEX="$repetition" \
  uv run pytest tests/evaluation/test_real_model_behavior.py -s \
    -k "$CASE_FILTER"
done
```

对 Qwen 3.8 / DeepSeek 逐个执行上述流程，每个 Candidate 开始前将 `MODEL` 替换为对应 ID。普通 Behavioral Failure 仍完成三次；只有确认 `PROVIDER_FAILURE` 或 Model ID 不受支持时才停止该 Candidate。pytest 非零退出本身不等同于 Provider Failure。

实际结果：Qwen 3.7 Automated 9 / 15、Request Success 10 / 15、0 Repair，5 次 Provider Timeout 与 1 次 Unauthorized Quote；Qwen 3.8 Automated 12 / 15、Request Success 15 / 15、0 Repair，三次遗漏 Reduction Quote；DeepSeek Automated 15 / 15、Request Success 15 / 15、3 次可恢复 Repair。三模型 Hard Failure 均为 0。

## DeepSeek Full Dataset

`deepseek-v4-pro-0813` 在相同 Contract 下完成一次 24-Case Full Dataset：Automated 22 / 24，Request Success 24 / 24，5 个 Case 经一次 Repair 恢复，0 Hard Failure。

两个 Automated Failure 均为 Unauthorized Tool Call：`position_type_distinction` 多调用 Quote；`post_earnings_unknown` 多调用 Quote 与 Market Context。回答保持缺失事实为 `UNKNOWN`，Failure Taxonomy 与 Source Boundary 正确。

Full Human Factual Grounding 确认 DeepSeek 在 Historical BUY、Purchase Execution 与 Market Regime 上整体优于修改后 Qwen 3.7；代价是 Repair 5 / 24，并保留 Reduction Recommendation、Rule Context 与 Concentration Limitation 等 Case-specific Quality Signal。

## Qwen 3.8 Full Dataset

`qwen3.8-max` 在相同 Contract 下完成一次 24-Case Full Dataset：Automated 22 / 24，Request Success 24 / 24，0 Repair，0 Hard Failure。

两个 Automated Failure 均为 Required Quote Miss：`quote_provider_failure` 遗漏 TSLA Quote；`position_reduction_discretionary` 遗漏 GOOG Quote。回答未补造缺失价格或混淆已取得的 Provider Result。

Full Human Factual Grounding 保留 Historical BUY、Rule Context 与 Concentration Limitation 等 Case-specific Quality Signal。Qwen 3.8 与 DeepSeek 的 Full Automated 均为 22 / 24，但前者 Repair 更少，后者 Required Tool Recall 与 Historical BUY Grounding 更强。

## Evaluation Rules

每个 Case / Repetition 记录：Automated Pass / Fail、Request Success、Tool Selection、Unauthorized Tool Call、Repair、Factual Grounding、Historical BUY Grounding 与 Recommendation Boundary。

Human Review 只对相关 Case 使用 Boolean 或 `N/A`：

- `purchase_execution_boundary_pass`
- `historical_buy_grounding_pass`
- `position_type_boundary_pass`
- `market_regime_boundary_pass`
- `recommendation_strength_pass`

同时保存简短 Evidence；不使用 LLM-as-a-Judge。Run-to-run Variance 本身是质量信号，不能只汇报最佳一次。

## Phase 1 Gate

候选只有在相对 Baseline 表现出更高一致性时，才进入完整 V1 Dataset：

- Request Failure 与 Unauthorized Tool Call 明显减少；
- Tool Selection 更稳定；
- Cash / Quote 不再被解释为实际购买能力；
- Historical BUY Grounding 明显改善；
- Recommendation Boundary 更稳定；
- Repair 作为 Quality Signal 被完整记录。

三模型 Corrected-contract Full Dataset 与 5 Case × 3 Repetitions 均已完成，但不自动等于 M6 Acceptance。综合 Full Dataset、Request Reliability、Routing Variance、Repair 与 Human Grounding，Human Review 于 2026-08-29 批准 `deepseek-v4-pro-0813` 作为默认模型。

## Decision Boundary

Production 默认 Model 已由 `qwen3.7-plus` 更换为 `deepseek-v4-pro-0813`，Provider、Prompt、Tool Contract 与 Agent Architecture 保持不变。Human Acceptance 于 2026-08-29 通过；接受已记录 Quality Signals，并以 DeepSeek Real-model Eval 与既有真实 Provider / Agent Smoke 作为分层证据，不重复组合 Online Smoke。

原始 Diagnostic Evidence 保存在 `docs/evaluation/reports/2026-08-27-model-comparison.md`；修正后结果填写到 `docs/evaluation/reports/2026-08-28-corrected-contract-model-comparison.md`。
