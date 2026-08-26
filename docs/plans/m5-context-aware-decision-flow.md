# M5 — Context-Aware Decision Flow 执行计划

## 1. 状态与目标

**Status:** IMPLEMENTED（等待 Human Acceptance）

M5 在 M4 已提供 Portfolio Snapshot、Current Quote、Recent Price History 与 Recent News 的基础上，验证 Single Investment Agent 能否按问题选择最小充分 Context，并补齐 Market Context / Market Regime 对相关决策问题的影响。

M5 不把开放式投资意图降级为大规模关键词分类，也不增加第二个产品 Agent。Native Function Calling 继续负责开放问题的 Tool Selection；Application 负责能力清单、调用预算、参数与失败校验、确定性派生事实、结构化日志和可重复 Evaluation。

## 2. 当前证据与缺口

- Current Quote、Recent Price History 与 Recent News 已能在同一 Tool Round 中独立或组合调用，单类问题已有“不机械调用其他 Tool”的固定评测。
- Portfolio Snapshot 必定注入，并保留同一 ticker 的 `LONG_TERM` / `SWING`；已有相同问题在不同 Cash 或 Position Type 下的 Behavioral Cases。
- Context Selection 目前只能从 Provider Fake 的请求记录间接观察；生产日志没有一次请求级的选择摘要，难以把 Tool Call 与 Portfolio / Position Type Context 关联起来。
- `market_context` 在 M5 开始时仍为 `UNAVAILABLE`；2026-08-26 Human Review 已批准使用 SPY Daily Price Stress 的 V1 Heuristic，等待实现 Market Regime、Source Tracking 与相关 Routing Case。
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

## 5. 已批准 Market Context 方案

2026-08-26 Human Review 批准以下 V1 方案：

- 复用 ADR 0004 的 Alpaca Historical Daily OHLCV，不新增 Provider、Credential 或 Infrastructure。
- 使用 `SPY` 作为美国大盘股市场代理；它不代表完整美股市场、VIX、市场宽度、宏观环境或任意个股。
- 查询最近 90 个日历日、最多 60 根调整后 Daily Bars，结束时间至少落后当前 15 分钟；至少需要 21 根有效 Bars。
- 确定性计算并保留原始指标：5-session Close Return、20-session Latest Close Drawdown from Maximum Close、20-return Annualized Realized Volatility。
- 指标单位为百分比，统一保留 4 位小数并使用 Half-even；分类使用同一已量化值，避免展示值与阈值判断不一致。
- Regime 采用最高严重度规则：

| Regime | 任一触发条件 |
|---|---|
| `ELEVATED_VOLATILITY` | Volatility ≥ 25%，或 Drawdown ≤ -5%，或 5-session Return ≤ -3% |
| `HIGH_STRESS` | Volatility ≥ 40%，或 Drawdown ≤ -10%，或 5-session Return ≤ -6% |
| `EXTREME_STRESS` | Volatility ≥ 60%，或 Drawdown ≤ -15%，或 5-session Return ≤ -10% |
| `NORMAL` | 未触发以上条件 |

- 阈值元数据必须明确标记为 `V1_HEURISTIC`：它们是工程启发式规则，不是行业标准、没有经过历史回测验证，也不是投资信号。
- Tool Result 必须保留三个原始指标、触发规则、观察数量、Period Start / End、Provider、Feed、Coverage、Adjustment 与 Fetched At，便于后续 Eval 或 Backtest 驱动调整。
- Market Context 是 Portfolio Risk Context / risk modifier；没有明确既定规则、并要求判断当前是否应该增加或减少风险暴露时才属于 minimum decision context。购买能力、纯事实查询与既定规则执行不机械调用。
- Market Context Failure 保持明确状态并产生 `DEGRADED` Answer；不得从用户前提、个股新闻或训练知识补造 Regime。
- Public Source Type 增加 `MARKET_CONTEXT`，使用 `ticker=SPY`；其余 Response Shape 不变。
- 单轮 Tool Call Budget 继续为 4，不因为新增能力默认提高调用成本。

决策记录见 ADR 0007。

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

## 8. Completion Summary

### Implemented

- 保持 Single Agent + Native Function Calling，不增加关键词 Intent Router、第二个产品 Agent 或新 Framework。
- 新增不记录问题正文、User ID 或 ticker 的 `ContextSelectionTrace`，记录可用 / 选中 Tool、唯一 Context 数、与持仓匹配的 Position Type、未持有标的数和 Routing Latency。
- 新增固定无参数 `get_market_context()`；模型不能控制 SPY、时间窗口、Bar 数量、指标或阈值。
- `MarketContextService` 固定最近 90 个日历日、最多 60 根 SPY Daily Bars 与 15 分钟 End Lag，并按 New York 常规收盘时间保守过滤尚未完成的当前 Session Bar。
- Domain 使用固定 50 位 Decimal 中间精度计算 5-session Return、20-session Close Drawdown 与 20-return Annualized Realized Volatility，统一 4 位 Half-even 后按最高严重度分类。
- Tool Result 保留三个原始指标、完整 Threshold Table、Trigger Rule、Period、Observation Count 与 Provider Metadata，并明确 `V1_HEURISTIC` 不是行业标准、未经历史回测验证且不是投资信号。
- Context Capability 将 `market_context` 设为 `AVAILABLE`；Public Source Type 新增已批准的 `MARKET_CONTEXT` / `SPY`，其余 Response Shape 不变。
- LLM 仍通过 Native Function Calling 自主选择 Optional Tools；Current Quote Tool 结构化声明 `request_purpose`，仅当模型声明 discretionary current risk action 且漏选 Market Context 时，由 Application 在同一 Round 补足。该保证明确限定为 model-declared floor，purpose 误分类由 Behavioral Eval 诊断；四类 Context 继续共享最多 4 次调用预算，不增加关键词 Router。
- Final Structured Response 使用 provider-neutral `JSON_OBJECT`，Aliyun Adapter 映射 Provider-native JSON Mode；Application Parser、Source Validation 与一次 Repair 保留为 defense-in-depth。
- Behavioral Dataset 保留相同问题下 `NORMAL` / `HIGH_STRESS` 对照，并新增既定减仓规则检查不机械调用 Market Context、Market Context Failure 和 Source / Retrieval Trace；既有 Cash 与 Position Type 对照继续保留。
- Market Context Provider Failure Case 要求成功 Quote 与失败 Market Context 同轮调用，自动验证 `DEGRADED` 与 Tool Trace，并由 Human Checks 确认 Regime 保持 `UNKNOWN`、不从训练知识或个股信息补造整体市场状态。

### Automated Review

- 第一轮 Review 发现 `now-15min` 不能单独证明当日 Daily Bar 已完成；Service 现按 `America/New_York` 常规 16:00 收盘和 15 分钟数据延迟过滤，早收盘日采用保守延迟纳入。
- 修正百分比中间除法可能受调用线程全局 Decimal Context 影响的问题；所有 Return、Drawdown、Sample Standard Deviation、Annualization 与 Quantize 均在固定精度中执行。
- 修正非法 `QQQ` / 非 `1Day` 成功 Payload 可能被样本不足掩盖的问题，先验证固定代理与粒度，再映射 `NO_DATA`。
- Service Boundary 进一步拒绝非 `ALPACA / SIP / CONSOLIDATED / ALL / USD` 的成功 Payload，避免用不符合已批准语义的数据计算 Regime。
- `MarketRegimeContext` 构造期重算 Regime / Trigger IDs，并拒绝正 Drawdown、负 Volatility 或互相冲突的结构化事实。
- Review 后复审确认上述 P1 / P2 全部关闭；Agent Integration 复审未发现 Critical、High、Medium 或 Low Finding。

### Verification

- 默认全量 pytest：335 passed，36 skipped。
- 跳过项为 22 条未显式启用的真实模型 Behavioral Eval、2 条在线 Alpaca Market Tests、1 条在线 Alpaca News Test、1 条真实 Agent Smoke Test，以及未配置 `TEST_DATABASE_URL` 的 10 条 PostgreSQL Integration Tests。
- Ruff format check / lint：PASS；mypy strict：PASS（55 source files）。
- `uv lock --check`、Alembic head / history 与 `git diff --check`：PASS。

### Decision Records 与限制

- 新增 ADR 0007，记录 SPY Proxy、指标、Threshold、Heuristic 边界、Trade-off 与重新考虑条件；本次不需要额外 Engineering Note。
- SPY 只代表美国大盘股代理，V1 不包含 VIX、市场宽度、主要指数集合、Sector、Macro 或盘中 Market Regime。
- Human Review 已批准 7 个日历日 Freshness Guard；最新 completed SPY Daily Bar 超过该边界时返回 `NO_DATA`，Regime 保持 `UNKNOWN`。该工程启发式只检测明显陈旧数据，不引入 Market Calendar。
- 阈值没有历史回测验证；后续只能由固定 Eval、真实使用或 Backtest 证据驱动调整，不能因模型偏好修改。
- 已显式启用真实 LLM Behavioral Eval 命令，但当前环境没有 `LLM_API_KEY`，22 个真实模型 Cases 按既有 Gate 跳过；不能据此声称 Repair Rate 已改善。在线 Alpaca Tests 与真实 Agent Smoke Test 同样未运行。
