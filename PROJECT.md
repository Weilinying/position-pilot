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

M0～M7 只构成以上核心能力与 Demo Interface 的内部 Engineering Milestones。正式 `v1.0.0` 还要求本地用户无需预先知道 UUID、运行 Demo Seed 或执行其他开发者操作，即可从产品主页注册 / 登录本地账户，初始化 Portfolio，通过 BUY / SELL / DEPOSIT / WITHDRAWAL 持续维护 Structured State，并取得真实 Investment Agent Response；Version / Release 与 Milestone 的对应关系由 `ROADMAP.md` 管理。

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

`initial_cash` 只表示 Portfolio 创建时的初始资金。创建后的追加资金投入与资金取出使用独立、不可变的 Cash Event Ledger，当前只支持 `DEPOSIT` 与 `WITHDRAWAL`；不得通过修改历史 `initial_cash` 或伪造 BUY / SELL Transaction 改变资金历史。Available Cash 由 Initial Cash、Cash Events、Transactions 与现有交易成本规则确定性重建，Withdrawal 不得产生负现金。

系统开始跟踪前已经存在的持仓使用独立、不可变的 Opening State 表达，只记录 ticker、shares、average cost、可选 Position Type 与后端记录时间。Opening Position 不是经济 Ledger Event，不伪造成 BUY、不扣减现金、没有交易 sequence 或手续费；当前 State 由 Opening State 与 Cash / Transaction Ledger 共同确定性重建。

已有 Portfolio 的截图校准使用独立、不可变的 Position Reconciliation 事件，保存对应 `(ticker, position_type)` 的 `target_shares`、`target_average_cost`、确认时间、来源及可选 broker / source info。Replay 在确认时间将该仓位直接校准到目标状态，之后的 Transaction 继续生效；它不生成 BUY / SELL、不改变 Cash，也不删除截图中未出现的持仓或修改任何历史事实。

从 M9 开始，Opening State 中的 Asset Identity 以 Asset Metadata Provider 验证后的 canonical symbol 表示；现有 `ticker` 字段承载该 canonical symbol，而不是未经验证的用户输入或公司名称。每一条可提交的 Opening Position Draft 都必须绑定 Provider 验证后的 Asset Identity：自由输入必须由用户从真实候选中明确选择；Recognition 明确识别的 `suggested_symbol`，或在其缺失时明确识别的 `ticker`，经后端 exact validation 成功后可以自动绑定，验证失败或存在歧义时才要求用户选择。修改已绑定的 ticker 后必须重新选择或重新验证。V1 不建立、复制或持续同步完整的本地 Asset Master；M9 只通过 Provider-neutral Asset Metadata Boundary 规范化前端 Asset Selector 与写入校验所需的 canonical symbol、display name 和 exchange，Provider-specific Payload 不进入 Portfolio Domain。Provider exact validation 成功只表示当前能够识别并规范化该 symbol，不把 Provider 未明确提供的 active / inactive 状态推断为 Portfolio Domain Truth。只有当前界面出现真实需求时才增加其他 Metadata 字段，不建设通用证券主数据模型。

V1 的 Email / Password 账户只为本地产品闭环提供稳定身份与 Portfolio Ownership。Account 与现有单一 `User → Portfolio State` 之间保持一对一关系；Browser 不再把 UUID 当作正常用户身份或恢复方式。密码明文不得持久化，认证后由 HttpOnly Session Cookie 识别当前 Account，Portfolio 与 Investment API 的 User Identity 必须由 Session 在 Server 端确定。

同一 Ticker 可以同时存在 `UNSPECIFIED`、`LONG_TERM` 和 `SWING` 三类独立仓位。`UNSPECIFIED` 只表示用户尚未提供策略分类，系统与 LLM 都不得自动把它推断为长期仓或波段仓；已明确的长期与波段仓仍必须在数据结构和分析逻辑中保持区别，因为两者的 Thesis、Plan、风险管理方式和退出条件不同。

### M9 当前持仓与批次扩展（2026-09-10 确认，已在 M9 Branch 实现）

保留交易与资金历史作为事实来源。当前持仓由剩余批次汇总，UI 按 ticker 展示总体，展开后直接列出 UNSPECIFIED 批次，再列 SWING、LONG_TERM 分组及各自按购买时间排序的批次；不在主页面并列展示起始持仓与校准记录。

BUY 建立批次，SELL 明确选择扣减批次并释放其成本，剩余均价由剩余成本与股数重算。批次策略类型可调整并记录生效时间，不改变总股数、总成本或现金，不覆盖历史交易分类。成交字段通过引用原交易的更正记录修正并重放，不能覆盖原始事实。此扩展替代聚合仓位“部分卖出均价永远不变”的核算规则。

截图保存后仍能直接手工维护：导入持仓使用无现金影响的校准；真实交易使用更正；策略类型直接调整。截图只有聚合值时不推测购买批次或日期，显示来源与未知时间。批次明细与聚合校准必须由同一确定性重放产生，不能维护第二份独立持仓。

M9 提供当前市值与未实现指标。新手工 BUY 录入券商显示的含费平均成本，不再额外估算手续费；新手工 SELL 录入可选实际 Fee，并按成交金额减去 Fee 更新现金。历史 Transaction 永久保留原 fee schedule 与 commission 口径。Transaction 截图导入属于 M10，已实现盈亏属于 M11。2026-09-11 确认暂缓 M10，M11 直接基于 M9 的手工交易、费用与批次事实推进，不依赖交易截图导入。账户历史收益率需完整资金事实与明确口径，另行规划，不等同于当前持仓盈亏百分比。本地旧测试数据不做兼容迁移，可在实施时重置后重新录入。

执行细节见 [M9 当前持仓与批次计划](docs/plans/m9-current-holdings-and-batch-editing.md)。

### M11 已实现盈亏（2026-09-12 确认）

统一 Replay 同时产生当前 Portfolio 和每次 SELL 的批次分配结果。已实现盈亏等于卖出成交额减去
已记录卖出费用及释放的批次成本；单次收益率以释放成本为分母。费用按分配股数摊分并处理舍入
余数，完全卖出后仍保留历史收益。历史收益按卖出当时批次类型归属，之后修改剩余批次类型不移动
旧收益；更正 BUY 成本则重算相关历史卖出的有效收益。

Opening、校准和出入金本身不生成交易收益。校准生效前的 SELL 使用当时成本，之后使用确认后的
成本。已实现不依赖当前行情；任一当前持仓行情缺失时，组合未实现与交易盈亏合计明确不可用。
全清仓时未实现为零。已实现加当前未实现只是账本覆盖范围内的交易盈亏金额，不代表完整账户
历史收益率。执行见 [M11 计划](docs/plans/m11-accounting-and-pnl.md)，核算决策见
[ADR 0013](docs/adr/0013-replay-derived-realized-pnl.md)。

以下交易示例沿用现有接口；新增批次相关 Schema 随实现更新。示例 Transaction：

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

`amount` 是由 `price × shares` 确定性计算的只读金额，不是独立用户输入。手工 BUY 的 `price` 表示含费平均成本；手工 SELL 的 `price` 表示成交价，并可另行提供实际 Fee。费用数值与口径随 Transaction 保存，后续规则变化不得改写历史经济结果。

当前持仓、平均成本、现金变化和仓位比例必须由确定性业务代码计算，不依赖 LLM 从聊天历史推断。Cash Event 只影响现金，不改变 Position Shares、Cost Basis 或 Average Cost。

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

PositionPilot 提供投资分析，不接入券商下单。普通投资分析、加仓建议与资金分配默认按金额表达，
不以 Broker、Account 或 Ticker 的碎股权限验证为前置条件，也不因权限未知拒绝分析。用户明确说明
账户支持碎股时，Agent 可以把它作为本轮条件使用，无需重复验证。用户明确要求股数时，可以用用户
预算与可靠价格做确定性的理论股数计算，但必须标明这不是账户实际可执行订单数量；只有用户明确询问
券商账户权限时，才根据可用证据回答，缺少依据则保持 UNKNOWN。任何建议都不得扩大用户本轮预算、
覆盖 Available Cash 或直接修改 Portfolio / Ledger。若未来接入真实订单执行，tradable、fractionable、
minimum notional / quantity、rounding 与账户权限必须另行建立可靠来源和执行 Contract。

Portfolio Import 中的识别结果只生成可审查 Draft，不直接成为 Structured State。Recognition Confidence 只用于帮助用户定位需要复核的字段，不是 Portfolio Domain Truth，也不形成独立 Write Gate；最终写入只接受用户明确确认、在本地 Browser Draft 中已绑定 Provider-validated Asset Identity 且通过 deterministic Domain Validation 的确定字段。M9 接受仅限 loopback 本地产品的受信任 Browser 边界，Confirm 不重复调用 Asset Provider；若未来暴露到公网或不受控客户端，必须恢复写入时验证或引入后端签名的短期 Asset Receipt。Asset Metadata Provider 与 Vision / OCR Capability 必须在实现前通过短 Capability Spike 完成选型，并通过各自的 Provider-neutral Boundary 接入。Recognition 输出只作为数据处理，不进入 PositionPilot Agent 的指令链路。

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

PositionPilot 自身的 Agent Orchestration 已在 M3 Human Review 中确定使用 Single Agent + Native Function Calling，M3 不引入 LangGraph。M2 已选择 Alpaca Market Data API v2 REST 作为 Market Data Provider，具体覆盖与限制见 ADR 0004；M3 已选择阿里云 Model Studio 作为 V1 默认 LLM Provider，并保持 Provider / Model 可配置和与 Agent / Domain 解耦；M9 已选择 Finnhub 作为 Asset Metadata Provider、Alibaba Model Studio `qwen3-vl-flash` 作为 Vision / OCR Capability，具体边界见 ADR 0010；News Provider 和 Financial Data Provider 尚未确定。

“尚未确定”本身是一种有效状态。开发过程中不得因为需要继续编码，就未经评估默认选择某个 Framework 或 Provider。进入相关 Milestone 后，应根据真实需求、Technical Spike 或可验证比较做出决策，并在必要时记录 ADR。

重要技术和架构决策统一记录在 `docs/adr/`。

## 11. V1 Non-Goals

V1 不实现自动交易、券商账户控制、自动调仓、期权策略、量化自动交易、股价预测模型和 A 股支持。

V1 也暂不实现自动投资复盘、行为偏差分析、复杂 Semantic Memory、Vector Database、大型 RAG Pipeline 和 Multi-Agent；不为了增加技术复杂度主动加入 Redis、Kafka、Microservices、Kubernetes、MCP Server 或多个未实际使用的 LLM Provider。

V1.x 保持本地、受控环境与单 Account / 单 Portfolio Context。V1 只实现基础 Email / Password 注册、登录、退出和持久 Session，不实现 Email Verification、Password Reset、OAuth、MFA、Organization、Role / Permission、Cloud Account、Broker Sync、Multiple Portfolio Management、完整 Portfolio Performance History、Dividend 或 Corporate Action；这些 Account Platform、connected product 与 accounting 边界留到 V2。

M9 Import 辅助 Portfolio Opening State 初始化，并允许用户用当前截图对已有 Portfolio 追加一次明确确认的 Position Reconciliation。它不提供 Broker / Account Connection、自动 Sync、自动 Diff、Conflict Resolution 或持续同步；Recognition Draft 也不得绕过用户确认直接写入。

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

当本地用户还能在不预先取得 UUID、运行 Demo Seed 或理解开发 Fixture 的情况下，从公开产品主页完成注册 / 登录、初始化并维护上述 Structured State，并通过正式 Single Investment Agent 获得基于当前持仓和市场 Context 的真实 Response，这一闭环即达到 `v1.0.0` Local Self-Service MVP 的主要产品目标。
