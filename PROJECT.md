# PositionPilot

## 1. 项目定位

PositionPilot 是一个面向美股投资场景的 Stateful、Context-Aware AI 投资决策辅助 Agent。

它解决的核心问题是：通用 AI 在连续辅助投资决策时，往往不能稳定记住用户的持仓、成本、历史买入位置、剩余可投资资金，以及长期仓与波段仓的区别，导致用户反复补充相同信息，回答也容易脱离个人真实状态。

PositionPilot 的目标是结合“当前用户 + 当前市场 + 当前股票”提供个性化、可解释的投资决策辅助。系统不自动交易、不承诺收益，也不把不确定的未来价格表述为确定事实。

## 2. V1 产品目标

V1 只支持美股及必要的美国上市 ETF。

核心闭环是：

```text
用户自由提问
→ Agent 理解问题
→ 自动读取相关用户状态
→ 获取必要的市场与个股信息
→ 动态选择 Context 和 Tool
→ 综合事实与用户状态
→ 返回个性化 Response
```

典型问题包括“GOOG 今天能买吗？”“为什么今天跌？”“财报以后还应该继续持有吗？”“我还有 300 美元，可以继续加仓吗？”“如果减仓，应该卖波段仓还是长期仓？”

用户已经明确提供并持久化的信息不应被重复询问，除非该信息可能过期、发生冲突或需要确认更新。

## 3. Decision Context

Agent 的判断不能只依赖用户最新一句话。一次投资问题的有效上下文可抽象为：

```text
Decision Context
= User Intent
+ Portfolio Context
+ Transaction Context
+ Market Context
+ Asset Context
+ External Information
```

并非每次请求都需要全部 Context。Agent 应根据当前问题决定真正相关的信息。

例如用户问“GOOG 现在可以买一点吗？”，在正常市场中重点可能是持仓、剩余现金、价格状态、估值和公司新闻；如果 VIX 显著上升、主要指数快速下跌，则整体 Market Risk 应自动进入分析范围。

## 4. Structured State 与 Memory

V1 优先实现 Structured Memory。总可投资资金、剩余现金、Portfolio、Transaction History、Average Cost 和 Position Type 属于结构化事实，应持久化到关系型数据库并作为 Source of Truth。

同一 Ticker 可以同时存在 `LONG_TERM` 和 `SWING` 两类仓位。两者必须在数据结构和分析逻辑中保持区别，因为长期投资 Thesis 与波段交易 Plan 的目标、风险管理方式和退出条件不同。

示例 Transaction：

```json
{
  "ticker": "GOOG",
  "action": "BUY",
  "price": 220.5,
  "shares": 0.45,
  "amount": 99.225,
  "position_type": "LONG_TERM",
  "timestamp": "2026-08-19T10:30:00Z",
  "reason": "首次建立长期仓"
}
```

`amount` 是由 `price × shares` 确定性计算的只读成交金额，不是独立用户输入。Transaction 对现金的实际影响可以包含当前已批准规则产生的交易成本，但 `PROJECT.md` 不绑定具体券商或费率实现。

当前持仓、平均成本、现金变化和仓位比例必须由确定性业务代码计算，不依赖 LLM 从聊天历史推断。

Semantic Memory，例如“用户偏好分批建仓”或“用户长期看好某类资产”，不属于 V1 必需能力。只有出现明确的非结构化长期检索需求时，再评估 Semantic Memory 或 Vector Database。

## 5. Market Context 与 Asset Context

系统需要轻量 Market Context 描述整体市场环境。V1 从少量高价值信息开始，例如 VIX、主要指数表现、市场趋势、必要的市场广度信息和重大宏观事件。

Market Regime 可以抽象为 `NORMAL`、`ELEVATED_VOLATILITY`、`HIGH_STRESS`、`EXTREME_STRESS` 等状态。具体分类标准属于技术实现决策，应由确定性规则产生并记录在 ADR 中，而不是由 LLM 凭感觉判断。

Asset Context 描述个股自身的价格状态，可按真实需求包含 OHLCV、趋势、成交量、波动率、移动平均线、RSI 和 Support / Resistance。VIX、RSI6 等指标只能作为 Decision Context 的一部分，不能直接等价为 BUY / SELL 信号。

## 6. V1 产品架构

V1 使用一个 Single Investment Agent：

```text
User Question
      ↓
Investment Agent
├── User State
├── Portfolio / Transactions
├── Market Context
├── Market Data Tools
├── News Tools
└── Fundamental Data Tools
      ↓
Personalized Response
```

Investment Agent 负责理解问题、决定需要哪些 Context、动态调用必要 Tool，并综合 Portfolio、市场环境和个股信息生成 Response。

只有当真实开发或 Evaluation 暴露明确 Failure Mode，例如 Context Interference、Prompt 过大、Tool Routing 持续不稳定或不同分析领域确实需要独立评估时，才重新考虑 Multi-Agent。

这里的 Investment Agent 属于 PositionPilot 产品架构；Codex 的 worker、explorer 或其他 subagent 只是开发工具，两者不得混淆。

## 7. Tool、确定性代码与 LLM

Tool 负责获取外部事实或暴露系统能力，例如当前价格、历史行情、新闻、财务数据、用户持仓、交易历史和剩余现金。

确定性代码负责平均成本、金额、仓位比例、技术指标以及能够明确编码的 Market Regime 规则。

LLM 负责理解开放式问题、判断需要哪些 Context、选择 Tool、综合多个来源、解释金融信息和生成条件式 Decision Support。

涉及当前价格、当天涨跌、VIX、最新新闻、最新财报和当前估值时，必须使用足够新的外部数据，不能依赖模型训练知识作为当前事实。

## 8. Response 与金融事实原则

PositionPilot 不以简单输出 `BUY / HOLD / SELL` 为目标。回答应解释当前事实、这些事实意味着什么、用户状态如何影响决策、主要风险是什么，以及哪些条件出现后需要重新评估。

系统应尽量区分 `FACT`、`INFERENCE` 和 `UNKNOWN`。如果市场变化存在多个可能原因，不应把某个推断表达成唯一确定原因。

避免“这里一定是底部”“这只股票肯定上涨”“现在买不会亏”等虚假确定性表述，优先使用条件式分析。

## 9. V1 已确定技术方向

V1 已确定使用 Python、FastAPI、Pydantic、PostgreSQL 和 pytest。

具体 ORM、Migration Tool、Dependency Management、Formatter / Lint / Type Checker 等工程方案，在进入对应 Milestone 时再决定。

## 10. 尚未确定的技术问题

PositionPilot 自身的 Agent Orchestration 已在 M3 Human Review 中确定使用 Single Agent + Native Function Calling，M3 不引入 LangGraph。M2 已选择 Alpaca Market Data API v2 REST 作为 Market Data Provider，具体覆盖与限制见 ADR 0004；M3 已选择阿里云 Model Studio 作为 V1 默认 LLM Provider，并保持 Provider / Model 可配置和与 Agent / Domain 解耦；News Provider 和 Financial Data Provider 尚未确定。

“尚未确定”本身是一种有效状态。开发过程中不得因为需要继续编码，就未经评估默认选择某个 Framework 或 Provider。进入相关 Milestone 后，应根据真实需求、Technical Spike 或可验证比较做出决策，并在必要时记录 ADR。

重要技术和架构决策统一记录在 `docs/adr/`。

## 11. V1 Non-Goals

V1 不实现自动交易、券商账户控制、自动调仓、期权策略、量化自动交易、股价预测模型和 A 股支持。

V1 也暂不实现自动投资复盘、行为偏差分析、复杂 Semantic Memory、Vector Database、大型 RAG Pipeline 和 Multi-Agent；不为了增加技术复杂度主动加入 Redis、Kafka、Microservices、Kubernetes、MCP Server 或多个未实际使用的 LLM Provider。

复杂度必须由真实需求证明。

## 12. Evaluation

Evaluation 不只判断“Agent 能不能回答”，还应逐步覆盖 Intent Understanding、Context Retrieval、Portfolio Awareness、Market Context Awareness、Tool Selection、Position Type Correctness、Groundedness、Hallucination、Response Usefulness、Latency 和 Token / API Cost。

尤其需要验证：相同问题在不同 Portfolio 和不同 Market Regime 下，Agent 是否会合理调整分析路径和最终 Response。

具体 Evaluation Dataset 随开发逐步建立，不要求项目启动阶段一次性设计完整。

## 13. 长期产品演进方向

长期方向是：理解用户当前投资状态 → 记录用户为什么做出决策 → 帮助用户复盘 → 识别长期决策模式 → 在真实需求证明必要时演进 Multi-Agent。

这只是产品演进边界，不等于当前开发计划。V1 的 Milestone、开发顺序和 Done Criteria 由 `ROADMAP.md` 管理。

## 14. V1 成功标准

当用户只问“GOOG 今天还能加一点吗？”时，系统无需再次询问已有信息，就能读取当前 GOOG 仓位、平均成本、历史买入位置、长期仓 / 波段仓、剩余资金和当前 Market Context，并根据问题动态获取必要的个股行情、新闻或基本面信息。

最终回答应明显体现：这是基于“当前这个用户 + 当前这个市场 + 当前这只股票”的分析。

如果这一闭环能够稳定实现，V1 即达到主要产品目标。
