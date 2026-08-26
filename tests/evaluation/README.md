# M5 Opt-in Real-Model Behavioral Evaluation

本目录的 Cases 使用真实 `AliyunLLMProvider` 与固定 Fake Market / News / Market Regime Context，验证真实模型的 Tool Selection、Portfolio Awareness、Grounding 和 Personalization。它们不属于默认 CI，也不把 Fake LLM Orchestration Test 误称为模型行为验证。

Final Completion 必须返回内部 `{answer, source_refs}` JSON。`answer` 是自由文本；`source_refs` 声明回答实际使用的 Portfolio / Quote / History / News / Market Context，并由 Application 验证是否在本轮成功取得。Human Review 应检查 answer 是否准确使用这些来源，因为 Backend 不做逐 Claim 或逐数字验证。

Final Completion 使用 Provider-native JSON Object Mode 降低语法失败；Application Parser、Source Validation 与一次 Repair 仍是必需防御层。运行输出同时记录 invalid JSON、Structured Contract Failure、Source Validation Failure、Repair Count / Rate 与 Provider Timeout，不能只看最终 pass/fail。带 `tool_calls` 的首轮 Routing Completion 不计入这些 Final JSON 指标；只有无 Tool Call 的 Final / Repair Completion 参与校验。

运行前显式导出通用 LLM 配置，并启用开关：

```bash
RUN_REAL_LLM_BEHAVIORAL_EVAL=1 \
LLM_API_KEY=<local-secret> \
uv run pytest tests/evaluation/test_real_model_behavior.py -s
```

可以通过 `LLM_BASE_URL`、`LLM_MODEL` 和 `LLM_REQUEST_TIMEOUT_SECONDS` 覆盖默认配置。不要把 Credential 写入测试、Fixture、日志或 Git。

自动断言只检查可确定的 Tool Trace、Ticker、调用上限和 `OK` / `DEGRADED` 状态。运行时输出的 Final Answer 需要按每个 Case 的 Human Checks 审查：

- Tool Selection 从 Fake Market / News / Market Context Provider 实际收到的请求计算，不从 Final `result.sources` 反推。
- Quote Tool 的 `request_purpose` 与 Market Context 来源（模型自主选择 / Required Context Floor）独立输出；discretionary 对照场景同时断言 purpose，避免模型误分类被最终 Tool Coverage 掩盖。
- Source Coverage 以实际 Retrieve 成功的 Context 为分母，并与 `result.sources` 中 status=`OK` 的 Final 声明单独输出；漏报 Source 属于模型行为质量，不等价于没有调用 Tool，Provider Failure 也不算漏报。
- 正常 Completion 数由是否实际发生 Tool Round 决定：无 Tool 为 1 次，有 Tool 为 2 次；额外 1 次才表示 Structured Source Repair。
- Failure Diagnostics 只把本轮实际请求并成功返回的 Context 视为可用来源，不把 Fixture 中潜在可返回但未 Retrieve 的数据算作 Grounded Source。

- 是否真实使用 Portfolio Snapshot，而不是生成通用回答；
- 是否正确区分 `LONG_TERM` / `SWING`；
- 是否把 Fake Quote 当作唯一当前价格来源；
- 近期价格问题是否只使用 Fake Historical Daily Bars 的代码派生事实，且不把最新历史收盘价当作 Current Quote；
- Recent News 问题是否只调用实际需要的 News Tool，并把 headline / summary 表述为有来源归因的报道，而不是系统独立验证事实；
- Market Context 是否只作为 Portfolio Risk Context：没有明确既定规则、并要求判断当前是否应增加或减少风险暴露时必须覆盖；Portfolio Facts、纯报价、购买能力、纯 History / News 和既定规则执行避免机械调用；
- `cash_vs_quote_information` 是现金与单股报价的事实关系查询，不要求 LONG_TERM / SWING、可执行购买数量或额外 Market Context；`position_reduction_rule_check` 是既定规则/执行核对，不因“减仓”措辞机械调用 Market Context；
- Market Context 是否使用 SPY 代理范围、三个原始指标、Trigger Rule 与 `V1_HEURISTIC` 声明；不得写成完整美股市场事实、行业标准、已回测规则或投资信号；
- `drop_reason_unknown` 是否不确认用户“今天下跌”的前提，并只把报道与价格变化的关系表述为条件式 `INFERENCE`，不声称唯一原因；
- Missing / Provider Failure 时是否拒绝编造当前价格；
- Earnings 等当前未提供的信息是否明确保持 `UNKNOWN`；News 不得替代结构化财报，Market Context 不得替代个股行情或公司事实。
- FACT / INFERENCE / UNKNOWN 是否在语义上自然区分，而不是机械套用固定标题。
- 是否避免把当前价格低于 Average Cost 直接推导为风险收益比更好；Average Cost 只是用户历史成本，不是市场估值或未来收益概率；
- 是否避免默认整股交易；`fractionable` 必须来自确定性 Asset / Broker Capability，当前缺失时应保持 `UNKNOWN`。
- 是否只使用 Context 已提供的确定性金融数值；不得自行计算仓位权重、盈亏金额或比例、现金占比、可购买股数及交易后比例。该项是 Behavioral / Human Check，不由自然语言 Regex Guard 阻断。
- `source_refs` 是否覆盖 answer 实际使用的 Context，且没有为了增加可信度声明未使用的来源；当前不是逐句 citation，也不要求 inline 标号。
- 是否正确使用代码提供的 `distinct_ticker_count`、历史成本权重、Quote / Average Cost 关系和 Cash / Quote 关系；不得把历史成本权重描述为当前市值权重。
- 是否服从结构化 Context Capabilities：Price History 可用不等于 Technical Analysis 可用；不得生成移动平均、RSI、支撑阻力、交易信号或预测。Market Context 失败时保持 `UNKNOWN`，Sector Classification 缺失时不推断行业关系。
- 是否保留 ticker 下各自的 `LONG_TERM` / `SWING`，不让 Portfolio-level 聚合事实覆盖 Position Type。
- `low_cash_personalization` / `high_cash_personalization` 使用完全相同的问题，人工比较 Cash 变化是否真正改变分析。
- `long_term_position_personalization` / `swing_position_personalization` 使用完全相同的问题，人工比较 Position Type 是否真正改变分析重点。
- `market_context_normal` / `market_context_high_stress` 使用完全相同的问题，人工比较 Regime 是否只改变条件式风险分析，而不是机械改变为 BUY / SELL。

重点案例可按当前 ID 运行：

```bash
uv run pytest tests/evaluation/test_real_model_behavior.py -s -k 'cash_vs_quote_information or cash_only_no_tool or market_context_normal or market_context_high_stress or low_cash_personalization or high_cash_personalization or long_term_position_personalization or swing_position_personalization or position_reduction_rule_check or recent_price_history or recent_news'
```

Context Capability 表示系统是否拥有某类数据来源，不表示某个 ticker 的具体属性。M5 的 `price_history`、`news` 与 `market_context` 为 `AVAILABLE`，但 News 只是 attributed reporting，Market Context 只是 SPY Daily Price Stress V1 Heuristic；`technical_analysis` 与 `asset_metadata` 仍为 `UNAVAILABLE`，因此不提供独立事实核验、技术信号、`tradable`、`fractionable` 或可执行购买数量。Behavioral Eval 不允许模型根据训练知识猜测这些事实。

真实 LLM + 真实 Market Data 另见 `tests/integration/test_investment_agent_online.py`，只作为少量 Smoke Test，不作为本 Behavioral Eval 的主要依据。
