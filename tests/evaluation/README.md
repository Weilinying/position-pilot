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

真实 LLM + 真实 Market Data 另见 `tests/integration/test_investment_agent_online.py`，只作为少量 Smoke Test，不作为本 Behavioral Eval 的主要依据。
