# M2 — Minimal Market Data 执行计划

## 1. 状态与目标

**Status:** IN PROGRESS

M2 只为 M3 第一个 Agent 闭环提供最小、真实、可追溯的美股与美国 ETF 行情，不建设完整 Market Intelligence Platform。

## 2. 已批准语义

- Provider 使用 Alpaca Market Data API v2 REST，见 ADR 0004。
- Current Quote 默认来自实时 IEX Snapshot，并明确标记 single-exchange coverage。
- Historical OHLCV 使用至少延迟 15 分钟的 SIP `1Day` bars，`adjustment=all`。
- Quote 与 Bar 使用 Decimal，保留 Provider、feed、coverage、currency、market timestamp 和 fetched timestamp。
- 正常无数据、非法输入、认证失败、限流、Provider 不可用和非法响应必须结构化区分。
- Provider 与 HTTP 细节不得进入 Portfolio Domain；Unit Test 不访问真实 API。

## 3. Scope

- 建立无具体 Provider 依赖的 Market Quote、OHLCV Bar、Result Status 与 Error Schema。
- 建立 Market Data Application Service 和 Provider Protocol。
- 实现最小同步 Alpaca REST Adapter、分页、超时和 HTTP / Payload Failure 映射。
- 增加 Alpaca 环境配置与安全 `.env.example`。
- 覆盖输入校验、正常 Quote、历史 OHLCV、空结果、错误映射、非法响应和分页测试。
- 使用本地凭据执行可选的在线 smoke test；凭据不存在时明确报告，不让常规 Unit Test 失败。
- M2 稳定后更新 Architecture 和 Completion Summary。

## 4. Non-Goals

- 不实现 WebSocket streaming、自动刷新、缓存、行情持久化或后台任务。
- 不实现技术指标、VIX、Market Regime、News、Fundamentals 或 Corporate Action Engine。
- 不实现 Portfolio REST API、Market Data REST API、Agent Tool、LLM 或 Agent Routing。
- 不引入第二个 Market Data Provider，不实现自动 Provider fallback。
- 不实现交易、下单或 Alpaca Brokerage Account 接入。
- 不进入 M3。

## 5. Acceptance Criteria

- 可按规范化 Ticker 获取结构化 Current Quote，包含 last price、可选 bid / ask、source、IEX feed、coverage 与时间戳。
- 可按 Ticker 与时间范围获取按时间升序的 SIP Daily OHLCV，并处理分页。
- 所有价格字段使用 Decimal；OHLC 关系、Volume 与时区数据经过确定性校验。
- `NO_DATA` 与认证、限流、网络 / 5xx、非法响应等 Failure State 明确不同。
- Alpaca HTTP 与 JSON 细节被限制在 Integration Adapter，Application 只依赖 Protocol。
- API Key 不硬编码、不进入 Git，也不出现在错误信息中。
- Unit Test 不依赖真实外部 API；如存在本地凭据，在线 smoke test 验证真实 Quote 与 Historical Bars。
- pytest、Ruff format / lint、mypy 与 dependency check 通过。
- 没有 M3 或未来能力。

## 6. 执行顺序

```text
T1 ADR / Plan / Config Contract
  ↓
T2 Market Data Domain Schema + Application Protocol
  ↓
T3 Alpaca REST Adapter + Failure Mapping
  ↓
T4 Unit Tests + Optional Online Smoke Test
  ↓
T5 Full Tests / Quality Checks
  ↓
T6 主线程 Automated Review → 修复 → 再验证
  ↓
Atomic Commits → Human Acceptance
```

Market Data Schema、Provider Protocol 与 Alpaca Adapter 具有直接接口依赖，默认由主线程串行实现。
