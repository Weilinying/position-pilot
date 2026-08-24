# M3 Opt-in Real-Model Behavioral Evaluation

本目录的 Cases 使用真实 `AliyunLLMProvider` 与固定 Fake Market Data，验证真实模型的 Tool Selection、Portfolio Awareness、Grounding 和 Personalization。它们不属于默认 CI，也不把 Fake LLM Orchestration Test 误称为模型行为验证。

运行前显式导出通用 LLM 配置，并启用开关：

```bash
RUN_REAL_LLM_BEHAVIORAL_EVAL=1 \
LLM_API_KEY=<local-secret> \
uv run pytest tests/evaluation/test_real_model_behavior.py -s
```

可以通过 `LLM_BASE_URL`、`LLM_MODEL` 和 `LLM_REQUEST_TIMEOUT_SECONDS` 覆盖默认配置。不要把 Credential 写入测试、Fixture、日志或 Git。

自动断言只检查可确定的 Tool Trace、Ticker、调用上限和 `OK` / `DEGRADED` 状态。运行时输出的 Final Answer 需要按每个 Case 的 Human Checks 审查：

- 是否真实使用 Portfolio Snapshot，而不是生成通用回答；
- 是否正确区分 `LONG_TERM` / `SWING`；
- 是否把 Fake Quote 当作唯一当前价格来源；
- Missing / Provider Failure 时是否拒绝编造当前价格；
- News、Earnings、Market Context 等 M3 未提供的信息是否明确保持 `UNKNOWN`；
- FACT / INFERENCE / UNKNOWN 是否在语义上自然区分，而不是机械套用固定标题。
- 是否避免把当前价格低于 Average Cost 直接推导为风险收益比更好；Average Cost 只是用户历史成本，不是市场估值或未来收益概率；
- 是否避免默认整股交易；`fractionable` 必须来自确定性 Asset / Broker Capability，当前缺失时应保持 `UNKNOWN`。
- 是否只使用 Context 已提供的确定性金融数值；不得自行计算仓位权重、盈亏金额或比例、现金占比、可购买股数及交易后比例。
- `low_cash_personalization` / `high_cash_personalization` 使用完全相同的问题，人工比较 Cash 变化是否真正改变分析。
- `long_term_position_personalization` / `swing_position_personalization` 使用完全相同的问题，人工比较 Position Type 是否真正改变分析重点。

M3 不提供 Asset Trading Capability。`tradable` 与 `fractionable` 是后续接入 Broker / Asset Metadata 时的明确扩展点；Behavioral Eval 不允许模型根据训练知识猜测这些字段，也不要求为了该能力接入真实 Alpaca。

真实 LLM + 真实 Market Data 另见 `tests/integration/test_investment_agent_online.py`，只作为少量 Smoke Test，不作为本 Behavioral Eval 的主要依据。
