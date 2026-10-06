# ADR 0018：Gemini Production Final 与 Aliyun OCR 分离

2026-10-05。状态：Accepted；本轮只整合已批准的 Final 接线，在线验证待单独执行。

2026-10-06 后续：Production Smoke 已取得技术 PASS；Human 已接受
[有限 Production Provider 回归](../evaluation/reports/2026-10-06-gemini-production-regression-review.md)，
允许本地整合分支合并；AQ06 / AQ13 原评分偏差保留，不视为全面 Production Quality Acceptance。
原架构决策、Phase 4 已验收边界及 Research DEFERRED 均不变。

## 背景

Human 已批准分析 / Final 使用 Gemini、图片识别继续 Aliyun。原实现与证据保存在 Stash
`911862ad`，但它来自旧工作树，并混有 Research 与旧 Runtime 代码。当前权威基线为已完成
Phase 4A / 4B 的 `main`（`0d36e78`）。旧 R2 单次链路 PASS 不等于当前整合 Candidate 的在线验收。

## 决策

- 仅移植官方 `GoogleProvider` / `GoogleModel` 工厂与同一 Event Loop 内的客户端生命周期；
  使用既有 `PydanticAIRuntime` 的 `NativeOutput`，包括当前 4B 的 optional Strategy Draft Schema。
- 默认 `LLM_PROVIDER=GOOGLE_GEMINI`、`LLM_MODEL=gemini-3.8-flash`；Google 分支只读
  `GEMINI_API_KEY`，不使用 `LLM_API_KEY` / `LLM_BASE_URL`，缺 Key 明确失败，不自动回退。
- Aliyun OCR 继续 `qwen3-vl-flash`，显式 `VISION_API_KEY` 优先。只有显式 Aliyun Final 下才允许
  原有 `LLM_API_KEY` fallback；Gemini / 其他 Provider 不允许跨端点复用凭据。
- 生产 dependency 仅提升固定 `pydantic-ai-slim[google,openai]==1.107.6` 的 google extra；
  复用当前锁文件中的 Google SDK，不引入 Bedrock 或其他 Provider。
- 不替换当前 Runtime / Prompt、Tool Admission / Final-only、7 / 8 配额、60s 截止、Strategy /
  Conversation / Ledger；无 Migration，无公共 API / Answer Source Contract 扩展。
- `OPEN_WEB_RESEARCH = DEFERRED`。不移植 Research Gateway 装配、Google Search、
  `WEB_RESEARCH` 来源、Research UI / quota / attribution、Page Fetch 或 Brave。
  当前 Production 根本没有 Search 启用开关；仅有独立 Gemini Key 不会暴露研究工具。

## 取舍

不 apply / pop 整份 Stash，也不复制旧 Runtime 文件。独立工厂可复用已有输出与 Strategy 接缝，
避免回退已验收行为。只设置 Gemini 环境变量而继续使用 OpenAI-compatible 工厂不能替代官方接线。
Research Spike 保留在封存引用，未删除、未标记产品 PASS。当前只交付离线验证和冻结 Candidate，
不把历史 Eval / R2 证据改写为当前版本的 Production Certification。

## 重新考虑条件

当前 4B Schema / Tool Loop 无法无损接入 Google 时停止报告 Gap；模型不可用、延迟或真实行为
缺口需保留新证据并独立 Review。不得自动换 Provider、增加 Retry / Repair / 预算或恢复 Research。
