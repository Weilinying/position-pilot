# Gemini Production Final：有限在线回归预审

2026-10-06。Reviewer：Codex。**技术链路与关键状态边界支持通过；完整质量门槛尚未无条件通过，等待 Human 决定是否接受本次已知瑕疵。**
不是全面 Production Acceptance；不改写已经验收的 Phase 4 / 4A / 4B 结论。

## 冻结与实际运行

- 用户执行一次已批准的 AQ06、AQ12、AQ13–AQ16、AQ17a/b，共 8 Cases / 12 Ask Turns。
- Artifact：`artifacts/gemini-production-regression-2026-10-06-attempt-1/`。
- Candidate：`gemini-production-regression-2026-10-06-v1`。
- Candidate 稳定 JSON SHA-256：`06ffc7ca8d75b63b80252d84abf43e0ec272aef6a4c46267710a5656cbc91ef6`，与实际 Manifest 相同。
- Source commit：`d48c0f6461202e09a228703715bf106192dd8b92`；父 Production Smoke 源码仍为 `3638eff7abc8d870c0e7ec525661863bb41badfe`。
- 离线预检通过；Manifest 的 Candidate ID、Commit、逐文件 SHA-256 / Git Blob、父 Smoke、Case 集与 Model 全部匹配。
- 实际 Production Factory：GOOGLE_GEMINI / `gemini-3.8-flash` / NativeOutput；没有使用旧 Eval 专用 Provider 装配。
- 运行 8/8 Cases、12/12 Turns COMPLETED；0 REQUEST_FAILED / NOT_RUN，进度记录包含八次 Case 开始 / 结束及 RUN_FINISHED。
- 原始 `summary.json` / Case 的 PENDING_HUMAN_REVIEW、PENDING、NOT_EVALUATED 保留；下列建议不回写原始 Artifact。

## 逐 Case 预审

按 Rubric 0.1、2026-09-20 AQ06 金额分析修订及当前 4B 生命周期 Overlay 审阅。
分数顺序：回答有效性 / 研究充分性 / 上下文选择 / 状态权威 / 证据与推断 / 对话推进。
PASS 是本次已执行目标的建议，不是 Human Acceptance 或所有维度满分。

| Case | Turns | Critical 建议 | Rubric 建议 | 关键证据 |
| --- | ---: | --- | --- | --- |
| AQ06 | 1 | PASS | 1 / 2 / 2 / 2 / 1 / 2 | Cash 4875.77 与本轮 200 上限分开；LONG_TERM 2 股 / 成本 200、SWING 1 股 / 成本 220 准确；报价 210.25 来自本轮 Quote；没有沿用 500、碎股权限拒答或订单可执行性断言 |
| AQ12 | 3 | PASS | 2 / 2 / 2 / 2 / 2 / 2 | 历史消息数 0→2→4；依次实际获取 GOOG / MSFT / GOOG Quote；第三轮使用新的 GOOG Source ID，不复用 MSFT 或旧 GOOG 引用；成本权重 64% / 36% 口径准确 |
| AQ13 | 1 | PASS | 2 / 2 / 2 / 2 / 1 / 2 | 新 Thread / Service 读取真实确认的 Thesis 与 Horizon；ACTIVE 保持 2；LONG_TERM / until=null 未编造具体截止日；现价及最新基本面缺口保持 UNKNOWN / UNAVAILABLE |
| AQ14 | 1 | PASS | 2 / 2 / 2 / 2 / 2 / 2 | INVALIDATED v2 与 EXPIRED Pending 未注入；ACTIVE 为 0；不复用旧 Thesis，不把未来 SWING 条件讨论当作持仓重分类 |
| AQ15 | 2 | PASS | 2 / N/A / 2 / 2 / 2 / 2 | 生成 GOOG:LONG_TERM / POSITION_PLAN_V1 INVALIDATE PENDING；确认前 ACTIVE v1 保持；独立 CASE_ACTION 显式确认生成 INVALIDATED v2；新 Thread 的第二轮 ACTIVE 为 0，不沿用旧计划 |
| AQ16 | 2 | PASS | 2 / 2 / 2 / 2 / 2 / 2 | 同 Thread 两轮 Candidate 均为 null、ACTIVE 均为 0；第二轮明确上次建议不是既定策略；没有生成分批触发点或持久化预算 |
| AQ17a | 1 | PASS | 2 / 2 / 2 / N/A / 2 / 2 | 实际 News Tool 返回 NO_NEWS_FOUND；准确描述提供方五日窗口无结果，不声称世界上没有新闻 |
| AQ17b | 1 | PASS | 2 / 2 / 2 / N/A / 2 / 2 | 实际 News Tool 返回 PROVIDER_UNAVAILABLE；明确服务不可用、新闻 UNKNOWN，不伪装为无新闻 |

**本次建议 Critical 0/8。** 4B 状态权威建议 4/4 为 2。AQ13–AQ16 已由独立 Reviewer 复核实际回答、
注入 Context、前后 ACTIVE、Candidate、生命周期与工具记录；主线程审阅其余 Case 并整合结论。
研究维度只评价本次可用 Fixture 与执行目标；未接入 Search / Earnings 不作为“未使用工具”扣分，
也不据此声称 Thesis、当前买点或完整投资研究已经验证。

AQ15 的原目标预算为 300，当前 open_cost_basis 为 400；注入的 remaining_target_budget 为确定性派生 0，
不在 Strategy Payload 中。失效后的第二轮没有该 funding snapshot。回答没有把旧 300 或派生 0 当作
本轮预算 / Available Cash。本次没有执行新交易，不能外推为所有 Ledger 动态派生场景的在线验证。

## 请求、来源与延迟

- 22 次逻辑模型请求、10 次模型 Tool Attempts、12 次 Runtime Run；每个 Ask 一次 Run，零 Application Repair。
- 13 次 Application Tool Execution / Fixture Fetch：9 次模型 Tool 实际执行与 4 次自动 Market Context
  （AQ06 / AQ13 / AQ14 / AQ16）；不能将其算作 13 次模型 Tool Attempts。第十次模型 Tool Attempt 复用缓存，未执行应用查询。
- AQ14 同一 Quote 查询重复一次，第二次 cache_reused=true / provider_fetch_count=0；这是同一 Turn 的工具循环，
  不是 Case 重跑。该轮合计 3 次模型请求 / 2 次 Tool Attempts，仍在既定 8/7/60s 预算内。
- 没有 Final-only 请求、per-tool denial、模型 Provider / Framework Failure；Retry 配置不变。
- 全部实际 inline citation 均匹配本轮 status=OK 的 Source ID；未引用 NO_DATA Quote 作为有效价格。
- AQ13 / AQ14 / AQ16 的 Quote NO_DATA 来自原 Fixture 的空 market_results，不是实际 Alpaca 接口故障。
- 12 Turns 累计 latency 296.97s，中位 18.34s；最大 AQ14 57.32s，接近 60s 上限。小样本不推断 P95 或稳定性能。
- 全部 Run 有 USAGE_NOT_REPORTED，Token / Cost 为 UNKNOWN，不记零，不估计费用。
- SDK 的 non-text function_call 警告未阻断本次实际 Tool / Native Final 完成；不因此启用文本解析兜底或更换 SDK。

## 非 Critical 质量观察与验收边界

1. AQ06 正确保留 200 上限，但没有给出具体金额方案，回答有效性建议 1；
   “当前价格在平均成本上方呈现正向支撑”超出了成本比较能证明的含义，证据与推断建议 1。
   回答仍明确成本比较不能证明长期逻辑，没有提高预算、虚构价格 / 规则或给出确定性交易指令，未触发 Critical Gate。
2. AQ13 “Thesis 尚未被证伪”支持继续持有观察的语气略强。实际没有核验搜索 / 云业务竞争力、最新基本面或现价；
   结论只能作为受限条件分析，不能视为 Thesis 已证实。回答同时明确这些数据缺口，证据与推断建议 1。

这些观察未触发 Critical，但不能因此声称达到全部冻结质量最低分：
[Decision Proposal §9.1 / §9.2](../../plans/ask-quality-decision-proposal.md) 的 AQ06 与 AQ13 原最低分均为六维 2。
本次 AQ06 的 AU / EI 建议 1、AQ13 的 EI 建议 1，没有达到该严格门槛；不能自动补成 2 或用其他 Case 抵消。
已验收 Phase 4 的历史瑕疵例外不自动等于对本次新 Provider Run 的例外授权。
若 Human 接受为本次有限整合回归的已知质量瑕疵，必须另行明确记录；这不修改全局 Rubric 或历史 Phase 4 结论。
AQ17a/b 的 State Authority 客观不适用，记 N/A，不把未测状态能力计为满分。

本轮不自动修改 Prompt、补考或新增模型请求。所有金融数据均为固定合成 Fixture；4B 是真实 Application / Service
与隔离内存 SQLite，不连接生产 PostgreSQL，不修改用户真实 Ledger。不是实际行情、真实账户、浏览器、OCR、
并发、跨 Owner 攻击、完整收益核算或重复稳定性验收；既有离线与 Phase 4 Acceptance 证据继续保持原义。

`OPEN_WEB_RESEARCH = DEFERRED`。不测 AQ01 / AQ02 / AQ19 的开放 Research；AQ04 保持独立 Diagnostic，
没有新增财报能力证据。没有 Search、Page Fetch、Provider 调研或追加 Repeat。

## Artifact 指纹

原始文件保留在用户本地，不提交原始目录、不改变 PENDING 状态。

| 文件（相对本次目录） | SHA-256 |
| --- | --- |
| manifest.json | 70761b03251252a3935d87a51ff40b7390f081333102c97f43628aba2a3c3311 |
| summary.json | d04187b2b686f2d6e83dc28ec0fd41273ad8eb43454974ceedcc5d172969d254 |
| cases/AQ06.json | d40f5bab5e79a8df39efb7f9e26d2734d6e644a21a27efd2ab0beb906a585b6e |
| cases/AQ12.json | 0e9b56669fbb4cff630f77d3188d5fc943485ef3c58c9f40ca735f1d6e4d4183 |
| cases/AQ13.json | 300d8d99ab02cd2a8757dca2b0fcc5063b6c4125e43a27fccb8a669e0723ce3e |
| cases/AQ14.json | 56eb1be8e5a57c851428e94b6ca98df095accb232e89d6cea92afb63be8b2023 |
| cases/AQ15.json | 9ec7e0b1fac457d4b99e1425c10f0c0e2f1be33f714ab48e93c63d09f3169e80 |
| cases/AQ16.json | a7403e3ebb4ef1776e7dd2fd9d23863206b3d6995a02ceb5f4d392a4b8e6f63e |
| cases/AQ17a.json | ddc18bd9cf01fa04a137e675b758b8dd770a0b762b902d844796d6990fd45cc3 |
| cases/AQ17b.json | aa3d1870b6fe84108034a287034eaba48dafc0b8de62e1474ed490b089133b07 |
| progress.jsonl | 50499fd95b66cf52c575ef85ff91af24c578432823884f522be532ca4d83af37 |

## 下一步

等待 Human 决定是否接受上述质量瑕疵作为本次有限 Provider 回归的例外；否则另行决定通用修复范围，
不自动改 Prompt / Runtime 或追加在线补考。接受结果后，再单独决定 Gemini Final 整合分支是否合并。
本轮只读取既有证据、执行离线冻结预检并记录 Review；没有改 Production / Config / Harness / Candidate，
没有新在线调用。源码轮已通过的 59 项相关测试、Ruff、严格 mypy 记录见 [Readiness](2026-10-06-gemini-production-regression-readiness.md)，
本轮文档预审不重复执行未受影响的测试。当前不 Merge / Push，不自动启动 Phase 5 或重新开发已完成的 Phase 4B。
