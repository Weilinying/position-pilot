# M9 Provider / Vision Short Spike

**Date:** 2026-09-01
**Status:** Human Approved — Massive + Alibaba Model Studio `qwen3-vl-flash`

## 1. Scope

本 Spike 只回答 M9 开始实现所需的八个最小问题，不研究通用证券主数据、完整 Provider
能力矩阵或未来截图格式。

## 2. Asset Metadata Provider

### 推荐：Massive（原 Polygon.io）

| 最小问题 | 结论 |
|---|---|
| 能否按 symbol / company name 搜索 | 可以。`GET /v3/reference/tickers` 的 `search` 参数搜索 ticker 与 company name。 |
| 能否 exact validate | 可以。`GET /v3/reference/tickers/{ticker}` 返回单一 ticker 的当前详情；Adapter 只映射 canonical symbol、display name、exchange 与 status。 |
| 美股 + ETF 是否够用 | 可以。Stocks Basic 提供美国股票 Reference Data，官方 Stocks 计划覆盖美国市场；M9 使用少量股票与 ETF Fixture 做 Online Smoke。 |
| 稳定性与成本是否可接受 | 可以。Reference Endpoint 每日更新；Basic 免费，适合低频 Asset Selector。免费额度为 5 calls/min，达到限额时明确返回 Provider Failure。 |

官方依据：

- [All Tickers：支持 ticker / company name search](https://massive.com/docs/rest/stocks/tickers/all-tickers)
- [Ticker Overview：单 ticker 详情查询](https://massive.com/docs/rest/stocks/tickers/ticker-overview)
- [Stocks plans 与价格](https://massive.com/stocks)

Alpha Vantage 支持 Symbol Search，但没有同等直接的 exact ticker details Endpoint，免费额度也更
紧，因此只作为未来替换候选，不进入 M9 实现。

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
Credential。Human Review 选择优先复用当前 Model Studio，并接受 Provider 原图保留时长未公开
这一限制，因此不进入 M9 实现。参考：

- [`gpt-4o-mini` 图片与 Structured Outputs](https://developers.openai.com/api/docs/models/gpt-4o-mini)
- [OpenAI API Data Controls](https://developers.openai.com/api/docs/guides/your-data)

## 4. Proposed Privacy Boundary

- Browser 只把用户主动选择的单张图片发送给 PositionPilot Backend。
- Backend 使用 Base64 直接调用 Model Studio OpenAI-compatible Chat Completions，不使用 File、
  Data Connection、Asset Center 或
  Provider-side persistent object。
- PositionPilot 不持久化原图、OCR 全文、Recognition Draft、Confidence 或 Provider Payload，
  也不把它们写入普通日志。
- 图片与识别文本只进入 Recognition Adapter，并作为 Structured Draft 数据返回；不进入
  `InvestmentAgent`、System Prompt、User Prompt、Tool 或 Conversation Memory。
- UI 在上传前明确提示：PositionPilot 本地不保存图片；图片会发送至 Alibaba Cloud Model Studio
  处理，官方声明不用于训练，但没有公开固定的 Provider 保留时长。
- Online Smoke 只使用脱敏或合成截图，默认 Test Suite 不访问外部 Provider。

## 5. Human Decision

2026-09-01 Human Review 批准以下组合，M9 进入实现：

1. Asset Metadata：Massive；
2. Vision：Alibaba Model Studio `qwen3-vl-flash`；
3. 图片隐私：采用第 4 节边界，明确 PositionPilot 不持久化图片，同时不宣称 Provider Zero
   Retention 或固定保留时长。

IBKR 参考截图只用于理解版式，不复制进 Repository：可见 ticker 与持仓数量，但没有 average
cost；Recognition 必须将该字段标为 `MISSING`。“AI Instructions”是截图 UI 文本，不是系统或
用户指令。
