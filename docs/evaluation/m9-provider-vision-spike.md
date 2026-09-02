# M9 Provider / Vision Short Spike

**Date:** 2026-09-02
**Status:** Human Approved — Finnhub + Alibaba Model Studio `qwen3-vl-flash`

## 1. Scope

本 Spike 只回答 M9 开始实现所需的八个最小问题，不研究通用证券主数据、完整 Provider
能力矩阵或未来截图格式。

## 2. Asset Metadata Provider

### 推荐：Finnhub

| 最小问题 | 结论 |
|---|---|
| 能否按 symbol / company name 搜索 | 可以。`GET /search?q=...&exchange=US` 支持按 symbol 或 security name 查询，并返回 `symbol`、`displaySymbol`、`description` 等候选字段；Adapter 对 bounded Candidate 调用 Profile 2 补齐真实 listed exchange。 |
| 能否 exact validate | 可以。Adapter 对 `/search` 结果执行精确 symbol 匹配，并使用免费版 `GET /stock/profile2?symbol=...` 获取或确认 `ticker`、`name`、`exchange`；空结果或无精确匹配返回 `NO_MATCH`。 |
| 美股 + ETF 是否够用 | 以 M9 固定 Fixture 验证为准；Provider 选择要求覆盖 `AAPL`、`GOOG`、`SPY`、`QQQ`、`VOO`、`IBIT`，并正确拒绝无效 symbol。 |
| 稳定性与成本是否可接受 | 相比原选型 Massive 免费版 5 calls/min，Finnhub 的两个最小 Endpoint 更适合交互式搜索与多持仓 exact validation。具体配额以账户方案为准；429 必须映射为 `RATE_LIMITED`，不能伪装成 `NO_MATCH`。 |

Provider-neutral Asset Identity 只保留 `canonical_symbol`、`display_name`、`exchange`。本次
Review 删除 `ACTIVE / INACTIVE`，因为 M9 当前只需要规范化和验证身份元数据，不需要把 Provider
返回或未返回记录解释为退市 / 存续事实。`AssetValidationResult` 的 `OK`、`NO_MATCH`、
`PROVIDER_UNAVAILABLE`、`RATE_LIMITED` 等结果状态仍保留，用于区分验证结果与请求失败。

官方依据：

- [Finnhub Symbol Lookup](https://finnhub.io/docs/api/symbol-search)
- [Finnhub Company Profile 2（免费版本）](https://finnhub.io/docs/api/company-profile2)
- [Finnhub API Authentication 与 Rate Limits](https://finnhub.io/docs/api/quote)
- [Massive Stocks Pricing（Stocks Basic：5 API Calls / Minute）](https://massive.com/pricing?product=stocks)

### 替代前决策与本次 Human Review

2026-09-01 Human Review 曾选择 Massive，理由是其搜索与单 ticker overview 能覆盖低频 Selector。
2026-09-02 重新按真实请求路径评估后改选 Finnhub：交互式 Selector 可能连续查询，多持仓 Import
还需要在短时间内逐个 exact validation，Massive 免费 5 calls/min 过于紧张。Finnhub 的
`/search` 与免费 `/stock/profile2` 足以满足当前最小 Boundary；不为已退市股票的低频场景增加
`ACTIVE / INACTIVE` Domain 字段。

## 3. Vision / OCR Capability

### 选择：Alibaba Model Studio `qwen3-vl-flash`

| 最小问题 | 结论 |
|---|---|
| 能否识别 ticker / shares / average cost | 模型支持图片输入与视觉理解；具体券商截图准确性仍由脱敏固定 Fixture 的 opt-in Online Smoke 验证。缺失 average cost 必须返回 `MISSING`，不能推算。 |
| 能否稳定返回 Structured Output | 当前 `qwen3-vl-flash` alias 官方支持 Structured Output；Adapter 仍执行严格 Schema Validation，不依赖模型自述正确性。 |
| 图片是否不会被默认长期保存 | PositionPilot 可以保证自身不保存；Provider 官方明确不把数据用于训练，但没有公开固定原图保留时长，因此不能宣称 Provider Zero Retention。Human 已明确接受该边界。 |
| 成本是否可接受 | 可以。北京地域输入不超过 32K 时为输入 `¥0.15 / 1M tokens`、输出 `¥1.5 / 1M tokens`，适合个人低频 Opening Import。 |

官方依据：

- [Qwen3-VL Flash 能力与价格](https://help.aliyun.com/zh/model-studio/qwen3-vl-flash)
- [Model Studio Structured Output](https://help.aliyun.com/en/model-studio/qwen-structured-output)
- [Model Studio Privacy](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/privacy-notice)

OpenAI `gpt-4o-mini` 的 Chat Completions Retention 说明更明确，但会新增独立 Provider 与
Credential。Human Review 继续选择优先复用当前 Model Studio，并接受 Provider 原图保留时长未公开
这一限制，因此不进入 M9 实现。参考：

- [`gpt-4o-mini` 图片与 Structured Outputs](https://developers.openai.com/api/docs/models/gpt-4o-mini)
- [OpenAI API Data Controls](https://developers.openai.com/api/docs/guides/your-data)

## 4. Proposed Privacy Boundary

- Browser 只把用户主动选择的单张图片发送给 PositionPilot Backend。
- Backend 使用 Base64 直接调用 Model Studio OpenAI-compatible Chat Completions，不使用 File、
  Data Connection、Asset Center 或 Provider-side persistent object。
- PositionPilot 不持久化原图、OCR 全文、Recognition Draft、Confidence 或 Provider Payload，
  也不把它们写入普通日志。
- 图片与识别文本只进入 Recognition Adapter，并作为 Structured Draft 数据返回；不进入
  `InvestmentAgent`、System Prompt、User Prompt、Tool 或 Conversation Memory。
- UI 在上传前明确提示：PositionPilot 本地不保存图片；图片会发送至 Alibaba Cloud Model Studio
  处理，官方声明不用于训练，但没有公开固定的 Provider 保留时长。
- Online Smoke 只使用脱敏或合成截图，默认 Test Suite 不访问外部 Provider。

## 5. Human Decision

2026-09-02 Human Review 批准以下组合，M9 进入实现：

1. Asset Metadata：Finnhub，使用 `/search` 与免费 `/stock/profile2`；
2. Asset Identity：只包含 `canonical_symbol`、`display_name`、`exchange`，删除 `ACTIVE / INACTIVE`；
3. Validation Result：保留 `OK`、`NO_MATCH`、`PROVIDER_UNAVAILABLE`、`RATE_LIMITED` 等明确请求结果；
4. Vision：Alibaba Model Studio `qwen3-vl-flash`；
5. 图片隐私：采用第 4 节边界，明确 PositionPilot 不持久化图片，同时不宣称 Provider Zero
   Retention 或固定保留时长。

实现前后的短 Online Smoke 应覆盖以下 Asset Fixture：`AAPL`、`GOOG`、`SPY`、`QQQ`、`VOO`、
`IBIT` 和一个无效 symbol。Smoke 是 opt-in 检查，不进入默认 Regression Suite；Provider Failure
或 rate limit 必须可观察并保持明确状态。

IBKR 参考截图只用于理解版式，不复制进 Repository：可见 ticker 与持仓数量，但没有 average
cost；Recognition 必须将该字段标为 `MISSING`。“AI Instructions”是截图 UI 文本，不是系统或
用户指令。
