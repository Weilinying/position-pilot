# ADR 0004：M2 Market Data Provider 使用 Alpaca

## 状态

已接受（2026-08-21）

## 背景

M2 需要为 M3 的第一个 Agent 闭环提供美股和美国上市 ETF 的 Current Quote、基础 Historical OHLCV、Volume、Market Timestamp 和明确的 Provider Error State。当前价格必须来自足够新的外部数据，Provider 还必须能被隔离和 Mock，不能进入 Portfolio Domain。

该选择会引入外部凭据、数据覆盖与授权限制，属于 Human Review Gate。2026-08-21 经 Human Review 批准使用 Alpaca Market Data API v2 REST。

## 候选方案

### Alpaca Market Data API v2

- Basic Plan 免费覆盖美股与美国 ETF，历史数据自 2016 年起，历史 REST 限额 200 requests/min。
- 免费实时数据只覆盖 IEX；完整实时 SIP 需要付费。免费账户可查询至少落后当前 15 分钟的历史 SIP 数据。
- Snapshot 同时返回 latest trade、latest quote、minute bar、daily bar 与 previous daily bar；Historical Bars 原生提供 OHLCV、分页、feed、timestamp 与 corporate-action adjustment 参数。
- Provider、feed 和时间戳语义在官方 API 中明确，适合将覆盖限制暴露给上层，而不是把有限数据伪装成完整市场事实。

参考：[Alpaca Market Data Plans](https://docs.alpaca.markets/us/docs/about-market-data-api)、[Market Data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq)、[Snapshot API](https://docs.alpaca.markets/us/reference/stocksnapshotsingle)、[Historical Bars API](https://docs.alpaca.markets/us/reference/stockbars)。

### yfinance

- Python 使用简单、适合研究和快速探索，也能取得行情与历史数据。
- yfinance 明确说明其不受 Yahoo 认可或审核，使用公开 API，定位为研究与教育用途；Yahoo Finance 数据用途还受个人使用条款约束。
- 它不是 PositionPilot 可以依赖的正式 Provider Contract，认证、响应和上游接口稳定性也不如面向开发者的受支持 API 明确。

参考：[yfinance README 与法律说明](https://github.com/ranaroussi/yfinance/blob/main/README.md)。

### Massive

- 数据覆盖和 API 设计完整，提供全市场 SIP、Snapshots 与 OHLCV。
- 免费 Stocks Basic 只有 End-of-Day 数据、5 requests/min；满足 15 分钟延迟 Snapshot 的 Starter Plan 为 USD 29/月。
- 免费层不能满足 M2 Current Quote 的新鲜度目标，当前阶段没有足够收益证明应承担付费方案。

参考：[Massive Stocks Plans](https://www.massive.com/stocks)、[Massive Stocks REST API](https://massive.com/docs/rest/stocks)。

### Alpha Vantage

- API 成熟，覆盖 Quote、Time Series 和大量派生数据。
- 免费层只有 25 requests/day；实时与 15 分钟延迟美国股票数据为 Premium 能力。
- 限额和实时数据门槛不适合 M3 的按需 Context 获取。

参考：[Alpha Vantage Support](https://www.alphavantage.co/support/)、[Premium Plans](https://www.alphavantage.co/premium/)。

### Twelve Data

- 免费 Basic 声明支持实时美国股票与 ETF，提供 Quote 与 Time Series，接口满足 M2 字段需求。
- 免费层限制为 8 API credits/min、800/day，并限定 internal non-display usage；公开说明对具体美国市场 feed 覆盖不如 Alpaca 的 IEX/SIP 区分明确。
- 可以作为重新考虑时的低成本候选，但当前优先选择来源边界更可解释、限额更宽松的 Alpaca。

参考：[Twelve Data Pricing](https://twelvedata.com/pricing)、[API Documentation](https://twelvedata.com/docs)。

## 决策

- M2 使用 Alpaca Market Data API v2 REST，不使用 Trading API 执行交易。
- 开发默认使用 Basic Plan：Current Quote 使用实时 `iex` feed；Historical Daily OHLCV 使用 `sip` feed，并要求查询结束时间至少落后当前 15 分钟。
- Historical Bars 使用 `adjustment=all`，由 Provider 处理拆股、现金分红与 spin-off 对历史 OHLCV 的调整；M2 不自行实现 Corporate Action Engine。
- 输出必须显式保留 `source=ALPACA`、feed、coverage、currency、market timestamp 与 fetched timestamp。IEX 必须标记为 single-exchange coverage，不能表述为完整 SIP / NBBO。
- Current Quote 使用 Snapshot 中的 latest eligible trade 作为 last price，并按可用情况返回 bid / ask 及其独立 timestamp。
- Domain / Application 依赖 Provider Protocol 和稳定 Schema；Alpaca JSON、HTTP 状态码和凭据只存在于 Integration Adapter。
- 使用 Python 标准库实现最小同步 REST Transport，不引入 `alpaca-py`、Cache、Queue、Database Table 或新 Framework。
- 正常无数据与 Provider Failure 必须区分。M2 稳定状态至少包含 `OK`、`NO_DATA`、`INVALID_SYMBOL`、`INVALID_REQUEST`、`AUTHENTICATION_FAILED`、`RATE_LIMITED`、`PROVIDER_UNAVAILABLE` 和 `INVALID_PROVIDER_RESPONSE`。
- API Key ID 与 Secret Key 仅通过环境变量提供；`.env.example` 只保存安全占位值，日志和错误不得暴露 Secret。

## 理由

- Alpaca Basic 已覆盖 M2 的最小闭环，无需先承担付费方案或引入交易能力。
- 明确暴露 IEX 与 SIP 差异符合金融事实的 Source / Timestamp / UNKNOWN 原则。
- 直接 REST Adapter 的依赖面小，Provider 可替换，Unit Test 可以完全使用 Fake Transport，不访问真实 API。
- 使用延迟 SIP 历史数据可获得比 IEX 更完整的 OHLCV，同时不会把延迟数据冒充实时数据。

## Trade-off

- 免费 Current Quote 只来自 IEX，低流动性标的可能比全市场交易更陈旧；调用方必须检查 feed、coverage 和 market timestamp。
- Current Quote 与 Historical OHLCV 来自不同 feed，Volume 不能直接假设为同一覆盖口径。
- `adjustment=all` 适合连续历史分析，但不等于未经调整的真实成交记录；输出必须保留 adjustment 元数据。
- 实际在线验证需要用户在本地提供 Alpaca 凭据；CI 与 Unit Test 不依赖真实凭据。

## 重新考虑条件

- M3 Evaluation 证明 IEX 当前数据不足以支持核心问题。
- 产品需要完整实时 SIP / NBBO、商业展示授权、SLA 或更高可用性。
- Alpaca 的价格、授权、限额、接口或数据质量发生显著变化。
- Twelve Data、Massive 或其他 Provider 在覆盖、许可与成本上形成经过验证的优势。
