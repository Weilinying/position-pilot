# M5 — Context-Aware Decision Flow 执行计划

## 1. 状态与目标

**Status:** IN PROGRESS

M5 在 M4 已提供 Portfolio Snapshot、Current Quote、Recent Price History 与 Recent News 的基础上，验证 Single Investment Agent 能否按问题选择最小充分 Context，并补齐 Market Context / Market Regime 对相关决策问题的影响。

M5 不把开放式投资意图降级为大规模关键词分类，也不增加第二个产品 Agent。Native Function Calling 继续负责开放问题的 Tool Selection；Application 负责能力清单、调用预算、参数与失败校验、确定性派生事实、结构化日志和可重复 Evaluation。

## 2. 当前证据与缺口

- Current Quote、Recent Price History 与 Recent News 已能在同一 Tool Round 中独立或组合调用，单类问题已有“不机械调用其他 Tool”的固定评测。
- Portfolio Snapshot 必定注入，并保留同一 ticker 的 `LONG_TERM` / `SWING`；已有相同问题在不同 Cash 或 Position Type 下的 Behavioral Cases。
- Context Selection 目前只能从 Provider Fake 的请求记录间接观察；生产日志没有一次请求级的选择摘要，难以把 Tool Call 与 Portfolio / Position Type Context 关联起来。
- `market_context` 仍为 `UNAVAILABLE`，没有 Market Regime 数据、确定性规则、Source Tracking 或相关 Routing Case。
- Transaction History、Earnings、Fundamentals、Asset Metadata 与 Technical Analysis 仍不可用；只有新的 Evaluation Failure 证明必要时才加入 M5。

## 3. Acceptance Criteria

- Portfolio-only 问题不调用外部 Context Tool；Quote-only、History-only 与 News-only 问题不机械调用其他 Tool。
- 多部分问题只组合实际需要的 Context，继续受单轮调用预算和 `(tool, ticker)` 去重约束。
- 每次成功的首轮 Native Tool Selection 产生结构化 Trace，包含可用 Tool、选中 Tool、唯一 Context 数量、与当前持仓匹配的 Position Type、未持有标的数量和 Routing Latency；不记录问题正文、User ID 或 Secret。
- 相同问题的 Low / High Cash、`LONG_TERM` / `SWING` 固定场景保留可解释的回答差异，且 Tool Trace 不因无关 Context 扩张。
- Human Review 批准后，Market Context 使用明确来源与确定性 Market Regime 规则；只在相关问题中进入 Context，失败时保持 `UNKNOWN` / `DEGRADED`。
- Context Selection 可通过日志和固定 Evaluation Trace 定位，不新增 Agent Framework、Database、Cache、Queue 或 Multi-Agent 产品架构。

## 4. 执行顺序

```text
T1 M5 Plan + Context Selection Trace
  ↓
T2 Routing / Logging Unit Tests + Behavioral Matrix Baseline
  ↓
T3 Market Context / Market Regime Decision Proposal
  ↓ Human Review Gate
T4 Provider-neutral Market Context + Deterministic Regime
  ↓
T5 Agent Tool / Routing / Source Tracking Integration
  ↓
T6 Behavioral Evaluation + Architecture / Decision Records
  ↓
T7 Full Checks → Automated Review → Fix → Re-check
  ↓
Atomic Commits → Human Acceptance
```

## 5. Market Context Human Review Gate

实现前必须批准以下内容：

- 使用现有 Alpaca Historical Daily OHLCV 还是选择新的 Market Data Provider；
- 代表整体美股市场的输入标的、窗口、Feed、Freshness 与 Failure State；
- Market Regime 的确定性指标、阈值、状态与适用边界；
- Market Context 何时需要调用、何时不应调用，以及它如何影响分析但不直接生成 BUY / SELL Signal；
- 是否扩展 Public Source Type，以及对应 API Contract。

这些选择会影响关键金融规则、Provider Boundary 或公共 API，因此在 Decision Proposal 获得 Human Review 前不实现相关代码。

## 6. Non-Goals

- Deterministic BUY / HOLD / SELL、Position Sizing 或自动交易。
- 用 Market Regime 预测指数或个股价格。
- 大规模关键词 Intent Router、第二个产品 Agent、LangGraph 或 Multi-Agent。
- VIX、Breadth、Macro、Sector、Earnings 与 Fundamentals 一次性全量接入。
- 为 Routing 新增 Database、Vector Database、Cache、Queue 或完整 Observability Platform。

## 7. 验证方式

- Pure Unit Tests 验证 Context Selection Trace 的去重、无 Tool、持仓匹配、`LONG_TERM` / `SWING` 保留与未持有标的计数。
- Agent Tests 验证首轮 Context Selection 日志、非法 Tool Call 不产生成功选择 Trace、既有 Tool Budget / Failure / Source Contract 无 Regression。
- Behavioral Eval 使用固定 Portfolio、Market / News Results 和真实模型，精确验证 Quote / History / News 的实际请求 Trace；自然语言个性化继续保留 Human Checks。
- Market Context 获批后使用固定正常 / 压力场景验证确定性 Regime、相关问题的 Tool Selection、无关问题不调用、Provider Failure 与 `UNKNOWN`。
- 完成后运行默认 pytest、Ruff format / lint、mypy strict、`uv lock --check`、Alembic head / history 与 `git diff --check`。
