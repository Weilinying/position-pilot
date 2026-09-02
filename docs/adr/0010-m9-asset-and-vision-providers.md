# ADR 0010：M9 使用 Finnhub Asset Metadata 与 Qwen3-VL Recognition

## 状态

已接受（2026-09-02；替代 2026-09-01 的 Massive 选型）

## 背景

M9 需要为一次性 Portfolio Opening State Import 提供两项外部能力：按 symbol / company name
搜索并精确验证 canonical symbol，以及把 Text / Screenshot 转换成可人工审查的 Structured
Draft。两项能力都必须隔离在 Provider-neutral Boundary 后，且 Recognition 不能直接写入
Portfolio。

Human Review 已要求 Phase 0 只做短 Spike。选型只验证搜索、exact validation、美股与 ETF
覆盖、ticker / shares / average cost 识别、Structured Output、图片保存边界和成本，不建设
通用 Provider 研究项目。

### 替代前决策

2026-09-01 Human Review 原先批准 Massive 作为 Asset Metadata Provider，并接受 5 calls/min
免费额度。2026-09-02 Human Review 重新评估了真实使用路径：交互式 Selector 可能连续触发查询，
一次多持仓 Import 还需要对多个 symbol 做 exact validation；Massive 免费额度对这两类请求过于
紧张。已退市股票不是当前主要使用路径，因此不再为了 `ACTIVE / INACTIVE` 状态承担额外的
Provider 请求和 Domain 语义。

## 候选方案

本次只比较原选型 Massive 与替换选项 Finnhub：

### Asset Metadata

- Finnhub：`/search` 支持按 symbol / security name 查询；免费版 `/stock/profile2` 可按 symbol
  获取 ticker、name 与 listed exchange 等最小元数据。
- Massive（原 Polygon.io）：提供 ticker / company name search 与单 ticker overview，但免费
  Stocks Basic 为 5 API calls/min，无法舒适覆盖交互式搜索与多持仓 exact validation。

### Vision / OCR

- Alibaba Model Studio `qwen3-vl-flash`：支持图片输入、Structured Output，能复用当前 Model
  Studio 接入与 Credential，成本低。官方声明数据不用于训练，但没有公开固定原图保留时长。
- OpenAI `gpt-4o-mini`：支持图片与 Structured Outputs，Retention 文档更明确，但会增加第二个
  LLM Provider 与 Credential。

## 决策

- Asset Metadata Provider 使用 Finnhub。
- 通过 Finnhub `/search?q=...&exchange=US` 取得 bounded Selector Candidate，再对返回候选调用
  免费版 `/stock/profile2?symbol=...` 补齐真实 listed exchange；exact validation 同样先做精确
  symbol 匹配，再由 Profile 2 确认最小元数据。Provider-specific Payload 只存在于 Adapter。
- Provider-neutral Asset Identity 只包含 `canonical_symbol`、`display_name` 与 `exchange`；
  删除 `ACTIVE / INACTIVE` status，不把 Provider 是否返回记录解释为 Domain 的存续状态。
- Validation Result 的 `OK`、`NO_MATCH`、`PROVIDER_UNAVAILABLE`、`RATE_LIMITED` 等请求结果
  状态仍保留，用于区分验证成功、未匹配和 Provider Failure。
- Vision / OCR 使用 Alibaba Model Studio `qwen3-vl-flash`，通过独立 Recognition Boundary 接入，
  不复用 `InvestmentAgent` 或其 Prompt / Tool 流程。
- 使用当前 `qwen3-vl-flash` alias，并通过严格 Application Schema 验证 Structured Output；具体
  快照能力变化由 opt-in Online Smoke 检测。
- PositionPilot 不持久化原图、OCR 全文、Draft、Confidence 或 Provider Payload，也不记录图片
  内容。图片以当前 Request 内 Base64 输入发送，不使用 Provider File / Asset 持久化能力。
- UI 明确披露图片会发送至 Alibaba Cloud Model Studio；官方声明不用于训练，但 PositionPilot
  不宣称 Provider Zero Retention 或固定保留时长。
- Recognition Confidence 只作为 Human Review Signal。缺失 average cost 等字段必须返回
  `MISSING`，不得由价格、市值或盈亏反推。

## 理由

- Finnhub 的 `/search` 与免费 `/stock/profile2` 覆盖 M9 Selector 和 exact validation 所需的
  最小调用；即使 Search Candidate 需要 bounded Profile enrichment，仍比 Massive 的 5 calls/min
  免费额度更适合交互式搜索与多持仓导入，实际额度由 Online Smoke 验证。
- 删除 Asset Identity status 使 Boundary 只表达当前 UI 和写入校验真正需要的元数据；`OK` 等
  Validation Result 仍能明确表达请求结果，不制造“当前可交易 / 未退市”的错误事实。
- Qwen3-VL 可复用现有 Model Studio 运维条件，减少个人项目的 Provider 和 Credential 数量。
- 独立 Boundary 与临时 Draft 保持 Portfolio Structured State、Recognition Suggestion 和外部
  Provider Payload 的职责清晰。
- 明确披露未知 Provider Retention，比在证据不足时承诺 Zero Retention 更准确。

## Trade-off

- Finnhub 的 Symbol Lookup 不返回真实 listed exchange，Adapter 必须对 bounded Candidate 调用
  Company Profile 2 enrichment，并为 exact validation 做精确 symbol 匹配、US 过滤、最小字段
  映射和空结果 / 429 / Provider Failure 映射。具体可用额度以 Finnhub 账户方案为准，不能把额度
  假设写入 Domain。
- 不再提供 `ACTIVE / INACTIVE` 语义，意味着 M9 exact validation 只证明 Provider 能规范化并
  返回所需身份元数据，不证明交易可用性或当前存续状态。若未来 UI 需要 tradable / lifecycle
  语义，必须重新定义字段和 Review 边界。
- Finnhub 的免费计划、覆盖和延迟可能变化；Online Smoke 仍必须验证固定美股 / ETF Fixture，
  并将 rate limit 明确暴露为失败，而不是降级为未匹配。
- `qwen3-vl-flash` alias 可能随 Provider 更新；Online Smoke 必须证明当前图片输入和 Structured
  Output Contract 可用。
- Model Studio 未公开固定原图保留时长，因此不适合需要严格 Zero Retention 的敏感截图场景。
- Screenshot 可能没有 average cost；这会增加人工补全，但不会降低 Portfolio Truth 边界。

## 重新考虑条件

- Finnhub 的 `/search`、`/stock/profile2`、美股 / ETF 覆盖、稳定性、延迟或成本无法满足实际
  M9 使用；或其配额不足以支撑真实交互式搜索 / 多持仓 exact validation。
- 产品明确需要交易可用性、退市生命周期或 `ACTIVE / INACTIVE` 作为用户可见事实。
- Qwen3-VL 无法在固定脱敏 Fixture 上稳定返回所需 Structured Draft。
- 产品需要可证明的 Zero Data Retention，或图片包含当前个人项目无法接受的敏感信息。
- 新 Provider 在相同最小 Fixture 上明显降低 Failure、成本或集成复杂度。

## 参考

- [Finnhub Symbol Lookup](https://finnhub.io/docs/api/symbol-search)
- [Finnhub Company Profile 2（免费版本）](https://finnhub.io/docs/api/company-profile2)
- [Finnhub API Authentication 与 Rate Limits](https://finnhub.io/docs/api/quote)
- [Massive Stocks Pricing（Stocks Basic：5 API Calls / Minute）](https://massive.com/pricing?product=stocks)
- [Qwen3-VL Flash](https://help.aliyun.com/zh/model-studio/qwen3-vl-flash)
- [Model Studio Privacy](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/privacy-notice)
