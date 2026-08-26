# ADR 0007：使用 SPY Daily Price Stress 构建 V1 Market Regime

## 状态

已接受（2026-08-26）

## 背景

M5 要求 Agent 根据 User Intent、Portfolio Context 与当前市场状态选择最小充分 Context。M4 已提供 Current Quote、Recent Price History 与 Recent News，但 `market_context` 仍为 `UNAVAILABLE`，因此系统无法独立验证“整体市场很差”等用户前提，也无法让 Market Regime 在相关建仓、加仓或减仓问题中影响分析。

Market Regime 必须由确定性代码生成。数据来源、阈值、公共 Source Type 和 Routing 行为会影响金融语义与 API Contract，因此本方案在实现前进入 Human Review Gate，并于 2026-08-26 获得批准。

## 候选方案

### SPY Daily Price Stress + 现有 Alpaca Provider

- 复用 ADR 0004 已批准的 Alpaca Historical Daily OHLCV、SIP Feed、`adjustment=all`、Credential 与 Failure Mapping。
- SPY 是可通过现有股票 / ETF 数据边界获取的美国大盘股代理，无需增加 Provider。
- Daily Close 可以确定性计算近期收益、回撤与实现波动率，但不能代表 VIX、市场宽度、宏观风险、盘中状态或完整美股市场。

### FRED / Cboe VIX

- VIX 直接表达由 S&P 500 期权价格反映的近期期望波动率，金融含义比 SPY 实现波动率更接近“预期波动”。
- FRED 提供 Daily Close，但会增加新 Provider、Credential / Usage Boundary 与 Adapter；Daily Frequency 也不能解决盘中市场状态。
- 当前 M5 没有证据证明这些成本优于复用已有 Provider，后续可在 Eval 证明 SPY Heuristic 不足时重新评估。

### 不实现 Market Regime

- 复杂度最低，但无法满足 M5 Done Criteria，也无法解决现有 `market_context_unknown` Evaluation Failure。

## 决策

- 使用 `SPY` 作为 V1 美国大盘股 Market Proxy；所有输出必须明确其代理边界。
- 使用 Alpaca 最近 90 个日历日内最多 60 根调整后 Daily Bars，查询结束时间至少落后当前 15 分钟；少于 21 根有效 Bars 时返回 `NO_DATA`，不形成 Regime。
- 使用最新 21 根 Close 计算：
  - `five_session_return_percent`：最新 Close 相对 5 个 Session 前 Close 的收益率；
  - `twenty_session_close_drawdown_percent`：最新 Close 相对最近 20 个 Session 最高 Close 的回撤；
  - `twenty_session_annualized_realized_volatility_percent`：20 个 Daily Simple Close Returns 的 Sample Standard Deviation × `sqrt(252)`。
- 三个指标使用 Decimal、百分比单位、4 位小数 Half-even；Regime 分类使用同一已量化值。
- 按任一指标触发的最高严重度分类：
  - `ELEVATED_VOLATILITY`：Volatility ≥ 25%，或 Drawdown ≤ -5%，或 5-session Return ≤ -3%；
  - `HIGH_STRESS`：Volatility ≥ 40%，或 Drawdown ≤ -10%，或 5-session Return ≤ -6%；
  - `EXTREME_STRESS`：Volatility ≥ 60%，或 Drawdown ≤ -15%，或 5-session Return ≤ -10%；
  - 其余为 `NORMAL`。
- 输出保留全部指标原始值、触发规则、Observation Count、Period、Source、Feed、Coverage、Currency、Adjustment 与 Fetched At。
- Methodology 固定标记为 `V1_HEURISTIC` / `1.0`，并显式声明：阈值是工程启发式规则，不是行业标准、未经历史回测验证，也不是投资信号。
- 新增无参数内部 Tool `get_market_context()`；LLM 不能选择 Proxy、窗口、指标或阈值。
- 当前建仓 / 加仓 / 减仓、整体市场风险与 Regime 问题需要 Market Context。纯 Portfolio Facts、Current Price、Recent Price History 或 Recent News 问题不机械调用。
- Tool Failure 使用既有 Market Data Failure Taxonomy，最终 Answer 标记为 `DEGRADED` 并保持 Regime `UNKNOWN`。
- Public Source Type 增加 `MARKET_CONTEXT`，其 `ticker=SPY`；其他 Response 字段不变。
- 单轮最多 4 次 Tool Call 的预算保持不变。

## 理由

- 该方案满足 M5 的最小闭环，同时复用现有 Provider 与 Adapter，不增加新 Credential、Infrastructure 或 Framework。
- 三个输入分别保留短期价格变化、近期回撤与实现波动率，且全部由确定性代码产生、可独立测试和追踪。
- 公开 Methodology、原始值与 Trigger Rule 可以防止把 Regime 当作黑盒金融事实，并为后续 Eval / Backtest 调整提供稳定证据。

## Trade-off

- SPY 主要代表美国大盘股，不能代表 Nasdaq、小盘股、市场宽度、跨资产压力或个股特有风险。
- Daily Price Stress 不是 VIX，也不能表达期权市场的前瞻波动预期。
- 固定阈值没有经过 PositionPilot 历史回测，不应被表述为行业标准或 BUY / SELL Signal。
- 90 日查询和 21 根计算窗口优先简单、稳定与低成本，无法覆盖长期市场周期。
- 单轮调用预算保持 4，复杂的多标的多 Context 问题可能需要明确降级，而不是无界增加 Tool Call。

## 重新考虑条件

- Behavioral Eval 或真实使用表明 SPY Regime 经常遗漏明显市场压力，或对个股问题产生误导。
- Backtest 证明当前阈值导致不可接受的误报 / 漏报，或新的阈值具有可重复优势。
- 产品需要 VIX、市场宽度、主要指数、盘中状态、宏观事件或 Sector Context。
- Alpaca 的覆盖、价格、许可、接口或数据质量发生显著变化。
- 新 Provider 能在来源、Freshness、成本与授权边界上提供经过验证的明显优势。

## 参考

- [Alpaca Historical Bars](https://docs.alpaca.markets/us/v1.4.2/reference/stockbars)
- [Cboe VIX](https://www.cboe.com/en/tradable-products/vix/)
- [FRED VIXCLS](https://fred.stlouisfed.org/series/VIXCLS/)
