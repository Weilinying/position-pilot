# PositionPilot V1 Roadmap

## 1. 文档目的

本文件只定义 PositionPilot V1 的 Milestone、范围和完成标准，用于回答“现在开发到哪一步、下一步要做到什么”。

具体类、接口、Task 拆分和并行关系不在本文件中维护。复杂 Milestone 开始前，由 Codex 根据当前 Repository 状态生成或更新 `docs/plans/<milestone>.md`。

开发遵循 Vertical Slice：只建设当前闭环真正需要的能力，不为未来需求提前扩展基础设施。新增能力应由当前 Milestone、Evaluation 或真实 Failure Mode 驱动。

## 2. Current Status

**Current Milestone:** M2 — Minimal Market Data
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

先支持最小流程：User Question → Portfolio Context + Current Market Data → LLM → Personalized Response。此阶段暂不要求完整 News、Fundamentals、VIX、Market Regime 或复杂 Technical Analysis。

PositionPilot 自身的 Agent Orchestration 在进入 M3 时评估，优先使用能够满足当前闭环的最简单方案。

**Done**

* 用户可以使用自然语言提出基础投资问题；
* Agent 自动读取相关 Structured State 和必要 Market Data；
* 不重复询问已经持久化的信息；
* 对相同问题，不同 Portfolio、Available Cash 或 Position Type 能产生合理且可解释的分析差异；
* `LONG_TERM` / `SWING` 在相关场景下会真实影响 Response；
* 当前金融事实来自 Tool，而不是模型训练知识；
* Tool / LLM Failure 有合理处理；
* 存在基础 Agent Evaluation Cases；
* 端到端 Vertical Slice 可运行。

## M4 — Investment Context Expansion

**Goal**

在 M3 核心闭环成立后，只增加能够解决真实问题并改善回答质量的 Investment Context。

**Scope**

根据 Evaluation Case 或已观察到的 Failure Mode，逐步加入 Market Context、News、Fundamentals / Earnings 和必要 Asset Indicators。每增加一类 Context，都必须说明它解决什么问题，并验证其是否改善 V1 核心场景。

M4 不以“覆盖所有可能的金融信息”为目标。无法通过 Evaluation 或真实使用证明价值的 Context 不进入稳定能力。

**Done**

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

把“Agent 看起来能用”转变成可以重复验证的 V1 系统。

**Scope**

建立规模可控的 Evaluation Dataset，覆盖 Entry / Add Position、Market Drop Explanation、Post-Earnings Holding、Position Reduction、不同 Cash、`LONG_TERM` / `SWING`、不同 Market Regime、Provider Failure 和 Missing Data，并补齐必要的 Error Handling、Logging、Tests 和明显技术债。

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
