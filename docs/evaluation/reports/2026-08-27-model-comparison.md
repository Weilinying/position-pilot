# 2026-08-27 M6 Model Comparison

## Status

**DIAGNOSTIC EVIDENCE RETAINED — Model-ranking conclusion superseded**

三个 Candidates 均已完成三次运行。原始观察对 `tools + response_format=json_object` Contract 仍有效；该 Contract 对 Qwen 3.8 / DeepSeek Tool Calling 形成 Confound，因此原 Model Ranking 不再作为模型能力或选型结论。

## Environment

| Field | Value |
|---|---|
| Dataset Version | `1.0` |
| Git Revision | `a269bc0d5534b7d37cf4047b95a86e3f7e4e175b` |
| Provider | `ALIYUN_MODEL_STUDIO` |
| Models | `qwen3.7-plus-2026-05-26` / `qwen3.8-max` / `deepseek-v4-pro-0813` |
| Cases | 8 affected Cases |
| Repetitions | 3 per Model / Case |
| Run ID | `2026-08-27-model-comparison` |
| Date | 2026-08-27 |

本轮在包含未提交 Evaluation Harness / Documentation 修改的工作区运行；后续候选必须保持相同 Dataset、Harness 与 Production Runtime 状态，实验报告可持续更新。该 HEAD Revision 不能单独重建完整运行状态，正式 Acceptance 前应使用可重建的干净 Revision 复验胜出候选。

报告中的 Model 是发送给 Provider 的实际 Request Configuration。当前 Adapter 不保留 Provider Response 顶层 `model` 字段，因此不能独立验证 Provider 后端别名解析结果；不同 Candidate 的 Repair、Failure 与 Answer Pattern 明显不同，但正式复验应补充 Provider-side Model Evidence，且不得为此增加 Production Instrumentation。

## Validity

- 保留：各 Model 在原 Contract 下的 Request、Tool Trace、Repair 与 Human Grounding 原始结果。
- 失效：`qwen3.7-plus-2026-05-26` 作为 Comparative Leader 的模型能力推论。
- 原因：Controlled Contrast 证明 Qwen 3.8 / DeepSeek 在 Routing `TEXT` 下恢复 Native Tool Calls。
- 后续：修正后实验单独记录于 [2026-08-28 Corrected-contract Model Comparison](./2026-08-28-corrected-contract-model-comparison.md)。

## Aggregate Results

| Model | Request Success | Automated Pass | Human Grounding Pass | Repairs | Unauthorized Tool Calls | Provider Status |
|---|---:|---:|---:|---:|---:|---|
| `qwen3.7-plus-2026-05-26` | 21 / 24 | 15 / 24 | 15 / 21 successful responses | 3 | 8 calls / 6 case runs | Supported；3 timeouts |
| `qwen3.8-max` | 22 / 24 | 12 / 24 | 12 / 22 successful responses | 7 | 0 | Supported；2 structured request failures |
| `deepseek-v4-pro-0813` | 24 / 24 | 12 / 24 | 12 / 24 successful responses | 2 | 0 | Supported；no request failure |

分母必须写明实际执行次数；Provider 不支持的 Candidate 不计为已运行通过。

## Case Results

`Human x / y` 是对成功 Answer 的人工 Factual Grounding 复核：分子表示通过全部相关 Human Boolean 的回答数，分母表示可复核的成功回答数。Tool Selection 只计入 Automated Results，不在 Human 分数中重复扣分。

| Case | Qwen 3.7 Plus | Qwen 3.8 Max | DeepSeek V4 Pro | Variance / Failure Category |
|---|---|---|---|---|
| `cash_only_no_tool` | Automated 3 / 3；Human 3 / 3 | Automated 3 / 3；Human 3 / 3 | Automated 3 / 3；Human 3 / 3 | Qwen 3.7：3 / 3 Repair；其余稳定通过 |
| `positions_only_no_tool` | Automated 1 / 3；Human 3 / 3 | Automated 3 / 3；Human 3 / 3 | Automated 3 / 3；Human 3 / 3 | Qwen 3.7 Repetitions 1 and 3 多调用 Quote |
| `missing_position_is_absence` | Automated 2 / 3；Human 3 / 3 | Automated 3 / 3；Human 3 / 3 | Automated 3 / 3；Human 3 / 3 | Qwen 3.7 Repetition 2 多调用 Quote |
| `market_context_normal` | Automated 3 / 3；Human 3 / 3 | Automated 0 / 3；Human 0 / 3 | Automated 0 / 3；Human 0 / 3 | Qwen 3.8 / DeepSeek 三次均未调用 Quote / Market Context |
| `low_cash_personalization` | Automated 3 / 3；Human 0 / 3 | Automated 0 / 3；Human 0 / 2 | Automated 0 / 3；Human 0 / 3 | Qwen 3.7 越过 Purchase Boundary；其他模型漏 Tool |
| `high_cash_personalization` | Automated 2 / 3；Human 0 / 2 | Automated 0 / 3；Human 0 / 2 | Automated 0 / 3；Human 0 / 3 | Qwen 3.7 一次 Timeout；其他模型漏 Tool |
| `position_reduction_discretionary` | Automated 1 / 3；Human 0 / 1 | Automated 0 / 3；Human 0 / 3 | Automated 0 / 3；Human 0 / 3 | Qwen 3.7 两次 Timeout；其他模型漏 Tool |
| `unspecified_ticker_no_tool` | Automated 0 / 3；Human 3 / 3 | Automated 3 / 3；Human 3 / 3 | Automated 3 / 3；Human 3 / 3 | Qwen 3.7 三次多调用 Quote；其他模型稳定通过 |

每格记录 3 次独立结果，不使用 `pass@3` 合并。

## Human Factual Grounding

以下 PASS / FAIL 是对实际 Answer 的人工审阅结论，不是 Harness 自动生成字段。只填写与对应 Case 相关的 Boolean / `N/A`；单项通过不代表该 Answer 的全部 Human Checks 通过。

| Model | Purchase Execution | Historical BUY | Position Type | Market Regime | Recommendation Strength |
|---|---|---|---|---|---|
| `qwen3.7-plus-2026-05-26` | FAIL：Low Cash 0 / 3；High Cash 1 / 2 | FAIL：0 / 5 successful Cash Contrast responses | PASS | PASS | FAIL：Reduction 0 / 1 |
| `qwen3.8-max` | FAIL：Low Cash 1 / 2；High Cash 1 / 2 | FAIL：3 / 4 successful Cash Contrast responses | PASS | FAIL：0 / 10 relevant successful responses | PASS |
| `deepseek-v4-pro-0813` | FAIL：Low Cash 1 / 3；High Cash 1 / 3 | FAIL：2 / 6 successful Cash Contrast responses | PASS | FAIL：0 / 12 relevant successful responses | FAIL：11 / 12 relevant successful responses |

## Failure Analysis

### Qwen 3.7 Plus

- `PROVIDER_FAILURE`：3 / 24 Request 因 Model Studio Timeout 失败；模型受当前 Account 支持，不属于 Unsupported Candidate。
- `TOOL_SELECTION`：6 / 24 Case Runs 出现多余 Quote，共 8 次。`unspecified_ticker_no_tool` 3 / 3 失败，`positions_only_no_tool` 2 / 3 失败，`missing_position_is_absence` 1 / 3 失败。
- `STRUCTURED_OUTPUT`：`cash_only_no_tool` 3 / 3 首轮产生非法 JSON，均经一次 Repair 恢复；作为重复 Quality Signal 记录。
- `GROUNDING`：`low_cash_personalization` 3 / 3 把 Cash / Quote 数值关系解释为不能买入或不能执行一股；成功的 Low / High Cash 回答 5 / 5 均只复述 Average Cost，未引用实际 Historical BUY 价格。
- `RECOMMENDATION_BOUNDARY`：唯一成功的 Reduction 回答把 HIGH_STRESS 扩展为“下行趋势”，并给出偏强的 SWING 优先卖出理由，未保留缺失 Trade Plan / Exit Condition / Risk Budget 的约束。

### Qwen 3.8 Max

- `TOOL_SELECTION`：四个纯 Portfolio Cases 12 / 12 通过且没有多余调用；10 / 10 个成功返回的 Tool-required Case Runs 均未调用 Quote / Market Context，共漏掉 20 次必需调用。其余 2 次为 Structured Request Failure，没有可用 Routing Trace。
- `STRUCTURED_OUTPUT`：7 / 24 Case Runs 发生 Source Contract Repair；5 次恢复，2 次 Repair 后仍引用未取得的 Source，形成 Hard Request Failure。未出现 Invalid JSON 或 Provider Timeout。
- `GROUNDING`：成功的 Cash Contrast 回答中 3 / 4 准确引用 LONG_TERM 190 / 210 与 SWING 220 的实际 BUY 价格，优于 Qwen 3.7；但所有 Tool-required 回答都缺少固定 Quote / Market Regime 事实。
- `PURCHASE_EXECUTION_BOUNDARY`：4 个成功 Cash Contrast 回答中 2 个完整保留可执行数量为 UNKNOWN；Low Cash Repetition 1 把现金描述为执行整股加仓的硬约束，High Cash Repetition 2 未明确保留 Executable Quantity Contract。
- `RECOMMENDATION_BOUNDARY`：成功回答保持条件式或 UNKNOWN，没有把 Market Regime 直接转化为 BUY / SELL；但因为从未取得 Market Context，不能视为完整 Case Grounding Pass。

### Interim Comparison

- Qwen 3.7 Plus 能调用必需 Tool，但存在过度调用与路由波动；Qwen 3.8 Max 的 No-Tool 选择稳定，却系统性跳过全部必需 Tool。
- Qwen 3.8 Max 的 Historical BUY Grounding 与 Purchase Boundary 较好，但 Automated Pass、Repair Rate 与完整 Context Grounding 均弱于 Qwen 3.7 Plus。

### DeepSeek V4 Pro

- `TOOL_SELECTION`：四个纯 Portfolio Cases 12 / 12 通过且没有多余调用；12 / 12 个 Tool-required Case Runs 均未调用 Quote / Market Context，共漏掉 24 次必需调用。
- `STRUCTURED_OUTPUT`：2 / 24 Case Runs 发生 Structured Contract Repair，均成功恢复；没有 Invalid JSON、Source Contract Failure、Request Failure 或 Provider Timeout。
- `GROUNDING`：成功的 Cash Contrast 回答中 2 / 6 引用 LONG_TERM 190 / 210 与 SWING 220 的实际 BUY 价格；所有 Tool-required 回答均缺少固定 Quote / Market Regime。
- `PURCHASE_EXECUTION_BOUNDARY`：Low / High Cash 各 1 / 3 完整保留可执行数量为 UNKNOWN；Low Cash Repetition 3 再次把 Cash / Quote 条件解释为“连一股都买不了”。
- `RECOMMENDATION_BOUNDARY`：11 / 12 相关回答保持条件式或 UNKNOWN；Reduction Repetition 2 使用“SWING 通常更适合优先减仓”的通用规则，超出当前 Structured Context。

### Final Comparison

- Qwen 3.7 Plus 的 Automated / Human Complete Pass 最高，并且能实际调用必需 Tool，但仍有过度调用、Provider Timeout、Purchase Boundary 与 Historical BUY Grounding Failure。
- Qwen 3.8 Max 与 DeepSeek V4 Pro 在相同 4 个 No-Tool Cases 上稳定，在相同 4 个 Tool-required Cases 上系统性失败；二者的 Repair / Request Failure Pattern 不同，不能仅因 pytest 汇总相同就视为同一模型行为。
- 当前证据提示后续 RCA 应优先验证 Model Studio 对各 Model ID 的 Native Function Calling 支持，以及 Routing Completion 同时使用 `tools` 与 `response_format=json_object` 的兼容性；不预设修改 Prompt、Guard 或 Architecture。
- DeepSeek `market_context_normal` Controlled RCA：默认 `JSON_OBJECT` 在原三次 Model Comparison 与一次 RCA 对照中均为 0 Tool Calls，Automated 0 / 4；`TEXT` 3 / 3 调用 GOOG Quote 与 SPY Market Context，Final 使用 `JSON_OBJECT`，0 Repair / Automated 3 / 3。
- Qwen 3.8 `market_context_normal` 在默认 `JSON_OBJECT` 下 Automated 0 / 3；`TEXT` 3 / 3 恢复 GOOG Quote + SPY Market Context，Final 使用 `JSON_OBJECT`，0 Repair / Automated 3 / 3。
- 跨模型结果进一步支持 Routing Format Compatibility RCA；Production 首轮同时承担 No-Tool Final Answer，因此补充代表性 Cash Case 检查 `TEXT` 相对默认基线的 Invalid JSON、Repair 与 Request Failure。
- `cash_only_no_tool` 使用 `TEXT` 时三个模型均 Automated 3 / 3、0 Tool、0 Request Failure。Qwen 3.7 Repair 3 / 3、Qwen 3.8 Repair 0 / 3，均与默认基线一致；DeepSeek Repair 1 / 3，相比默认 0 / 3 轻微退化但成功恢复。
- 代表性 No-Tool Case 没有阻断性 Regression。Production 默认 Qwen 3.7 的 `market_context_normal + TEXT` Automated 3 / 3，完整取得 GOOG Quote 与 SPY Market Context，0 Repair / Invalid JSON / Request Failure。
- Qwen 3.7 三次中 2 次由模型选择 Market Context，1 次由 Required Context Floor 补齐；一次把 `300 < 210.25` 误述为真。前者记为 Routing Variance，后者记为 Human Factual Grounding Failure，均属 Quality Signal。

## Decision

- Model Selection：**INCONCLUSIVE / SUPERSEDED**
- 历史相对结果：`qwen3.7-plus-2026-05-26` 在原 Contract 下领先，不作为模型选型依据
- Routing Format Decision：已批准并应用 Production 首轮 Routing Completion `TEXT`；Final 与 Repair 保持 `JSON_OBJECT`
- 理由：`TEXT` 在三个候选模型上恢复或保持代表性 Tool 路径，代表性 No-Tool Case 未出现阻断性退化
- 是否需要 Architecture Change：否；不拆分 Routing / Final 阶段，不修改 Prompt 或 Tool Contract
- 推迟到 V1 后的问题：保持 Evaluation README 的 V1 Scope Boundary，不扩大 Benchmark 或 Multi-Agent Architecture

8-Case Comparison 不构成 M6 Acceptance，也不会自动修改 Production 默认模型。
