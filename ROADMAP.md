# PositionPilot Product Roadmap

## 1. 文档目的

本文件定义 PositionPilot 的 Engineering Milestone、Release Mapping、范围和完成标准，用于回答“现在开发到哪一步、何时形成用户可感知的 Release、下一步要做到什么”。

具体类、接口、Task 拆分和并行关系不在本文件中维护。复杂 Milestone 开始前，由 Codex 根据当前 Repository 状态生成或更新 `docs/plans/<milestone>.md`。

开发遵循 Vertical Slice：只建设当前闭环真正需要的能力，不为未来需求提前扩展基础设施。新增能力应由当前 Milestone、Evaluation 或真实 Failure Mode 驱动。

## 2. Current Status

**Current Milestone:** M8 — Local Portfolio Management
**Status:** IN PROGRESS — Authentication Revision Approved, Implementation Pending
**Current Release State:** Portfolio / Ledger 自助 Slice 已实现；基础本地账户与真实 Agent 产品闭环尚未完成，未形成 `v1.0.0`
**Next Planned Milestone:** M9 — Portfolio Import（依赖 M8 完成，尚未开始）

Milestone 状态统一使用 `NOT STARTED`、`IN PROGRESS`、`DONE`，不维护百分比进度。

## 3. Milestone 与 Version / Release

Milestone 表示内部开发阶段；Version / Release 表示用户可感知的产品能力边界。完成一个 Milestone 不自动等于发布一个 Version。

| Release | Engineering Milestone | 用户可感知边界 |
|---|---|---|
| Demo Core（pre-`v1.0.0`） | M0～M7 | 核心 Ledger、Market / News Context、Single Agent、Evaluation 与需预置 User ID 的 Demo Interface |
| `v1.0.0` | M8 | 本地用户从产品主页注册 / 登录、初始化并持续维护 Portfolio，完成真实 Agent Self-Service MVP |
| `v1.1.0` | M9 | 通过 Text / Screenshot Draft 与人工确认降低 Portfolio 初始化成本 |
| `v1.2.0` | M10 | Broker-neutral Fee Policy 基础与语义明确的第一阶段 Accounting / P&L |
| `v1.3.0` | M11 | 按需路由的确定性 Technical Context |
| V2 | 后续另行规划 | Connected Product：完整 Account Platform、Broker Sync、多 Portfolio 与完整绩效历史 |

## 4. V1 Engineering Milestones

```text
M0 Project Foundation
→ M1 Portfolio & Transaction State
→ M2 Minimal Market Data
→ M3 Minimal Investment Agent
→ M4 Investment Context Expansion
→ M5 Context-Aware Decision Flow
→ M6 Evaluation & V1 Hardening
→ M7 Minimal Product Interface
→ M8 Local Portfolio Management (`v1.0.0`)
→ M9 Portfolio Import (`v1.1.0`)
→ M10 Accounting & P&L (`v1.2.0`)
→ M11 Technical Context (`v1.3.0`)
```

M0～M7 是构建 PositionPilot V1 Core 与 Demo Interface 的内部 Engineering Milestones，不直接等同于正式 `v1.0.0`。M8 完成 Local Self-Service 闭环后才形成 `v1.0.0`；M9～M11 在保持本地、单用户上下文与现有核心架构的前提下形成后续 V1.x Release。

## M0 — Project Foundation

**Goal**

建立可运行、可测试、可继续演进的最小 Python 工程骨架，不实现投资业务。

**Scope**

完成最小 Python / FastAPI 工程、Development PostgreSQL 连接、Migration 基础能力、pytest 和配置管理。只引入当前 M0 / M1 必需的工程依赖和质量工具，不提前建设未来架构。

**Done**

* Application 可以本地启动，`GET /health` 返回 200；
* Development PostgreSQL 可以连接；
* Migration 和 pytest 可运行；
* 已配置的 Formatter / Lint / Type Check 等质量检查可运行；
* `.env.example` 存在且不包含真实 Secret；
* 没有为未来需求提前搭建复杂架构。

## M1 — Portfolio & Transaction State

**Goal**

建立可靠的 Structured State，使系统在不依赖 LLM 的情况下维护用户真实投资状态。

**Scope**

实现 User、Cash、Transaction、Position、BUY / SELL 和 `LONG_TERM` / `SWING`。Shares、Average Cost、Available Cash 和 Position 必须由确定性业务逻辑产生，并能够从持久化状态可靠恢复。具体 Position Persistence Strategy 由当前需求和实现约束决定，不在 Roadmap 中提前锁定。

**Done**

* `LONG_TERM` / `SWING` 可独立维护，同一 Ticker 可以同时存在两类仓位；
* BUY / SELL 后 Shares、Position 与 Cash 正确；
* Average Cost 等核心计算结果正确且可重复验证；
* Transaction 可追溯；
* 核心金融计算有 Unit Tests；
* Database Schema 通过 Migration 管理；
* Human Acceptance 通过。

## M2 — Minimal Market Data

**Goal**

只提供 M3 第一个 Agent 闭环所需的真实市场数据，不建设完整 Market Intelligence Platform。

**Scope**

支持 Current Quote、基础 Historical OHLCV、Volume、Market Timestamp 和明确的 Provider Error State。Market Data Provider 在进入 M2 时根据当前需求评估并决定，必要时通过 Technical Spike 和 ADR 记录。

**Done**

* 可以按 Ticker 获取 Current Quote 和基础 Historical OHLCV；
* Tool 输出结构化，并保留必要的 Source / Timestamp；
* 正常空结果与 Provider Failure 可区分；
* Provider 与核心 Domain 解耦；
* Unit Test 不依赖真实外部 API。

## M3 — Minimal Investment Agent

**Goal**

完成第一个 Stateful Investment Vertical Slice，验证 Portfolio State 与 Position Intent 是否能够真实改善投资回答。

**Scope**

先支持最小流程：User Question → Portfolio Context + Current Market Data → LLM → Personalized Response。M3 使用 Single Agent 和 Native Function Calling 完成最小 Agent Tool Use，不引入 LangGraph。Portfolio Structured State 是核心用户上下文，Current Quote 是最小 Market Tool 能力；LLM Provider 与 Agent / Domain 保持解耦，具体 Provider / Model 属于实现配置。

当前金融事实必须来自 Structured State 或 Tool Result。Market Data 缺失、为 `UNKNOWN` 或 Provider Failure 时，LLM 不得自行补造当前市场事实。

M3 不引入 News、Fundamentals、VIX、Market Regime、Conversation Memory、Multi-Agent 或复杂 Technical Analysis。

M3 建立 Minimal Agent Behavioral Evaluation，不评价股价预测能力或最终投资收益。使用约 10～20 个小规模、固定、可重复的代表性场景，优先使用 Fake / Stub Portfolio 与 Market Data，验证 Portfolio 使用、必要且参数正确的 Current Quote Tool Call、避免无意义 Tool Call、不虚构 Position 或当前价格、Provider / LLM Failure Handling，以及当前金融事实能否追溯到 Structured State 或 Tool Result。确定性行为可以自动检查，自然语言分析质量可以保留 Human Review。

M3 不建设完整 Evaluation Framework、公开金融 Benchmark 集成、LLM-as-a-Judge、多模型 Benchmark、历史投资收益回测或金融预测准确率评价。

**Done**

* 用户可以使用自然语言提出基础投资问题；
* Agent 自动读取相关 Structured State 和必要 Market Data；
* 不重复询问已经持久化的信息；
* 对相同问题，不同 Portfolio、Available Cash 或 Position Type 能产生合理且可解释的分析差异；
* `LONG_TERM` / `SWING` 在相关场景下会真实影响 Response；
* 当前金融事实来自 Structured State 或 Tool Result，而不是模型训练知识；
* Market Data Missing / `UNKNOWN` 或 Provider Failure 时不虚构当前市场事实；
* Tool / LLM Failure 有明确且可验证的处理；
* Minimal Agent Behavioral Evaluation 包含约 10～20 个固定、可重复的代表性场景，覆盖 Portfolio Awareness、Tool Use、Groundedness 和核心 Failure Handling；
* 端到端 Vertical Slice 可运行。

## M4 — Investment Context Expansion

**Goal**

在 M3 核心闭环成立后，只增加能够解决真实问题并改善回答质量的 Investment Context。

**Scope**

M4 开始阶段先完成独立的 Cash Adjustment Vertical Slice，再进入外部 Investment Context 扩展。该 Slice 使用 `initial_cash + immutable Cash Events + immutable Transactions` 作为 Portfolio Source of Truth，支持 Portfolio 创建后的 `DEPOSIT` / `WITHDRAWAL`、确定性 Available Cash 重建和不足现金校验；不通过修改历史 `initial_cash` 或伪造 BUY / SELL 表示资金调整。

根据 Evaluation Case 或已观察到的 Failure Mode，逐步加入 Market Context、News、Fundamentals / Earnings 和必要 Asset Indicators。每增加一类 Context，都必须说明它解决什么问题，并验证其是否改善 V1 核心场景。

第一个外部 Context Slice 复用 M2 已批准的 Alpaca Historical Daily OHLCV，为 Agent 提供固定近期窗口的 Price History 区间事实；它不升级为 Technical Analysis、交易信号或预测。

第二个外部 Context Slice 使用有界、可归因的 Recent News，改善近期事件问题；新闻报道不自动升级为独立验证事实，也不证明价格变化的唯一因果。

M3 建立的 Evaluation Cases 随新增 Context 逐步扩展，用于验证新增 Context 是否解决已有 Failure Mode 并实际改善回答。M4 不以“覆盖所有可能的金融信息”或建设完整 Evaluation Platform 为目标；无法通过 Evaluation 或真实使用证明价值的 Context 不进入稳定能力。

**Done**

* Cash Adjustment Vertical Slice 已完成，Portfolio Snapshot 能从 Initial Cash、Cash Event Ledger 和 Transaction Ledger 稳定恢复 Position 与 Available Cash；
* V1 核心场景所需的主要外部 Context 已通过实际需求逐步覆盖；
* 每类稳定 Context 至少对应明确的 Evaluation Case 或真实 Failure Mode；
* Market / News / Fundamentals / Asset Data 边界清晰；
* 可确定指标由代码计算；
* 外部数据保留必要的 Source / Timestamp / Failure State；
* 没有明显价值的复杂 Context 不进入 V1。

## M5 — Context-Aware Decision Flow

**Goal**

让 Agent 根据 User Intent、Portfolio Context 和当前市场状态动态决定需要什么信息，而不是机械调用全部 Tool。

**Scope**

建立 Context-Aware Routing；必要时加入 Transaction Context 与 Asset Context。不同问题应选择不同的最小充分 Context，同时关注无意义 Tool Call、Latency 和 Token / API Cost。

Evaluation 持续验证 Context Selection、最小充分 Context、无意义 Tool Call，以及 Portfolio / Position Type 是否真实影响 Routing。Routing / Tool Selection 的问题应能通过 Logging 与 Evaluation 定位，不为此引入复杂 Agent Framework。

**Done**

* 相同问题在不同 Portfolio Context 下可产生合理不同的分析；
* Market Regime 在与当前问题相关时，可以合理影响 Context Selection 或最终分析；
* 不相关 Tool 不被机械调用；
* `LONG_TERM` / `SWING` 会真实影响 Context Selection 或分析逻辑；
* 覆盖 `PROJECT.md` 定义的主要 V1 场景；
* Context Selection 可以通过 Logging 和 Evaluation 定位；
* 不为了追求复杂 Routing 引入无法证明价值的 Agent 或 Framework。

## M6 — Evaluation & V1 Hardening

**Goal**

把“Agent 看起来能工作”推进到“核心 V1 行为能够被稳定、重复地验证”。

**Scope**

M6 不从零开始 Evaluation，而是在 M3～M5 已积累的 Behavioral Eval Cases 基础上，将其扩展、整理为可重复运行的 V1 Evaluation Dataset。Dataset 覆盖 Entry / Add Position、Market Drop Explanation、Post-Earnings Holding、Position Reduction、不同 Available Cash、`LONG_TERM` / `SWING`、不同 Market Context / Market Regime、Provider Failure、Missing / `UNKNOWN` Data、Context Selection、Tool Use、当前金融事实来源和核心 Failure Handling，并补齐必要的 Error Handling、Logging、Tests 和明显技术债。

根据 V1 Model Selection 或质量验证的实际需要，可以评估 Model / Provider 横向比较、Latency / Token / API Cost、Recommendation Consistency，以及更系统的人工 Rubric 或自动评分。公开金融 Benchmark、历史投资 Backtesting 和完整 LLM-as-a-Judge 系统不作为 V1 强制 Done Criteria，不为了建设 Benchmark Platform 而建设。

**Done**

* 核心 Evaluation Dataset 可重复运行；
* 主要 V1 场景通过预期验证；
* 相同问题在不同 Portfolio / Position Intent / Market Context 下能够产生合理、可解释的差异；
* Critical / High Reviewer Findings 已解决；
* 核心 Domain 和 Tool 行为有足够测试；
* 已知限制被明确记录；
* `PROJECT.md` 的 V1 Success Criteria 满足；
* Human Acceptance 通过，可以合并到 `main`。

## M7 — Minimal Product Interface

**Goal**

为 PositionPilot V1 提供一个可直接使用和演示的最小前端界面，使核心 Portfolio State、Agent Answer、Context Selection、Source Grounding 和 Failure State 能够被清晰展示。

**Scope**

实现轻量 Web Interface，支持输入投资问题、查看 Portfolio Snapshot、展示 Agent Answer，并呈现本次回答实际使用的 Quote、Price History、News、Market Context 等来源及 `OK` / `DEGRADED` 状态。

前端直接复用现有 V1 API 和业务语义，不在前端重复 Portfolio Calculation、Market Regime 或其他确定性业务逻辑。不扩展为完整交易终端，不实现券商下单、复杂图表、账户体系、移动端适配或非必要 UI 基础设施。

补齐必要的 API Integration、Loading / Error State、基础交互和 Demo 数据准备。

**Done**

* 用户可以通过 Web 界面提交 Investment Question 并获得 Agent Answer；
* Portfolio Snapshot 和 `LONG_TERM` / `SWING` 持仓能够正确展示；
* 当前回答实际使用的主要 Context / Source 能够被识别和展示；
* `OK` / `DEGRADED`、Provider Failure 和 `UNKNOWN` Data 能够被明确呈现；
* 前端不重复实现后端确定性业务逻辑；
* 核心 Demo Flow 可稳定运行；
* V1 可以通过界面完成端到端演示；
* Human Acceptance 通过。

## M8 — Local Portfolio Management

**Status:** IN PROGRESS — Authentication Revision Approved

**Goal**

让本地用户无需预先知道 UUID、无需 Demo Seed 或其他开发者操作，即可从产品主页注册 / 登录本地账户、初始化并持续维护 Portfolio，并通过真实 Investment Agent 完成个性化问答；M8 完成后发布 Local Self-Service MVP `v1.0.0`。

**Scope**

在现有同源 Web Interface 中增加产品主页与最小 Email / Password 注册、登录、退出和持久 Session。注册后的 Account 与当前 `User → Portfolio State` 一对一；用户可立即初始化 Portfolio，也可下次登录后继续。Portfolio Setup 接收 Current Available Cash（默认 `0`）和可选 Existing Positions：ticker、shares、average cost 与可选 Position Type。Opening Position 是独立 immutable Starting Fact，不是经济 Ledger Event，不伪造成 BUY，也不改变 Cash。Opening State 只能在第一笔 Transaction / Cash Event 前提交。提供最小 Ledger Entry UI：BUY / SELL 输入 ticker、quantity、price、可选 Position Type、可选实际发生时间与 reason / note；未分类统一保存为 `UNSPECIFIED`，并与 `LONG_TERM / SWING` 独立。DEPOSIT / WITHDRAWAL 复用 M4 已实现的 Cash Event Domain、Service 与 Public API。当前 State 统一为 `Opening State + Replay(Cash Events + Transactions)`。

Public API 只作为 `PortfolioService.create_user()`、`initialize_opening_positions()` 与 `record_transaction()` 的薄 Adapter，不复制 Domain Validation、金额、手续费、Average Cost、Cash 或 Position 计算。M8 的“修改 Portfolio”只表示初始化 immutable Opening State 或追加新的不可变 Ledger Record，不允许原地编辑或删除历史 Transaction。

Positions、Transactions 与 Cash Activity 分别展示当前仓位、只读交易记录和只读现金记录；不增加历史编辑能力。Decision Questions 可以在当前标签页保留 Question History，但每个问题独立分析，历史不进入模型上下文。正式产品页面调用真实 Investment Agent；确定性 Fake Agent 只用于隐藏的工程 Smoke。Answer 是默认视觉主体，Sources 作为可展开的分析依据。保留 M7 的 Source Grounding、Failure State、身份一致性与安全文本渲染。

**Non-goals**

- Email Verification、Password Reset、OAuth、MFA、Organization、Role / Permission 或完整 Account Platform；
- Cloud Account、Broker Sync 或 Multiple Portfolio Management；
- Chart、Portfolio Performance History 或 Full Transaction History Editor；
- 修改 / 删除既有 immutable Transaction 或 Cash Event；
- React / Frontend Framework Migration 或公开部署。

**Done**

* 首次用户可从产品主页注册本地账户、登录 / 退出，并在重新打开 Browser 后通过有效 Session 恢复；
* 用户可在注册后的引导中立即初始化 Portfolio，也可下次登录后继续；正常 UI 不要求输入或理解 UUID；
* 用户可输入 Initial Cash 与可选 Existing Positions，并自动加载新 Portfolio；
* 页面可一次性录入 Existing Positions，Opening Position 不伪造交易或现金影响；
* 页面可追加 BUY、SELL、DEPOSIT 与 WITHDRAWAL，仓位类型可选，`UNSPECIFIED / LONG_TERM / SWING` 保持独立；
* Transaction 与 Cash Event 具有只读记录视图，不提供 Edit / Delete / Undo；
* 非法 Ticker / Decimal、Insufficient Cash、Oversell、Unknown User 与非法时间具有明确失败状态，失败不产生部分写入；
* 每次写入后 Portfolio Snapshot 反映最新 deterministic Ledger replay，不在前端计算金融事实；
* `Landing → Register / Login → Portfolio Setup → Economic Mutations → Deterministic State + Read-only Records → Independent Question → Real Agent Grounded Answer` 可稳定完成；
* Automated Review、相关 Regression Gate 与 Human Browser Smoke 通过；
* Human Acceptance 通过，并形成 `v1.0.0` Release。

## M9 — Portfolio Import

**Status:** NOT STARTED

**Goal**

通过 Text / Screenshot Import 降低用户初始化 Portfolio 的录入成本，形成 `v1.1.0`。

**Scope**

建立 `Text / Screenshot → Structured Import Draft → Uncertain / Missing Field Highlight → Human Confirmation → Deterministic Validation → Portfolio Write` 流程。识别结果不得直接写 Ledger；原始图片默认不持久化，错误与低置信度 / `UNKNOWN` 字段必须可解释。

M9 复用 M8 已批准的 immutable Opening State 与一次性初始化 Command，只新增识别 Draft、字段置信度 / 缺失状态、Human Confirmation 与图片安全边界。截图中的 ticker、shares 与 average cost 不能伪造成真实历史 BUY；Vision / OCR Provider 仍必须在 M9 实现前评估，不默认假设当前 LLM Adapter 支持图片。

**Non-goals**

- 识别结果绕过确认直接写入；
- 默认持久化原始图片，或把图片内容写入普通日志；
- Broker Sync、自动 Reconciliation 或覆盖所有券商截图格式；
- 从不完整图片推测缺失的 Ticker、Position Type、Shares 或 Cost Basis。

**Done**

* Text 与受支持 Screenshot 均只能生成可审查的 Structured Import Draft；
* 不确定、缺失与非法字段在写入前明确展示并阻止未确认导入；
* Human Confirmation 后复用 deterministic Domain Validation，失败不产生部分 Portfolio State；
* Imported Opening Position 语义不冒充已知历史交易；Position Type 可缺省为 `UNSPECIFIED`，并保留 `LONG_TERM / SWING` 的独立语义；
* 图片隐私、大小 / 类型限制、Provider Failure 与 Injection Boundary 有明确测试和文档；
* Human Acceptance 通过，并形成 `v1.1.0` Release。

## M10 — Accounting & P&L

**Status:** NOT STARTED

**Goal**

先建立版本化、Broker-neutral 的 Fee Policy 基础，再提供语义明确且可确定计算的第一阶段 Accounting / P&L，形成 `v1.2.0`。

**Scope**

依赖顺序固定为 `Fee Policy → Cost Basis → Realized / Unrealized P&L → Return Metrics`。将当前唯一的 `IBKR_PRO_TIERED_US_2026_08` 演化为轻量 Fee Policy Contract / Registry，至少保留既有策略并评估 `ZERO_COMMISSION_US`；不为未来券商构建 Plugin System。Historical Transaction 永久保留创建时的 fee policy 与已持久化 fee，策略演进不得重算历史记录。

第一阶段只提供 Current Market Value、Unrealized P&L、Unrealized Return 与 Realized P&L。Current Market Value 与未实现指标必须保留 Market Price source / timestamp；默认不扣除未来卖出手续费，除非届时批准了明确规则。`LONG_TERM / SWING` 必须先独立核算，才允许向 ticker 或 portfolio 层聚合。Fee Policy、持久化约束和历史重放校验的具体演进属于候选 ADR / Human Review 范围。

**Non-goals**

- 用 `current_value / cumulative_deposit - 1` 冒充完整 Portfolio Return；
- TWR、MWR / XIRR、Return Curve 或 Daily Valuation History；
- Dividend、Tax、Corporate Action、多币种或完整 Broker Statement Accounting；
- 通用 Fee Plugin Framework、未经证实的券商费率或改写历史费用。

**Done**

* 至少两个明确、版本化的 Fee Policy 可独立测试，既有 IBKR Ledger 结果保持不变；
* Historical Transaction 的 fee policy 与实际 fee 不因当前默认策略变化而改变；
* Market Value 与 P&L 使用 Decimal、明确公式和结构化 Source / Timestamp；
* Realized / Unrealized P&L 与 Unrealized Return 对 BUY、部分 / 全部 SELL、费用和 `LONG_TERM / SWING` 有边界测试；
* 缺少或陈旧 Market Price 时不编造 Current Value / Unrealized Metrics，并给出明确状态；
* Human Acceptance 通过，并形成 `v1.2.0` Release。

## M11 — Technical Context

**Status:** NOT STARTED

**Goal**

在现有 Context Routing 与 Price History Tool 上增加按需使用的 deterministic Technical Context，形成 `v1.3.0`；不建设自动交易信号引擎。

**Scope**

保持 `Question → Context Routing → Price History Tool → Deterministic Python Calculation → Structured Derived Facts → LLM Explanation`。初步评估 SMA20、SMA50、Distance to SMA20、Distance to SMA50，并保留现有 range / direction facts。只有问题需要趋势、位置或均线 Context 时才调用 Price History；LLM 只解释已提供事实，不负责指标计算。

当前 Recent Price History 固定为最近 45 个日历日、最多 30 根 Daily Bars，不足以计算 SMA50；M11 必须在保留 completed-bar、freshness、adjustment、source / feed / timestamp 与 Provider Failure 语义的前提下扩展窗口。优先丰富现有 Price History Context，不为指标数量机械增加独立 Tool。

**Non-goals**

- 把 Technical Context 定义为 BUY / SELL Signal；
- 机械注入所有问题，或让 LLM 从原始 Bars 自行计算指标；
- RSI、MACD、Support / Resistance、Candlestick Pattern 或通用 Technical Analysis Engine；
- 分钟级 / 实时指标流、WebSocket、缓存或图表平台。

**Done**

* SMA20 / SMA50 与距离指标由确定性 Python / Decimal 代码计算并具有边界测试；
* Price History 窗口足以支持已批准指标，completed / stale / insufficient data 状态明确；
* 与技术趋势无关的问题不机械调用 Price History，相关问题能够取得并解释 Structured Derived Facts；
* Source Grounding 保留 Provider、Feed、Adjustment、Market Timestamp 与 Fetched At；
* 指标不被表示为自动 BUY / SELL Signal；
* Human Acceptance 通过，并形成 `v1.3.0` Release。

## 5. V2 — Connected Product

V2 只保留高层范围，等 V1.x 的真实使用、Evaluation 与 Failure Mode 提供证据后再制定详细 Milestone：

- Email Verification、Password Reset、OAuth、MFA、Organization、Role / Permission 与远程 Account Lifecycle；
- Multiple Portfolios 与明确 Ownership / Authorization；
- Broker Sync、External Transaction Identity、Idempotency、Partial Fill、Reconciliation 与 Broker / Local Conflict；
- Complete Portfolio Performance History，包括 Daily Valuation、TWR、MWR / XIRR 与 Return Curve；
- Dividend、Corporate Action 及 connected accounting requirements。

Broker Sync 会引入新的信任、身份、对账、幂等与 Credential Security 边界，因此属于 V2，而不是 V1.x 的普通功能增强。Framework、Semantic Memory、Vector Database、Multi-Agent、Cache、Queue 或额外 Infrastructure 仍不作为预设能力；只有真实需求证明必要时，才进入后续 Roadmap、Human Review 与 ADR。
