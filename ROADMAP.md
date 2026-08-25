# PositionPilot V1 Roadmap

## 1. 文档目的

本文件只定义 PositionPilot V1 的 Milestone、范围和完成标准，用于回答“现在开发到哪一步、下一步要做到什么”。

具体类、接口、Task 拆分和并行关系不在本文件中维护。复杂 Milestone 开始前，由 Codex 根据当前 Repository 状态生成或更新 `docs/plans/<milestone>.md`。

开发遵循 Vertical Slice：只建设当前闭环真正需要的能力，不为未来需求提前扩展基础设施。新增能力应由当前 Milestone、Evaluation 或真实 Failure Mode 驱动。

## 2. Current Status

**Current Milestone:** M4 — Investment Context Expansion
**Status:** IN PROGRESS

Milestone 状态统一使用 `NOT STARTED`、`IN PROGRESS`、`DONE`，不维护百分比进度。

## 3. V1 Milestones

```text
M0 Project Foundation
→ M1 Portfolio & Transaction State
→ M2 Minimal Market Data
→ M3 Minimal Investment Agent
→ M4 Investment Context Expansion
→ M5 Context-Aware Decision Flow
→ M6 Evaluation & V1 Hardening
```

M0～M3 应尽快形成第一个端到端可用闭环；M4～M6 再逐步增加上下文质量、动态路由和可靠性。

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

## 4. V1 之后

V1 完成前不展开 V2～V5 的详细 Roadmap。后续方向继续以 `PROJECT.md` 为准，并根据 V1 的真实使用、Evaluation 和 Failure Mode 再制定下一阶段 Roadmap。

Framework、Skill、Semantic Memory、Vector Database、Multi-Agent、额外 Infrastructure 等能力不作为预设 Milestone；只有真实需求证明其必要性时，再进入后续 Roadmap 或 ADR。
