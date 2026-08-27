# M6 V1 Real-model Behavioral Evaluation

Dataset Version `1.0` 使用真实 `AliyunLLMProvider` 与固定 Fake Portfolio、Market、News 和 Market Regime Context，验证真实模型的 Tool Selection、Portfolio Awareness、Grounding 与 Personalization。pytest 继续作为 Evaluation Execution Engine；这些 Cases 不属于默认 CI。

## 运行方式

全量 Real-model Eval 至少运行一次：

```bash
RUN_REAL_LLM_BEHAVIORAL_EVAL=1 \
LLM_API_KEY=<local-secret> \
uv run pytest tests/evaluation/test_real_model_behavior.py -s
```

可通过 `LLM_BASE_URL`、`LLM_MODEL` 和 `LLM_REQUEST_TIMEOUT_SECONDS` 覆盖默认配置。不要把 Credential 写入测试、Fixture、报告、日志或 Git。

只对少量代表性 Controlled Contrast、历史不稳定或实际触发 Repair 的 Cases 重复运行三次。当前重点选择：

```bash
uv run pytest tests/evaluation/test_real_model_behavior.py -s \
  -k 'cash_only_no_tool or low_cash_personalization or high_cash_personalization or long_term_position_personalization or swing_position_personalization or market_context_normal or market_context_high_stress or position_reduction_discretionary or position_reduction_rule_check'
```

## Coverage 与 Controlled Contrast

Dataset 内的 Coverage Matrix 将 V1 Requirement 映射到 Behavioral Case。Unit / Agent Tests 已有的 empty、failure 或 stale Contract Evidence 可以直接用于覆盖判断，不为矩阵对称性强行增加 Real-model Case。

有界历史 BUY Facts 已进入 Portfolio Snapshot；完整 V1 Success Criteria 仍缺少真实模型 Factual Grounding 证据，Dataset 在 Real-model Eval 与 Human Review 完成前保留该 Coverage Gap。

Controlled Contrast 尽量只改变一个输入变量：

- `low_cash_personalization` / `high_cash_personalization` 只改变 Available Cash；
- `long_term_position_personalization` / `swing_position_personalization` 只改变 Position Type；
- `market_context_normal` / `market_context_high_stress` 只改变 Market Regime Fixture；
- `position_reduction_discretionary` / `position_reduction_rule_check` 只改变 User Intent。

Known Limitation 只在与具体 Case 相关时记录，不要求所有 Case 填写。

## Grounding Boundary

Automated Grounding Contract 检查：

- Tool 名称、参数、预算、去重与实际 Provider 请求；
- `OK` / `DEGRADED` 与 Failure Status；
- `source_refs` 只能绑定本轮成功取得的同类型、同 ticker Context；
- Structured Answer、最多一次 Repair 与明确 Request Failure。

Human Factual Grounding 检查：

- Answer 是否准确使用 Portfolio 与 Tool Facts；
- 是否区分 `LONG_TERM` / `SWING`；
- 是否自然区分 `FACT`、`INFERENCE` 与 `UNKNOWN`；
- News attribution、SPY Proxy、V1 Heuristic 与条件式分析是否正确；
- 是否虚构当前事实、财报、技术指标、交易能力或确定性因果。

合法 `source_refs` 不代表每个自然语言 Claim 正确，也不等价于逐 Claim Citation。

## Failure 与质量信号

虚构 Source、突破 Tool Budget、错误 Status、混淆 Provider Failure / `NO_DATA` / `NO_NEWS_FOUND`、补造 `UNKNOWN`，或 Repair 后仍返回不合法成功结果，属于 Hard Contract Failure。出现后先保存 Trace 与 Diagnostics 并完成 Root Cause Analysis，再决定修改 Dataset、Fixture、Prompt、Application Contract 或 Provider Adapter；不预设新增 Guard。

Repair、路由波动、Context Over-call、Source 漏报、Latency 异常和回答差异不足属于 Quality Signal。只有形成稳定 Failure Mode、违反 Acceptance Criteria 或成为 Critical / High Review Finding 时，才驱动 Production 修改。

## 报告

每个 Case 输出 Dataset Version、Requirement、Tool Trace、Retrieved / Declared Source、Status、Completion / Repair、Answer、Human Checks，以及存在时的 Case-specific Known Limitation。Request Failure 同样进入报告并保留 Structured Diagnostics。Session Summary 聚合 `repair_count`、`cases_with_repair`、`repair_case_rate` 与 `request_failure_count`。

Reporter 只使用 Evaluation 层已有数据，不为了补齐 Token、Cost、阶段 Latency 或其他报告字段增加 Production Instrumentation。

## Capability Boundary

当前 `price_history`、`news`、`market_context` 与 `historical_buy_facts` 为 `AVAILABLE`；Historical Buy Facts 是当前 Positions 的有界 BUY 投影，News 只是 attributed reporting，Market Context 只是 SPY Daily Price Stress V1 Heuristic。`earnings`、`fundamentals`、`technical_analysis` 与 `asset_metadata` 仍不可用，不得由模型猜测当前财报、技术信号、`tradable`、`fractionable` 或可执行购买数量。

真实 LLM + 真实 Market Data 见 `tests/integration/test_investment_agent_online.py`。PostgreSQL、Alpaca Market / News 与真实 Agent Online Smoke 作为 Human Acceptance Evidence，不作为受第三方服务状态影响的常规 CI Gate。
