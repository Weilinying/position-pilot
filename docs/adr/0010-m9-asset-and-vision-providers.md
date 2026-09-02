# ADR 0010：M9 使用 Massive Asset Metadata 与 Qwen3-VL Recognition

## 状态

已接受（2026-09-01）

## 背景

M9 需要为一次性 Portfolio Opening State Import 提供两项外部能力：按 symbol / company name
搜索并精确验证 canonical symbol，以及把 Text / Screenshot 转换成可人工审查的 Structured
Draft。两项能力都必须隔离在 Provider-neutral Boundary 后，且 Recognition 不能直接写入
Portfolio。

Human Review 已要求 Phase 0 只做短 Spike。选型只验证搜索、exact validation、美股与 ETF
覆盖、ticker / shares / average cost 识别、Structured Output、图片保存边界和成本，不建设
通用 Provider 研究项目。

## 候选方案

### Asset Metadata

- Massive（原 Polygon.io）：提供 ticker / company name search 与单 ticker overview，免费方案
  足够低频 Asset Selector 使用。
- Alpha Vantage：支持 Symbol Search，但没有同等直接的单 ticker exact details Endpoint，免费
  限额也更紧。

### Vision / OCR

- Alibaba Model Studio `qwen3-vl-flash`：支持图片输入、Structured Output，能复用当前 Model
  Studio 接入与 Credential，成本低。官方声明数据不用于训练，但没有公开固定原图保留时长。
- OpenAI `gpt-4o-mini`：支持图片与 Structured Outputs，Retention 文档更明确，但会增加第二个
  LLM Provider 与 Credential。

## 决策

- Asset Metadata Provider 使用 Massive。
- Provider-neutral Asset Identity 只包含 `canonical_symbol`、`display_name`、`exchange` 与
  `status`；不建设 Asset Master 或通用证券主数据模型。
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

- Massive 直接满足 M9 Selector 的 search 与 exact validate，避免下载或维护完整 Asset Master。
- Qwen3-VL 可复用现有 Model Studio 运维条件，减少个人项目的 Provider 和 Credential 数量。
- 独立 Boundary 与临时 Draft 保持 Portfolio Structured State、Recognition Suggestion 和外部
  Provider Payload 的职责清晰。
- 明确披露未知 Provider Retention，比在证据不足时承诺 Zero Retention 更准确。

## Trade-off

- Massive 免费额度较低，搜索需要前端 debounce、后端 bounded query 与明确 Rate Limit Failure。
- `qwen3-vl-flash` alias 可能随 Provider 更新；Online Smoke 必须证明当前图片输入和 Structured
  Output Contract 可用。
- Model Studio 未公开固定原图保留时长，因此不适合需要严格 Zero Retention 的敏感截图场景。
- Screenshot 可能没有 average cost；这会增加人工补全，但不会降低 Portfolio Truth 边界。

## 重新考虑条件

- Massive 的搜索、exact lookup、覆盖、稳定性或成本无法满足实际 M9 使用。
- Qwen3-VL 无法在固定脱敏 Fixture 上稳定返回所需 Structured Draft。
- 产品需要可证明的 Zero Data Retention，或图片包含当前个人项目无法接受的敏感信息。
- 新 Provider 在相同最小 Fixture 上明显降低 Failure、成本或集成复杂度。

## 参考

- [Massive All Tickers](https://massive.com/docs/rest/stocks/tickers/all-tickers)
- [Massive Ticker Overview](https://massive.com/docs/rest/stocks/tickers/ticker-overview)
- [Qwen3-VL Flash](https://help.aliyun.com/zh/model-studio/qwen3-vl-flash)
- [Model Studio Privacy](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/privacy-notice)
