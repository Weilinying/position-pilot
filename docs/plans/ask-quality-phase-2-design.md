# Ask Quality Discovery — 阶段二：最小设计与 Decision Proposal 执行计划

## 1. 目标、状态与进入条件

**Status:** IN PROGRESS — 设计与 Automated Review 已于 2026-09-15 完成，等待
Human Review；Discovery 方向及本文状态分离原则已于 2026-09-13 获方向性批准；
Confirmed Mutation Boundary 已于 2026-09-14 获批准。具体 Schema、API、存储适配器、
Framework / Provider 与其余实施提案仍待证据和所需评审。

目标：用阶段一证据明确 **Domain State / Strategy State / Conversation Context / Long-term
Memory / Agent Runtime / Research / Answer** 边界，准备四类独立选型评分与后续实现。
先明确业务状态与记忆的归属，通过 4A 研究循环、4B 最小持久策略依次验证，不先建设通用记忆平台。

输入：[阶段一基线](ask-quality-phase-1-baseline.md) 的已运行证据、能力缺口与评分表；
[整体路线](ask-quality-discovery.md)、现行 [PROJECT.md](../../PROJECT.md)、
[Discovery Note](../engineering-notes/post-v1-answer-quality-discovery.md)。

阶段一已于 2026-09-15 完成真实 `qwen3.7-max` 基线、Human Rubric Calibration 与
Human Acceptance。每项设计必须连接具体 Case / Failure；没有当前闭环需求的部分写
“暂不实现及恢复条件”。

## 2. P2-T0 — 从失败确定最小产品行为

为主要失败填写一张决策表：

| Failure / Case | 当前行为与限制 | 目标行为 | 所需能力 / 约定 | 验证方式 |
|---|---|---|---|---|
| AQ01 | 未核验“今日下跌”就按真分析 | 先核验会改变分析基础的前提；无法核验则明确保留 UNKNOWN | Intraday Fact、可解决 UNKNOWN 时的 Research Loop、Gate | 固定事件时间线；`UNVERIFIED_CRITICAL_FACT_TREATED_AS_TRUE` 必须为 0 |
| AQ02 | 新闻无关且 Runtime 没有 Search | 说明当前证据不足；未提供的搜索能力不假装已执行 | Capability Coverage 与 Research Sufficiency 分开 | 无关新闻 Fixture；不因 Runtime 缺能力单独扣 RS |
| AQ03 | Quote 210.25 足以否定 180 的错误前提 | 现有证据足够时直接纠正并停止 | Evidence Sufficiency 不等于必须 Search | 保留三次 RS=2 的正向回归锚点 |
| AQ05 | 能区分账户 Cash 与本轮 500 预算，但条件分析弱 | 保留执行数量 UNKNOWN，同时完成已知部分的条件分析 | 本轮 Context、Quote / Portfolio / Market Context | 与 AQ06 只改变 `budget=500→200` |
| AQ06 | `200 < 210.25` 计算正确，但在碎股 / 账户权限 UNKNOWN 时建议提高预算 | 允许整股 / 碎股条件分支；不得从 UNKNOWN 生成确定执行限制或资金建议 | Execution Fact Authority、确定性计算、Gate | `UNVERIFIED_EXECUTION_FACT_USED_FOR_ACTIONABLE_CONCLUSION` 必须为 0 |
| AQ07 | 无策略时容易全盘拒答 | 已有证据的 LONG_TERM / SWING 条件分析先完成，再问关键个人条件 | Answer Contract、假设 / 候选策略标记 | 无策略但有市场证据的案例 |
| AQ09～AQ12 | 请求没有历史；AQ12 把恢复任务转给用户 | 延续话题、采用纠正后的预算；缺历史时主动重新评估 | Thread Context、引用解析、恢复策略 | 固定多轮脚本；GOOG / MSFT 事实不串用 |
| AQ13～AQ16 | 无持久策略；未确认建议不能当事实 | 读取已确认 Strategy；需要时重新展示 Draft 并等待绑定确认 | Strategy / Memory 分离、Pending Mutation、来源链 | 跨对话、未确认建议对照；旧策略不复活 |
| AQ17a / AQ17b | 能区分正常空结果与 Provider Failure；AQ17a 三次均 Repair | 保留错误语义，让正常空结果首次 Final 直接符合 Source Contract | 结构化失败 / Source 状态 | Fake Provider 对照；Repair 率单列 |
| AQ18 | 冲突新闻可完整执行 | 保留冲突并回查原文，不简化为“较新即真” | 来源归因、时间与独立性 | Protected FULL Regression |
| AQ19 | 当前没有实际 Page Fetch | 外部文本始终是不可信数据，不能修改任何状态或权限 | Fetch 边界、Prompt Injection 防护 | Protected DIAGNOSTIC；纸面设计不当已验证能力 |

表中内容是启动草案。基线如发现不同主因，修改表格并解释证据。目标不规定唯一工具路径，
不要求每问必查新闻或必给交易结论。

阶段二继承冻结的评测分母：Primary 为 r1 的 21 个唯一变体（FULL 9 / DIAGNOSTIC
12）；r2 / r3 共 10 次只是 Repeat Consistency，不混入 Primary 质量分布。`31 / 31`
是请求可靠性，不是 31 条独立质量样本。AQ04、AQ12、AQ18、AQ19 是已观察的
Protected Evaluation Set，不按具体 wording 调优，可做 Regression，但不称 unseen
holdout。新能力可在新 Run 重新评估 Scope，不回写或重标历史 Phase 1 结果。

## 3. P2-T1 — 五类状态与 Context 的语义设计

### 3.1 信息类型与权威来源

**Architecture Principle：Memory 不是所有“过去信息”的统称，Framework 不拥有业务语义。**
为以下五类信息分别写明 Source of Truth、生命周期、读取时机和写入条件：

| 类型 | 候选用途 | 必须解决的问题 |
|---|---|---|
| Domain State | Portfolio、股数、成本、现金、交易、批次与 Position Type | 现有确定性数据库 / Ledger；不是 Memory，聊天与记忆不能覆盖 |
| User Strategy State | Thesis、LONG_TERM / SWING 目标、期限、风险预算、计划投入、退出条件 | 结构化、可确认、可版本化的业务记录；不交给 LLM 自由写入通用 Memory |
| Conversation State / Context | 当前话题、本次 500 美元预算、已澄清条件、消息历史 | Application 管理 Thread、引用解析、纠正与上下文长度 |
| Long-term Memory | 反复出现、但不适合固定策略字段的长期偏好 / 背景 | 独立候选、确认、来源、过期与 Retrieval；不得作为结构化策略事实的替身 |
| Agent Execution State | 一次 Run 的 tool call、observation、next action 与执行状态 | Runtime 内部状态；可按需求持久化 / 恢复，但不进入产品 Memory |

**Confirmed Mutation Boundary：Ask 可以提出状态变更，但不能自行使状态生效。** 任何会改变
Domain State、Strategy State 或有效 Long-term Memory 的操作，都必须经过明确的目标解析、
结构化草案、影响展示、用户确认和对应业务服务的确定性校验；只有业务服务成功提交后，Agent
才能声明更新完成：

```text
识别变更
→ 生成结构化草案
→ 展示将改变的目标、范围与值
→ 用户确认当前唯一的 Pending Mutation
→ Domain / Strategy / Memory Service 校验并提交
→ Agent 返回实际提交结果
```

Confirmation 必须绑定一个明确、当前且唯一的 Pending Mutation，而不是绑定一组硬编码肯定词。
`嗯`、`可以`、`确认`、`保存吧` 等回复只有在上一条系统消息明确展示了即将保存的内容，且当前
不存在多个可能目标时，才可能确认该 Pending Mutation。用户的确认只授权该 Candidate 已展示的
operation、scope 与字段，不构成对其他推断、派生字段或后续变更的授权。候选已过期、已被替代、
存在多个候选或指代不清时必须重新确认。

Mutation 按影响分为三个层级，不能因为都从对话发起就共用一套宽松写入规则：

| 层级 | 示例 | 生效边界 |
|---|---|---|
| Conversation-only update | “这次最多投 500”、本轮 ticker / 意图纠正 | 当前 Thread Context 生效；不写持久业务状态，不需要持久化确认 |
| Persistent semantic update | Strategy、有效 Long-term Memory | `PENDING` Candidate → 明确确认 → 对应 Service 写入；Strategy 与 Memory 仍分开建模 |
| Financial fact mutation | 已发生的 DEPOSIT / WITHDRAWAL、BUY / SELL Ledger Transaction、现有 Position Reconciliation；`CashReconciliation` 为 Deferred 且当前没有 Command | 更严格的结构化草案、影响展示与确认；只能调用获批的 Domain Command，并通过确定性校验，不触发订单或券商操作 |

金融事实草案必须包含对应 Domain Command 所需的确定字段。Cash Event 至少明确 event type、金额与
已确认的 `occurred_at`；用户也可以明确授权“按现在记录”。时间未知且用户没有授权使用当前时间时
不得写入不可变 Ledger。BUY / SELL 同样只记录用户确认的已发生交易，不把讨论中的建议变成成交事实。

Pending Mutation 的逻辑信息至少能够表达 `candidate_id`、state / operation、scope、拟议字段、
origin、source turn、status，以及更新已有记录时的目标版本或替代关系；确认后保留 confirmer、
confirmation turn 与时间。`origin=AGENT_PROPOSAL → confirmed_by=USER` 与用户主动声明必须能够区分。
这些是 Contract 草图，不预先决定共用表、具体 Schema 或由框架拥有 Candidate；未确认 Candidate
不得进入后续决策 Context，也不得覆盖有效记录。

Hypothesis / Model Proposal 是作者与可信状态标记，不是混合存储以上五类事实的第六个通用库。
可能原因、候选行动与模型建议先留在本轮 Context / Run 中。用户表达若符合未来获批的 Candidate
Contract，可以由业务服务生成 `PENDING` Candidate 供确认；未经明确确认，不得提升为可用于决策
的有效 Strategy Record 或 Long-term Memory，也不得覆盖已有有效记录。Tool Result 可以作为
对话引用保留，但保留执行记录不等于确认用户事实。

五类状态可复用同一 PostgreSQL 基础设施，但各自有明确的数据模型、服务与读写 / 权限边界。
不能把业务事实、策略和软性背景一并塞进一张自由格式 `memory` 表或向量索引作为真相源。
现行 PROJECT 的“Structured Memory”是历史总称；这里澄清归属，不重定义已有账本含义。

Context Builder 组合各来源后交给 Runtime，而不是先将所有状态转成 Memory：

```text
Portfolio / Ledger ──────┐
Confirmed Strategy ──────┤
Conversation History ────┼→ Context Builder → Agent Runtime → Tools → Evidence-aware Answer
Relevant Long-term Memory┘                       ↑          │
                                                └─结果反馈─┘
```

Framework 可负责 loop、tool execution、history wiring、streaming、usage limits 与状态保存适配；
PositionPilot 负责 portfolio / strategy / memory truth、source / confirmation / staleness semantics。
若采用框架通用 Notebook / Memory 工具，其读写只能触及被明确授权的 Long-term Memory 范围，
不能用 `write_memory` 一类通用能力写 risk budget、exit condition 或 Portfolio 事实。

### 3.2 用实例确定范围与冲突

至少走查以下消息，分别写出“本轮如何用、是否形成候选、是否需要长期确认、会不会改账本”：

1. “我这次最多投 500 美元。”——本次预算；不能覆盖账户 Cash，也不直接成为长期风险预算。
2. “以后每月计划投入 500 美元。”——Strategy Record 候选；不代表未来资金已经入账。
3. “GOOG 是我的长期配置。”——确认其适用范围；不能仅凭聊天自动重分类现有 Lot。
4. “这次我想做短线。”——可能只改变本次意图，不能默认否定全部长期 Thesis。
5. 模型说“可以考虑分批”，用户只回复“嗯”。——这里只表示接受回答，不确认保存；只有 Agent
   随后展示一条明确、当前、唯一的 Pending Mutation 并说明确认后的影响，用户的直接肯定回复才
   能绑定并确认该 Candidate，不按固定关键词列表判断。
6. “忘掉之前那条分批计划。”——通过 Strategy Service 删除 / 失效该记录；明确旧聊天、摘要与存档的处理方式。
7. “其实账户现金只有 500。”——先区分 `current-turn budget = 500`、`cash balance = 500` 与
   `deposit = 500`。本轮预算只更新 Conversation Context；明确的实际入金可在结构化确认后调用
   现有 Cash Event Service，但草案必须包含已确认的金额和发生时间，或取得“按现在记录”的明确
   授权；余额校准不能伪造成 DEPOSIT / WITHDRAWAL。Ask 只能发起已有 Domain Command 支持的维护
   流程，不能覆盖账本、绕过 Domain Service，或在 CashReconciliation 尚未获批时假装已完成校准。
8. “我长期仓最大允许回撤 15%。”——confirmed strategy 候选；明确回撤基准、范围和单位后确认，
   不能让模型替用户决定基准，更不能将规则直接作为已发生回撤的事实。
9. “我最近似乎更偏向回调买入。”——软性 Long-term Memory 候选；不是已确认的价格阈值或交易规则。

分别绘制 Strategy State 与 Long-term Memory 生命周期，不能只设计一个共同的 Memory CRUD：

- **Strategy：** 提取结构化草案 → 可选持久化为 `PENDING` Candidate → 校验字段 / 口径 → 用户明确
  确认 → 版本化有效业务记录；更新绑定原记录与确认来源，旧版本被替代、失效或删除后不作为
  有效策略读取。模型可提议变更，但 Candidate 存储、确认与有效记录写入都由 PositionPilot 的
  业务服务处理。Agent 提案经用户采用后保留 `AGENT_PROPOSAL → USER_CONFIRMATION` 来源链，不能
  改写成用户最初主动声明，也不能从确认的一条 accumulation plan 扩张出 risk budget、期限或
  exit condition。
- **Long-term Memory：** 软性背景候选 → 可选持久化为 `PENDING` → 用户确认 → 有效记忆；支持
  修订、删除、冲突与过期。不能从行为频率直接推断成已确认偏好，不能通过 Memory 更新间接改
  Strategy；未确认 Candidate 只用于确认流程，不进入后续决策 Context。
- **Conversation / Runtime：** 分别定义 Thread 与单次 Run 的生命周期；重启恢复的执行
  Checkpoint 不自动成为用户长期记忆，原始消息不自动等于当前有效策略。

`CashReconciliation` 只记录为独立 Domain Open Question，不纳入 Phase 2 或 4B 的实现范围。
后续提案必须单独决定它表达 target balance 还是 adjustment delta、对 cash flow / 收益口径的影响、
Replay 顺序以及 correction / invalidation 语义，并按核心金融计算与 Domain Model 变化进入 Human
Review。没有该获批能力时，Agent 不得为了匹配用户声称的当前余额而伪造 DEPOSIT / WITHDRAWAL。

Strategy 示例至少覆盖来源消息、确认者 / 时间、对象 / Position Type、类型化值 / 单位、
版本、有效范围与替代关系；Long-term Memory 示例独立覆盖内容、来源、确认、适用范围与有效性。
先用总计 3～5 条示例记录检验两类模型；不强制共用表，也不预设新增数据库。

“用户确认过长期看好”只证明用户表达过该观点，不证明该观点对应的公司事实为真。记忆中的
旧行情或旧财报结论不能作为当前事实；需要重新查询时由 Agent 使用工具取得新证据。

### 3.3 读取与上下文组织

在提案中选择并说明：

- 哪些 Domain / Strategy / Conversation Context 随请求提供，哪些 Long-term Memory 按需
  检索；Context Builder 保留来源类型，避免把全部历史永久塞进 Prompt。
- Strategy 优先通过业务字段、适用范围、有效版本筛选；Long-term Memory 再依据实际规模与
  非结构化检索失败选择检索方式。向量检索不能取代 Strategy 的确定性有效性校验。
- 每条 Context 带来源、时间、范围和状态；先按身份 / 有效性过滤，再选相关内容，不让模型自行
  决定能否访问其他用户的数据。
- 历史摘要不能升级未确认建议，也不能丢失预算纠正与未知项；Strategy / Memory 更新或删除后，
  摘要、旧聊天引用及 Runtime 重放都不能复活失效记录，需明确重新组装 Context 的方式。
- AQ12 的恢复由系统负责：能读历史时恢复原结论，无法读时直接基于当前数据重新评估，
  不要求用户再输入系统自己丢失的内容。AQ16 的模型建议始终保留非事实身份；
  Agent 可重新展示 Draft，但只有对当前唯一 Pending Mutation 的确认才允许 Service 写入。
- 重开对话、刷新页面、退出登录、主动删除对话各是什么生命周期；是否保留及保留多久由提案明确。
- 旧 Strategy / Memory 与新意图的冲突不使用统一“最新消息覆盖全部”：按字段、范围、权威来源
  与确认状态处理；本轮意图不自动改持仓分类或持久策略。

**产物：** 五类状态归属表、分开的 Strategy / Memory 示例与生命周期、Context Builder 读取策略、
Runtime State 边界、冲突走查结果、必要 API / Schema 变化草图。
此时不执行 Migration，不增加第二份 Portfolio State。

## 4. P2-T2 — Answer Contract 的调整提案

将现有约束逐项分为“保留”“收窄 / 修改候选”“所需新能力”，关联代码位置与案例：

| 边界 | 提案应明确的处理 |
|---|---|
| 确定性金融事实 | 保留代码计算与真实来源；新情景计算需要明确输入、口径与计算工具 |
| 当前事实与一般知识 | 当前事实须新数据；一般金融概念可否用于解释、怎样避免冒充当前证据要明确 |
| UNKNOWN | 缺失项限制对应结论；可解决且对结论重要时先研究，否则保持 UNKNOWN 并完成已知部分的条件分析 |
| 投资观点与策略 | 允许有依据的条件分析、候选方案；不能把建议写成既定规则或承诺收益 |
| 新闻归因 | 区分来源报道、支持程度、其他解释；不要求证明唯一因果才能提供任何解释 |
| 本轮预算 | 区分账本现金、用户声明预算与假设；明确纠正、冲突及预算超出现金时的行为 |
| 成交与讨论 | 不知道券商权限不等于不能讨论投资理由；不得宣称订单一定可执行 |
| 对外表达 | 回答直接围绕问题，不机械复述内部状态字段；不强制固定标题或统一模板 |

特别检查 [PROJECT.md](../../PROJECT.md) 的 Fractional Shares 规则：若希望在权限未知时展示
假设股数或资金情景，必须把拟议口径、与现行规则的差异单独交 Human Review；不能以“改善回答”
为由默认支持碎股、默认只支持整股或让 LLM 计算可买数量。没有批准新口径前保留现行边界。
账户 / 券商已确认状态是执行能力的最高权威，其次是 Broker / Asset Metadata 等官方
规则，再次是一般网页；模型训练知识不能充当当前账户执行事实。当碎股或订单权限
仍为 UNKNOWN 时，可输出明确标记的整股 / 碎股条件分支，但不得给出确定可执行数量、
执行限制或“提高预算”等行动结论。

澄清规则建议按信息来源区分：公开信息主动查；可计算事实交给代码；只有用户知道且会显著改变
分析的条件才追问。可作低风险、可修正的解释假设时，应明确假设并先完成可支持的分析。
不为“是否需要查行情”反复请求用户确认，也不为回避关键歧义擅自替用户确认长期策略。

写出三份依据固定 Fixture 的“期望回答示例 + 注释”：下跌原因、500 美元加仓、用户纠正后追问。
示例标为合成、未执行，只解释事实 / 推断 / 未知分别来自哪里，不能伪造真实新闻或要求模型逐字复现。

**产物：** 新旧约定差异表、三个回答示例、保留的硬边界与需要 Human Decision 的语义变化。

## 5. P2-T3 — Research 与自主执行的最小设计

先描述行为，再决定框架：

```text
已授权的用户问题 + 相关 Context
→ 模型选择所需工具 / 澄清 / 回答
→ Application 验证与执行所选工具，返回结果和来源
→ 模型根据新结果继续选择或结束
```

循环不预写题型路径。需要明确的执行语义包括：预算用尽、用户取消、工具正常空结果、Provider
失败、无新证据的重复查询、Final Response 与部分有效结果。用少量有依据的调用 / 耗时上限，
具体值依据阶段一延迟及阶段三 Spike 决定；不增加假设场景的无限 Retry / Fallback。

为 Dedicated Quote / Asset / News / Financial Data 与开放 Search / Page Read 制作来源分工表：

- 账本事实只能来自 Structured State；当前报价与指标优先来自专用、口径明确的数据工具。
- 搜索发现候选页面，必要时读原始公告或报道。新闻相关性、发布日期、事件发生日、行情时段
  分别处理；搜索排名与多个转载不自动等于可信或独立佐证。
- 首次结果无关时可改查询；足够证据已经支持回答时可停止。报价本身不能证明下跌原因。
- 来源元数据至少能表达 URL / 来源名称、获取时间、可得的发布时间 / 事件时间、内容范围与状态。
  哪些主张需要就近引用、引文是否真正支持主张，不能只靠合法 source_refs 判定。
- 明确冲突时如何回查原文，何时保留未解冲突；日期缺失、文章只取得摘要时不能假装读过全文。
- 明确访问域 / URL 边界、正文获取限制、外部文本作为不可信数据的方式、敏感用户信息是否进入
  搜索查询。网页不能修改指令、Strategy State、Long-term Memory、账本或触发额外权限。
- 正常无结果、Provider Failure、受限页面与预算耗尽各自如何表达；已取得的有效事实仍可利用。

Framework、Model / Provider、Research Provider、Memory / Persistence 分开评分。Framework 不决定数据权威；选择
Search 或 Financial Provider 要依据覆盖、时效、引用能力、接口兼容性、失败、延迟与费用。
阶段三可先用固定 Fake Search 结果验证循环，再以获批方式验证候选真实 Provider。

Research Sufficiency 只评价当次 Runtime 实际提供且允许使用的 Search / Page Fetch /
Research Loop 是否被充分使用。缺失能力本身只进 Capability Coverage，不单独扣 RS；
AQ03 的 Quote 已足以否定错误前提。AQ01 的失败是把未核验前提当真，不是“没有调用
不存在的 Search”。

Tool Management 先定义必要的注册、输入输出、执行、来源与预算职责；复用现有 Service。
MCP 仅在候选服务确有接入价值时评估，Skills 仅在案例证明需要可复用分析方法时评估。
安装开发环境插件不代表 PositionPilot Runtime 已获得对应工具。

首轮 Runtime 正式候选仅 Current Runtime 与 Pydantic AI；只有明确缺口才追加 LangChain
`create_agent`。LangGraph 仅由 durable execution / interrupt-resume / 复杂 HITL / 显式状态图
需求触发；smolagents 仅技术参考，不进入首轮正式选型。框架内置功能仍须验证实际版本、模型
兼容性与接入边界，不能因为文档列出 Memory / Search 就自动采用其默认存储或 Provider。

**产物：** 执行与来源规则、Provider 待选清单、关键 Failure 语义、四类独立 Spike 验收表。

## 6. P2-T4 — 最小交付范围与实验设计

为阶段三、四分别填写可评审范围：

| 项目 | 最小范围候选 | 本轮明确不做 / 恢复条件 |
|---|---|---|
| Agent | Single Agent、多轮工具、必要的执行事件 | 不因 ReAct 自动引入 Multi-Agent；按持续路由失败再评估 |
| Conversation | 连续消息、本轮预算、话题与纠正 | 不先建无限历史或复杂摘要体系；按实际 Context 长度问题扩展 |
| Strategy State | 4B 交付少量已确认、版本化策略的读取 / 更新与纠正 / 失效 | 业务服务拥有写入；核心正确性不推迟到阶段五 |
| Long-term Memory | 阶段五按真实需要管理软性长期背景 | 不作为 4A / 4B 前置条件；没有独立需求可暂缓 |
| Research | 一个获批搜索边界及必要页面读取，复用现有金融工具 | 不预设通用浏览器、全市场数据平台或全部 Financial Providers |
| 产品体验 | Answer、来源、必要研究进度及确认入口 | 不展示模型隐式思维链；展示动作、证据与结论调整 |
| Mutation / Confirmation | Phase 2 定义 Confirmed Mutation Contract；4B 实现并验证 Strategy 路径 | 不在 Phase 2 实现通用写入平台或 CashReconciliation |

表格是候选切片，最后范围必须回指阶段一最重要的案例。对 Strategy 的确认与版本、Long-term
Memory 候选确认、API 的 Thread 身份、Session Ownership、存储、清理 / 删除与日志分别提出
方案；4B 所需策略管理不能以“阶段五再做”遗漏边界。
拟变更公开 API 时提供请求 / 响应示例和调用方影响；批准前不直接修改现行 Contract。

### 6.1 阶段四的两个 Checkpoint

不新增阶段编号，阶段四内部按以下顺序交付：

| Checkpoint | 开启的能力 | 评测及进入下一步的证据 |
|---|---|---|
| 4A — Ask Runtime / Research Loop | Conversation History、本轮 budget / context、Open Search + Page Fetch、多轮 Tool Loop | 固定 Eval 核验研究、指代、预算、部分失败与回答修正；记录未启用持久 Strategy / Long-term Memory |
| 4B — Minimum Persistent Strategy | confirmed strategy read / update、绑定唯一 Pending Mutation 的确认、来源 / 版本、correction / invalidation、cross-session retrieval | 连续 Ask Eval 与跨 Session 对照，确认状态持久化、确认范围不膨胀、纠正后新回答改变、旧策略不复活 |

4A 完成固定评测并通过其范围内的 Critical Failure Gate 后再启用 4B。4B 对照固定 4A 的模型、
Research Provider、市场 Fixture 与 Answer 约定，只新增必要 Strategy 接线 / Context 并记录差异。
不在同一对照中偷偷换模型、改搜索 Provider 或开启软性 Long-term Memory。

两个 Checkpoint 后执行完整链：“为什么跌 → 是否加仓 → 我还有 500 美元 → 我主要是长期仓
→ 如果跌到 XXX 呢 → 再分析”。用 Fixture 明确 XXX 为假设情景，必要计算仍由代码完成；
观察 market research、portfolio awareness、指代解析、budget / strategy awareness、条件推断与
answer revision。链内说“长期仓”不自动写策略；另有明确确认步骤才验证 4B 写入。关联 AQ01、
AQ05、AQ09～AQ11、AQ13～AQ16，整链按 Session 记录；不修改阶段一原有案例分母。

### 6.2 四类选型分别评分

使用四张评分表，各项可用 0（不满足）、1（有缺口）、2（满足）并附证据；它们不与 Answer
Rubric 混算。未测项写 NOT_MEASURED，不给默认分；权重及必须通过项在候选结果产生前冻结。

| 选型维度 | 固定其他变量 | 独立评分内容 |
|---|---|---|
| Agent Runtime | 同模型 / Provider、等价工具与结果、五类 State 输入、Prompt、预算 | 连续工具调用、停止、错误、history wiring、streaming / usage limits（按已定需求）、Trace 与维护 / 接入成本 |
| Model / Model Provider | 同 Runtime、Context / Strategy / Memory、工具、输出约定和预算 | 研究与推断质量、工具选择、结构化输出、纠正能力、接口兼容性、延迟 / Token 费用；Model 与 Provider 各自标识 |
| Research Provider | 同任务集、时间窗口、查询 / 读取脚本和来源规则 | News / Market / Search / Fetch 各自的覆盖、相关性、时效、原文 / 引用、失败、延迟与费用 |
| Memory / Persistence | 同状态记录、业务服务、确认 / 版本 / 删除与检索脚本 | PositionPilot-owned DB 及可选框架适配器的隔离、正确读写、有效性、可追溯性与接入成本；五类状态不混存为通用事实 |

Research Provider 真实结果有时变性，记录运行时间、返回内容及独立观察，再用固定 Evidence
Fixtures 比较 Agent / Model。框架配套功能若同时改变 Provider 或存储，另列为组合实验；
不能写成“Pydantic AI 效果最好”来替代对实际组合中各因素的评估。

在四张选型表之外设计能力增量与端到端实验，避免因多个变量一起变而误归因：

1. **能力增量实验：** 固定模型，在单独记录的条件下调整回答约定、增加对话 / Strategy / Long-term Memory、增加多轮研究；
   区分哪个变化改善哪个 Case。允许测有意义的组合，不必穷举全排列。
2. **框架实验：** 现有实现与候选采用等价的多轮能力、Prompt、Tool、各类 State / Context 与预算；比较运行
   正确性、接入成本与可观测性。旧一轮系统只能作为产品基线，不能假装与多轮框架公平对比。
3. **模型实验：** 冻结已选择的同一能力与约定后比较候选模型；记录 Provider 参数与实际可用
   功能差异。真实 Web 的时变结果不作为唯一排名依据。

所有正式回答质量比较只纳入当次候选真实运行路径下 scope=FULL 且 execution_status=COMPLETED
的执行；原先因缺少能力而属于 scope=DIAGNOSTIC 的场景，只有新能力确实通过被测路径提供后才
转为 FULL。DIAGNOSTIC 的适用维度仍保留局部评分和证据，但不形成完整 Case 总分。诊断结果、
请求失败与整个目标集能力覆盖分别报告，不能混入完整场景质量或从覆盖分母删除。

执行前填入验收阈值草案并经 Human Review 冻结：

- **Critical Failure Gate：** 任一虚构来源、错误 Portfolio / cash / budget、未经用户确认将
  Strategy / Long-term Memory 提升为有效状态、覆盖已有有效记录或把未确认记录用于后续决策，
  失效 / 已删除策略当作有效记录重用，或其他关键事实 / 权限错误，都使该次 Case FAIL，不被
  其他 Rubric 分数或重复成功抵消。按获批 Candidate Contract 生成且保持 `PENDING`、不参与决策
  的 Candidate 本身不触发 Gate。基线记录错误不阻止完成证据采集；实现验收需修复并重测。
- 质量：主要维度需达到的绝对锚点、相对基线改善、关键案例最低分、可接受的重复波动。
- 覆盖：必须支持的案例 / 多轮脚本，仍不支持项及原因；不能仅报告可运行子集均分。
- 体验：可接受的典型与较慢请求时间、调用 / Token / 外部费用预算，UNKNOWN 用量的处理。
- 回归：需要保留的 Portfolio-only、Position Type、确定性事实与 Provider Failure 行为。

提案中的报告首页固定采用能力覆盖率、完整场景回答质量、请求成功率与 Critical Failure 次数；
各项写清分母与 NOT_RUN / NOT_EVALUATED 数量，不用跨维度单一平均分替代。

不要等候选结果出来后再挑阈值；若基线不足以给出具体数字，在提案中列明需由 Spike 补齐的
测量项和冻结时点。该项未解决前不声称发布验收通过。

## 7. P2-T5 — 形成 Decision Proposal 与评审包

建议执行时生成 `docs/plans/ask-quality-decision-proposal.md`，以如下结构组织：

1. **Problem / Evidence：** 最重要的 3～5 个 Failure、基线 Run / Case、用户影响。
2. **Proposed Behavior：** 最小闭环、回答示例、信息不足时如何继续或澄清。
3. **State / Context / Source Contract：** 五类状态分别归属，Strategy 与 Memory 的确认 / 版本 /
   读写 / 失效，Conversation 与 Runtime 生命周期，Research 来源语义。
4. **Options / Recommendation：** 各选项解决的已知问题、Trade-off、推荐与暂不实现项。
5. **Impact：** 与现行 PROJECT / API / Domain / Security / Architecture 的差异及所需 Migration。
6. **Spike Plan：** 收窄的 Runtime 候选、四张独立选型评分表、等价输入、允许验证的范围；4A / 4B 检查点。
7. **Acceptance：** 固定案例、scope=FULL / DIAGNOSTIC 与 execution_status 的正交统计口径、
   DIAGNOSTIC 局部评分、四组报告首页指标、评分阈值、硬错误、重复次数、耗时 / 成本与真实使用
   验证方式。
8. **Decision Log：** 每项 ACCEPTED / REJECTED / DEFERRED / NEEDS_SPIKE、日期、理由与负责人。

本次方向性批准已覆盖状态分离、收窄候选、四类选型分评、4A / 4B 与 Critical Failure Gate。
后续提交 Domain / Strategy / Conversation / Long-term Memory / Runtime / Research / Answer 的
具体方案与待定项，不重复询问是否接受已批准方向，也不要求用户逐 Task 批准普通实现。
框架 / Provider 可以保留 NEEDS_SPIKE；批准候选实验不代表批准生产选型。阶段三得到证据后，
只提交尚未决定或实质变化的选型，不重做已批准的 Milestone 级规划。

评审前，由开发方用 AQ01、AQ03、AQ05、AQ06、AQ07、AQ12、AQ16、AQ17a、AQ17b、
AQ18、AQ19 做纸面走查：逐轮列出可用能力、事实状态、Scope、Gate、有效 Strategy /
Memory、预期输出性质、允许的状态变化与回归断言。可以验证设计覆盖，
但这不是模型行为测试，不计入通过率。检查新提案是否误伤原有正确行为。

按照 [AGENTS.md 第 4 节](../../AGENTS.md#4-human-review-gate)，变更核心框架 / Provider、
主要 Agent / Memory 架构、公开 API 或敏感数据处理方式需 Human Review。本文仅指导准备
具体方案，不要求为了写文档再请求批准，也不自动授权这些生产变更。

获批后按最终选择整理 ADR 与正式实施计划；确有产品语义变化时同步 PROJECT，实际架构落地
后更新 ARCHITECTURE。框架、Provider 或基础设施未选定时保持“未决定”。

## 8. 完成清单与交付记录

- [x] P2-T0：每个最小行为对应基线 Case / Failure，范围不依赖猜测。
- [x] P2-T1：五类状态分别归属，Strategy / Memory 分开建模、确认 / 版本 / 纠正 / 删除、读取与生命周期明确。
- [x] P2-T2：回答约定新旧差异、保留边界、三个合成回答示例完成。
- [x] P2-T3：Research Source Policy、执行 / Failure 语义、收窄候选与四类 Spike 验收表完成。
- [x] P2-T4：四类独立评分、4A / 4B 检查点、场景执行范围、等价实验、Candidate 安全边界、
      Critical Failure Gate、验收阈值与待测量项明确。
- [ ] P2-T5：案例走查、文档一致性检查与 Automated Review 已完成；
      等待用户审阅具体提案。

### 已确认设计原则（2026-09-14）

- **ACCEPTED：** Confirmed Mutation Boundary；Ask 可以生成变更草案和发起确认，但只有对应业务
  服务成功提交后才能声明生效。
- **ACCEPTED：** Confirmation 绑定明确、当前、唯一的 Pending Mutation，不绑定固定肯定词；授权
  仅覆盖已展示的 operation、scope 与字段。
- **ACCEPTED：** Conversation-only、Persistent semantic、Financial fact mutation 使用不同生效
  门槛；Agent Proposal 经用户确认后必须保留来源链。
- **DEFERRED / OPEN DOMAIN DECISION：** CashReconciliation 不纳入 Phase 2 实现；不得用虚构 Cash
  Event 代替，恢复时单独确定 Ledger / Accounting 语义并进入所需 Human Review。

提案位置：[Phase 2 Decision Proposal](ask-quality-decision-proposal.md)。Automated Review 日期：
**2026-09-15**；原始 P1 发现已修正。Human Review 日期与结果：**待填写**。
只有明确的决策与允许的后续范围已记录，才将阶段二标为完成；待选型项可以进入阶段三，
但不能在没有选型证据与所需批准时进入生产替换。
