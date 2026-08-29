# 2026-08-28 M6 Corrected-contract Model Comparison

## Status

**MODEL SELECTED — M6 Human Accepted 2026-08-29**

本实验在修正后统一 Contract 下比较模型能力。原 2026-08-27 Comparison 的原始观察保留，Model Ranking 因 Routing Response Format Confound 已失效。

## Frozen Contract

```text
Dataset Version: 1.0
Provider: ALIYUN_MODEL_STUDIO
Routing Completion: TEXT
Final / Repair Completion: JSON_OBJECT
Same Prompt / Tools / Fixtures / Evaluation Rules
Only Model changes
```

Candidates：

- `qwen3.7-plus-2026-05-26`
- `qwen3.8-max`
- `deepseek-v4-pro-0813`

## Existing Controlled Evidence

| Case | Qwen 3.7 Plus | Qwen 3.8 Max | DeepSeek V4 Pro |
|---|---|---|---|
| `cash_only_no_tool` | TEXT Automated 3 / 3 | TEXT Automated 3 / 3 | TEXT Automated 3 / 3 |
| `market_context_normal` | TEXT Automated 3 / 3 | TEXT Automated 3 / 3 | TEXT Automated 3 / 3 |

该 Evidence 来自显式 `TEXT` Controlled RCA；Production 决策前后的有效 Routing / Final Contract 一致。Run ID、Repair、Routing Variance 与 Human Grounding 仍按原报告保留，不用两个 Case 单独形成 Model Selection。

## New Comparison Matrix

以下 5 个高区分度 Case 作为修正后比较矩阵：

- `unspecified_ticker_no_tool`
- `market_context_high_stress`
- `low_cash_personalization`
- `high_cash_personalization`
- `position_reduction_discretionary`

| Case | Qwen 3.7 Plus | Qwen 3.8 Max | DeepSeek V4 Pro | Failure / Variance |
|---|---|---|---|---|
| `unspecified_ticker_no_tool` | Automated 0 / 3 | Automated 3 / 3 | Automated 3 / 3 | Qwen 3.7 一次多调用 Quote、两次 Timeout；DeepSeek 3 / 3 Repair |
| `market_context_high_stress` | Automated 3 / 3 | Automated 3 / 3 | Automated 3 / 3 | Tool Trace 均正确，Human Grounding 有差异 |
| `low_cash_personalization` | Automated 3 / 3 | Automated 3 / 3 | Automated 3 / 3 | Human Grounding 差异明显 |
| `high_cash_personalization` | Automated 3 / 3 | Automated 3 / 3 | Automated 3 / 3 | Human Grounding 差异明显 |
| `position_reduction_discretionary` | Automated 0 / 3 | Automated 0 / 3 | Automated 3 / 3 | Qwen 3.7 Final 3 / 3 Timeout；Qwen 3.8 3 / 3 遗漏 Quote |

原计划上限为 45 Case Runs。初期 Adaptive Evaluation 先完成 Qwen 3.8 / DeepSeek 各 15 Case Runs；目标明确为可对外解释的三模型完整比较后，再补齐 Qwen 3.7 的 15 Case Runs。最终矩阵为三模型各 `5 cases × 3 repetitions`，共 45 Case Runs。

不使用 `pass@3`；单次成功不抵消其他 Repetition 失败。Qwen 3.7 的 5 次 Request Timeout 单独记录，不伪装成 Behavioral Grounding Failure，也不从 Automated 分母移除。

## Corrected-contract Results

| Model | Automated | Request Success | Repair | Routing Failure | Hard Failure |
|---|---:|---:|---:|---:|---:|
| `qwen3.7-plus-2026-05-26` | 9 / 15 | 10 / 15 | 0 | 1 Unauthorized | 0 |
| `qwen3.8-max` | 12 / 15 | 15 / 15 | 0 | 3 / 15 | 0 |
| `deepseek-v4-pro-0813` | 15 / 15 | 15 / 15 | 3 | 0 / 15 | 0 |

Qwen 3.7 在 `position_reduction_discretionary` 3 / 3 与 `unspecified_ticker_no_tool` 2 / 3 发生 Provider Timeout；唯一成功的 `unspecified_ticker_no_tool` 多调用 GOOG Quote。Qwen 3.8 在 `position_reduction_discretionary` 3 / 3 只选择 Market Context，遗漏必需 GOOG Quote。DeepSeek 15 / 15 Tool Trace 满足 Automated Contract；`unspecified_ticker_no_tool` 3 / 3 首轮非法 JSON，均经一次 Repair 恢复，作为 Quality Signal。

## Human Factual Grounding

| Model | Purchase Execution | Historical BUY | Market Regime | Recommendation Boundary |
|---|---:|---:|---:|---:|
| `qwen3.7-plus-2026-05-26` | 4 / 6 | 0 / 6 strict pass | 2 / 3 strict pass | N/A：0 / 3 Request Success |
| `qwen3.8-max` | 6 / 6 | 1 / 6 | 1 / 3 strict pass | 3 / 3 |
| `deepseek-v4-pro-0813` | 6 / 6 | 6 / 6 | 3 / 3 | 2 / 3 |

Qwen 3.7 在 Low / High Cash 两次把 Cash / Quote 数值关系解释为足以或不足以购买一股；只有一次提到 190 / 210 / 220，但未按 Position Type 绑定，严格 Historical BUY Grounding 为 0 / 6。High Stress 一次将达到 `-10%` 表述为超过阈值。Qwen 3.8 在 Low / High Cash 稳定保留可执行购买数量 `UNKNOWN`，但只有一次引用实际 Historical BUY 位置；High Stress 只有一次完整声明 SPY 为美国大盘股代理。DeepSeek 在三次 Low / High Cash 对照中均使用 190 / 210 / 220 实际 BUY 位置，并完整保留 Purchase Boundary 与 Market Regime 限制；Reduction Repetition 1 仍使用通用 SWING 语义给出倾向性优先顺序，记为 Recommendation Quality Failure。

Qwen 3.8 / DeepSeek 的 `unspecified_ticker_no_tool` 均没有调用 Tool，但回答未完整明示 `current_market_value_weight=UNAVAILABLE`；该 Case-specific Human Limitation 不影响 Tool Selection 结论。Qwen 3.7 唯一成功回答还多调用 GOOG Quote。

## Post-change Qwen 3.7 Full Baseline

Production Routing 改为 `TEXT` 后，Qwen 3.7 完成一次 24-Case Full Dataset：Automated 18 / 24，Request Success 24 / 24，2 次可恢复 Repair，0 Hard Failure。

6 个 Automated Failure 均属 Tool Routing Quality Signal：`cash_only_no_tool`、`position_type_distinction`、`missing_position_is_absence`、`post_earnings_unknown`、`unspecified_ticker_no_tool` 多调用 Quote；`position_reduction_discretionary` 遗漏 GOOG Quote。Human Grounding 仍发现 Low Cash Purchase Boundary、Low / High Cash Historical BUY 与 Position Reduction Recommendation Boundary Failure。

本轮 metadata 的 `git_revision` 只记录 HEAD `a269bc0...`，未标记 tracked dirty worktree。Harness 已按 Finding 修正；后续运行会追加 `-dirty`。

## DeepSeek Full Dataset

DeepSeek 在相同修正 Contract 下完成一次 24-Case Full Dataset：Automated 22 / 24，Request Success 24 / 24，5 个 Case 经一次 Repair 恢复，0 Hard Failure。

`position_type_distinction` 多调用 GOOG Quote；`post_earnings_unknown` 多调用 GOOG Quote 与 Market Context。两者均保持缺失事实为 `UNKNOWN`，未突破 Tool Budget、伪造 Source 或混淆 Failure Status，记为 Unauthorized Tool Call Quality Signal。

Repair 分布：`positions_only_no_tool` 与 `unspecified_ticker_no_tool` 为非法 JSON；`position_type_distinction`、`quote_provider_failure` 与 `market_context_provider_failure` 为 Structured Source Repair。全部在一次 Repair 内恢复。

Human Factual Grounding 保留 4 个 Case-specific Quality Signal：`high_cash_personalization` 未引用实际 Historical BUY；`position_reduction_discretionary` 使用通用 SWING 语义给出倾向；`position_reduction_rule_check` 未说明具体 Trade Plan / Exit Condition 不在 Context；`unspecified_ticker_no_tool` 未明确声明 Current Market Value Weight `UNAVAILABLE`。其余关键 Case 未发现虚构当前事实、Position Type 混淆、Purchase Execution 越界或 Market Regime 边界失守。

## Qwen 3.8 Full Dataset

Qwen 3.8 在相同修正 Contract 下完成一次 24-Case Full Dataset：Automated 22 / 24，Request Success 24 / 24，0 Repair，0 Hard Failure。

`quote_provider_failure` 遗漏 TSLA Quote；`position_reduction_discretionary` 遗漏 GOOG Quote。两个回答均未补造当前价格或混淆已取得的 Provider Result，记为 Required Tool Miss Quality Signal。

Human Factual Grounding 保留 Case-specific Quality Signal：Low / High Cash 均未引用实际 Historical BUY；`position_reduction_rule_check` 未说明具体 Trade Plan / Exit Condition 不在 Context；`unspecified_ticker_no_tool` 未明确声明 Current Market Value Weight `UNAVAILABLE`。Purchase Execution、Position Type 与 Market Regime 边界未发现 Hard Failure。

## Evaluation

Hard Failure 单独记录，不被其他成功抵消。Automated Evaluation 比较 Request Success、Required Tool Recall、Unauthorized Tool Calls、Status / Failure Taxonomy 与 Repair。Human Factual Grounding 比较 Purchase Execution Boundary、Historical BUY、Market Regime Proxy / Heuristic、Position Type 与 Recommendation Strength。

## Decision

- Selected Model：`deepseek-v4-pro-0813`
- Full Dataset：Qwen 3.7 Automated 18 / 24；Qwen 3.8 与 DeepSeek 均为 22 / 24；三者 Request Success 均为 24 / 24、Hard Failure 均为 0
- Selected Matrix：Qwen 3.7 Automated 9 / 15、Request Success 10 / 15；Qwen 3.8 Automated 12 / 15、Request Success 15 / 15；DeepSeek Automated 与 Request Success 均为 15 / 15
- 主要理由：DeepSeek 的 Required Tool Recall、Historical BUY 与 Market Regime Grounding 最强；当前固定 timeout 下也未出现 Request Failure
- Trade-off：DeepSeek Full Repair 5 / 24、Selected Repair 3 / 15，并有一次 Reduction Recommendation Quality Failure；Qwen 3.8 Repair 为 0，但稳定遗漏 Reduction Quote 且 Historical BUY 较弱
- Human Decision：2026-08-29 批准
- Production Default：`deepseek-v4-pro-0813`
- Provider / Prompt / Tool / Architecture Change：无
- Human Acceptance：接受已记录的 DeepSeek Quality Signals；DeepSeek Real-model Eval 与既有真实 Provider / Agent Smoke 分层覆盖，不重复组合 Online Smoke
- Environment Limitation：PostgreSQL Integration 因未配置 `TEST_DATABASE_URL` 跳过
