# ADR 0006：M4 News Provider 使用 Alpaca Historical News

## 状态

已接受（2026-08-25）

## 背景

M4 的 `drop_reason_unknown` Behavioral Case 已证明 Agent 缺少近期事件 Context。Recent Price History 只能描述 Daily Price Path，不能回答近期有哪些报道，也不能证明某个事件导致价格变化。`PROJECT.md` 将 News Provider 保持为未决定，因此进入实现前需要 Human Review。

M4 只需要一个小型、按需、可追溯的 Recent News Tool，不建设新闻搜索平台、全文抓取、情绪模型或因果推断系统。

## 候选方案

### Alpaca Historical News REST API

- 与已批准的 Alpaca Market Data 共用 `data.alpaca.markets`、API Key Headers 和同步 REST Transport 设计，不新增 Secret 或 SDK。
- `/v1beta1/news` 支持 symbols、start / end、排序、limit 和分页；Historical News 官方文档声明数据可追溯至 2015 年。
- 当前 News 上游由 Benzinga 提供。系统可以同时保留 `provider=ALPACA` 与文章级 reporting source，而不是把聚合入口冒充原始报道机构。
- Endpoint 仍是 beta，具体账户 Entitlement 需要 opt-in Online Smoke Test 验证。

### 直接接入 Benzinga

- 原始 Provider 边界更直接，也可能提供更完整的产品能力。
- 需要新增账户、Credential、费用 / 许可评估和独立集成；当前 V1 没有证据证明这些成本能改善核心场景。

### SEC Filings

- 适合未来 Earnings / Filing Context，来源权威。
- 不覆盖一般公司新闻与市场事件，不能解决当前 Recent News Failure。

### 暂不接入 News

- 不增加 Provider 风险。
- `drop_reason_unknown` 继续没有任何近期事件事实，无法改善 M4 目标场景。

## 决策

- M4 Recent News 使用 Alpaca Historical News REST API，当前上游 reporting source 为 Benzinga。
- News 使用独立的 Provider-neutral Domain Schema、`NewsService` 和 `NewsProvider`，不并入 Quote / OHLCV 的 `MarketDataService`。
- 复用现有 Alpaca Credentials、HTTPS Base URL 和同步 JSON Transport 设计，不增加 Secret、Database、Cache、Queue、SDK 或 Framework。
- Agent 暴露内部 Tool `get_recent_news(ticker)`。Application 固定最近 5 个日历日、结束时间至少落后 15 分钟、最多 5 篇、倒序；模型不能控制时间、条数、URL 或关键词。
- 请求 `include_content=false`，不获取或抓取正文。只保留有界 headline、可选 summary、author、article id、URL、reporting source、symbols、created / updated timestamps 与 fetched timestamp。
- Current Quote、Recent Price History 与 Recent News 共用一个 Tool Round；单轮 Tool Call Budget 最多 4 次。Agent 仍按问题实际需要选择 Tool，不默认调用全部 Context Tools。
- 公共 API `sources[].type` 增加 `RECENT_NEWS`。`market_timestamp` 对 News 保持空值，文章时间保留在 Tool Result；`fetched_at` 表示本次 News 获取时间。
- `NO_NEWS_FOUND` 只表示当前 Provider 在指定 ticker 和时间窗口内没有返回文章，不表示不存在相关新闻、事件或股价驱动因素。
- News Result 是 attributed reporting。Agent 必须区分“来源报道声称 X”和“X 已被系统独立验证”，保留来源归因，不得把报道自动升级为确定事实。
- News 与价格变化的关系最多是条件式 `INFERENCE`。Recent News 不证明用户前提中的价格变化，也不证明某篇报道是唯一原因。
- News 不替代 Earnings / Fundamentals，不从 headline 或 summary 补造 EPS、Revenue、Guidance、Valuation 或其他结构化财务事实。

## 理由

- 该方案以最小新增依赖解决已经存在的 Evaluation Failure，同时保留 Provider-neutral Application Boundary。
- 固定窗口、小上限和 no-content policy 限制 Token、Latency、版权内容暴露与外部文本注入面。
- 独立 News Status 可以清晰区分局部空结果与认证、限流、Provider Failure，避免把 `NO_DATA` 泛化成“没有事件”。
- 强制 attribution 与 causality boundary 符合 PositionPilot 的 `FACT / INFERENCE / UNKNOWN` 原则。

## Trade-off

- `/v1beta1/news` 仍为 beta，接口和 Entitlement 可能变化；Adapter 和 Online Smoke Test 必须隔离此风险。
- 当前只使用 Benzinga 单一上游，不代表完整新闻覆盖。没有返回文章不能证明市场不存在其他报道或事件。
- 最近 5 个日历日、最多 5 篇是 V1 的受控 Context Window，可能遗漏更早或更多报道；它不是通用新闻检索。
- headline 与 summary 是来源报道文本，不是 PositionPilot 独立事实核验；自然语言归因质量仍需要 Behavioral Evaluation 和 Human Review。
- 不读取正文降低内容风险和复杂度，但也限制事件细节。

## 重新考虑条件

- Alpaca News beta Endpoint、许可、定价、Entitlement 或稳定性无法满足 V1。
- Behavioral Eval 证明单一 Benzinga 上游、5 日窗口或 5 篇上限无法覆盖核心问题。
- 产品需要结构化 Earnings、Filings、宏观新闻、更多来源交叉验证或商业展示授权。
- attributed reporting 与因果边界无法通过现有 Single Agent 稳定保持。

## 参考

- [Alpaca News Articles API](https://docs.alpaca.markets/us/reference/news-3)
- [Alpaca Historical News Data](https://docs.alpaca.markets/us/docs/historical-news-data)
- [Alpaca Market Data Plans](https://docs.alpaca.markets/us/docs/about-market-data-api)
