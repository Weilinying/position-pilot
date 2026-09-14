# Ask Quality / Memory / Open Web Research — Discovery 执行路线

## 1. 状态与职责

**Status:** DISCOVERY — DIRECTION APPROVED（2026-09-13）；各阶段尚未执行，不绑定 Milestone 或 Release。

**记录日期：** 2026-09-13。Human Review 已批准 M13 后的 Discovery 方向，并要求区分五类状态、
收窄框架候选、独立评价四类选型及在阶段四设置 4A / 4B 检查点；本版落实这些意见。
方向性批准不等于 Framework / Provider 已选型、具体数据模型 / 公共 API 已批准或评测已执行。

本文件是 Discovery 的工作安排，不是新的 Milestone 实施承诺。产品现行语义以
[PROJECT.md](../../PROJECT.md) 为准；发布范围以 [ROADMAP.md](../../ROADMAP.md) 为准；
已有问题与取舍见 [Discovery Engineering Note](../engineering-notes/post-v1-answer-quality-discovery.md)。

## 2. 目标与当前证据

目标是让 Ask 能主动补充公开信息，结合当前意图与相关记忆进行条件式分析，并在新证据或用户
纠正出现后调整回答。用户可以看到使用了哪些来源、哪些结论发生变化及其依据。
自主性不以工具调用多、回答长或固定输出“思考过程”来衡量，也不表示模型自行更新权重。

2026-09-13 的代码审阅确认：

- [InvestmentAgent](../../backend/position_pilot/application/investment_agent.py) 只有 Quote、
  Recent Price History、Recent News、SPY Market Context 四类工具；每次最多一轮、四次调用，
  工具返回后必须生成 Final Response，无法根据结果继续检索。
- [Investment Context](../../backend/position_pilot/application/investment_context.py) 每次将
  trading plan、exit conditions、risk budget 固定为 UNKNOWN；没有独立的本轮投入预算。
- [InvestmentQuestionRequest](../../backend/position_pilot/main.py) 只有当前 question，
  当前请求没有对话历史、持久策略状态或 Long-term Memory 入口。
- 现有评测擅长验证工具与来源约定；其通过不证明开放研究、连续对话和回答实用性达标。
- 用户报告“为什么谷歌今天跌了”和“我还有 500 美元，可以加仓吗”的回答僵硬；这是历史使用
  反馈，不是本次已重跑的实验，不能据此确定运行时模型或当日市场事实。

保留账本、确定性计算、Position Type、来源与失败语义；审视将局部 UNKNOWN 扩大成整段拒答
的回答约定。修正 Prompt、补足能力、选择框架与更换模型应分别提供证据。

## 3. 整体顺序

| 阶段 | 工作与产物 | 评测时点 / 完成判断 |
|---|---|---|
| 1 — 当前基线 | 约 20 个固定案例、冻结输入与运行配置、当前回答记录、评分及 Failure Map | 首先测当前版本；记录不支持和未运行，不为基线修改 Production 行为 |
| 2 — 最小设计 | Domain State / Strategy State / Conversation Context / Long-term Memory / Agent Runtime / Research / Answer 边界、最小闭环与 Decision Proposal | 用案例走查；Human Review 确认具体实施边界与待验证项 |
| 3 — Framework / Capability Spike | Current Runtime 与 Pydantic AI 正式对照；Runtime、Model / Provider、Research Provider、Memory / Persistence 四类独立评分 | 固定非目标变量，验证循环与兼容性；按各自证据选型，批准后记录 ADR |
| 4 — 第一个完整 Ask 闭环 | 4A：对话、本轮预算、Search / Fetch、多轮循环；4B：已确认 Strategy 的持久读取 / 更新、纠正 / 失效与跨会话检索 | 4A 后固定 Eval，4B 后连续 Ask Eval，最后验证完整讨论链 |
| 5 — Long-term Memory 完善 | 对确有检索需求的非固定字段长期背景，完善候选、确认、编辑删除、冲突、过期与检索 | 不混入 Strategy / Ledger；没有独立需求可暂缓，已上线状态的正确性不得延期 |
| 6 — 优化与验收 | 按失败补数据 / 调 Prompt、必要的模型对比、来源与进度体验、验收报告 | 相关检查与 Automated Review 后完成固定评测和 Human Acceptance；再落实发布 |

阶段一、二详见：

- [阶段一：基线与评测执行计划](ask-quality-phase-1-baseline.md)
- [阶段二：最小设计与 Decision Proposal 执行计划](ask-quality-phase-2-design.md)

阶段二先明确五类状态。阶段四仍是一个阶段，内部顺序固定为 4A → 固定 Eval → 4B → 连续 Ask Eval：

- **4A — Ask Runtime / Research Loop：** Conversation History、current-turn budget / context、
  Open Search + Page Fetch、多轮 Tool Loop；不同时启用持久 Strategy 或软性 Long-term Memory。
- **4B — Minimum Persistent Strategy：** 结构化 confirmed strategy read / update、版本与来源、
  correction / invalidation、跨 Session 读取；确认、纠正和停止使用旧策略不能推迟到阶段五。
- **最后整体验证：** “为什么跌 → 是否加仓 → 我还有 500 美元 → 我主要是长期仓 → 如果跌到
  XXX 呢 → 再分析”。将这条脚本映射到既有案例和各轮能力，不当成六个互不相关的单问。

4A → 4B 的固定比较保持模型、Research Provider、Prompt / Answer 约定与市场 Fixture 不变，
只增加 Strategy 能力及其必要 Context；必要接口接线差异单独记录，不混入其他调优。
阶段五只解决独立的非结构化长期背景需求；Strategy State 的核心正确性已经在 4B 闭环。

阶段三验证没有结论时可以回到阶段二调整提案；阶段四暴露新失败时可补充案例，保持旧基线
可追溯。不为了严格按编号推进而跳过证据，也不每个 Task 重做方向规划。

## 4. 状态归属与框架边界

**Architecture Principle：Memory 不是所有过去信息的统称；Framework 不拥有业务语义。**

| 类型 | 示例 | 归属与处理 |
|---|---|---|
| Domain State | Portfolio、cash、transaction、batch / lot、Position Type | 现有确定性数据库 / Ledger，是业务事实，不进入 Memory 读写体系 |
| User Strategy State | Thesis、LONG_TERM / SWING 目标、risk budget、exit condition、计划投入 | PositionPilot 拥有的结构化、可确认、可版本化业务记录；不由 LLM 自由写入通用 Memory |
| Conversation State / Context | “刚才的 GOOG”“这次预算 500”、逐轮澄清 | Application 管理 Thread / Message History 与短期上下文 |
| Long-term Memory | 反复出现但不适合固定字段的长期偏好 / 背景 | 独立候选与确认、来源、失效及按需 Retrieval；不能替代 Strategy State |
| Agent Execution State | 单次 Run 的 tool call、observation、next action | Runtime 内部运行状态；即使有 Checkpoint 也不成为产品长期记忆或业务事实 |

“长期仓最大允许回撤 15%”属于待确认的 Strategy Record，需定义回撤基准与适用范围；
“最近似乎更偏向回调买入”可形成 Long-term Memory 候选。不得将两者及账本一并写入通用
`memory` 表或向量库。模型提案 / 假设保留作者与未确认身份，不能自动提升到任一已确认记录。

现行 PROJECT 使用过“Structured Memory”这一历史总称；本 Discovery 将其业务内容明确称为
Domain State，不改变原有 Ledger Source of Truth，也不代表当前运行代码已经具备新分类。

Context Builder 按各自边界组合 Portfolio / Ledger、Confirmed Strategy、Conversation History
与相关 Long-term Memory，再提供给 Agent Runtime；不让全部输入先流经一个通用 Memory 系统。
Runtime 管理 loop、tool execution、history wiring、streaming 与 usage limits；PositionPilot
管理 portfolio truth、strategy truth、memory truth、source、confirmation 与 staleness semantics。

## 5. 框架候选与四类选型

ReAct 指“根据当前上下文选择行动 → 执行工具 → 利用观察结果继续判断”的工作模式，
不指定软件依赖。程序管理执行边界，模型选择问题所需路径，不按题型预写完整分析顺序。

首轮正式 Runtime 比较限定为 **Current Runtime vs Pydantic AI**。只有记录到明确能力缺口，
才追加 LangChain `create_agent`；只有 durable execution、interrupt-resume、复杂 HITL 或
显式状态图需求出现时才评估 LangGraph。smolagents 仅作技术参考，不进入首轮正式 Benchmark。
这不是已选型或质量排名；阶段三开始时核验官方文档、实际版本与接口兼容性。

阶段三使用四张独立评分表，每张记录固定项、变化项、能力 / 正确性、成本与证据：

| 选型维度 | 评价对象与边界 |
|---|---|
| Agent Runtime | Current Runtime / Pydantic AI；评 loop、tool execution、history wiring、streaming、usage limits 与接入成本 |
| Model / Model Provider | 在同 Runtime、工具、Context、Answer 约定下评模型行为及 Provider 兼容性，不预选新模型 |
| Research Provider | 现有 News / Market + 候选 Open Search / Page Fetch；评覆盖、时效、来源、失败、延迟和费用 |
| Memory / Persistence | PositionPilot-owned DB + 可选框架适配器；分别评 Strategy、Conversation、Long-term Memory 与 Run State 的存取，确认业务规则未交给框架 |

组合的端到端质量单独报告，不能因某个 Runtime + 模型 + Search 组合得分高就把增益全归给
Runtime。Framework 自带 Web / Memory 能力若使用，同样登记 Provider、存储与业务边界，不绕过
独立选型。具体评分项与控制变量在阶段二冻结，执行指导见阶段二 P2-T4。

Framework 的通用 Memory / Notebook 读写不能成为 Portfolio、risk budget、exit condition 的
Source of Truth。MCP 是可能的外部接入协议，Skill 是可能的分析方法载体，二者均不自动提供当前金融事实。
优先复用现有 Provider 与 Service，不预建插件平台或自研通用 Agent Framework。

候选参考入口（执行 Spike 时重新核实）：

- [ReAct 原论文介绍](https://react-lm.github.io/)
- [Pydantic AI Agents](https://ai.pydantic.dev/agents/)
- [LangChain Agents](https://docs.langchain.com/oss/python/langchain/agents)
- [smolagents 多步 Agent](https://huggingface.co/docs/smolagents/v1.26.0/conceptual_guides/react)
- [LangGraph 概览](https://docs.langchain.com/oss/python/langgraph/overview)

## 6. 贯穿全程的评测方式

| 层次 | 输入与运行方式 | 用途与边界 |
|---|---|---|
| 确定性测试 | Fake Model + 固定数据；修改相关实现后运行 | 分别验证账本、策略版本、记忆生命周期、工具参数 / 失败、来源绑定；不证明模型行为 |
| 固定行为评测 | Real Model + 分开的 Domain / Strategy / Conversation / Memory / Tool Fixtures | 比较补信息、上下文使用、条件分析与纠正；基线、4A、4B 及阶段验收运行 |
| 真实使用验证 | Real Model + Real Providers；阶段四起覆盖连续问答 | 验证来源覆盖、时效、相关性、体验和延迟；外部数据变化不混入固定模型排名 |

沿用 pytest 和 [现有 Evaluation](../evaluation/README.md)，不为此次 Discovery 引入新的
评测平台。先用带锚点的人工 0～2 分评分；LLM Judge 若未来有价值，也必须先与人工校准，不能
代替事实核查。用户在阶段节点盲看少量 A/B 回答；工程检查、结果整理与差异分析由开发方承担。

**Critical Failure Gate：** 虚构来源、错误 Portfolio / cash / budget、未经用户确认将 Strategy /
Long-term Memory 提升为有效状态、覆盖已有有效记录或把未确认记录用于后续决策，继续把 stale /
deleted Strategy 当成有效策略，以及其他关键事实 / 权限错误，任一发生则该次 Case FAIL。
按已批准规则生成但保持 `PENDING`、不参与决策的 Candidate 本身不触发 Gate。Rubric 分数只保留
用于诊断，不能被平均值或另外两次成功抵消。报告以 scenario_execution_scope 的 FULL /
DIAGNOSTIC 表示场景能否完整测试，以 execution_status 的 COMPLETED / REQUEST_FAILED / NOT_RUN
表示实际执行结果；Critical Gate 无证据时记 NOT_EVALUATED。DIAGNOSTIC 保留适用维度的局部评分，
但不与完整场景质量混算。详细评分与统计见阶段一 P1-T2 / P1-T3。
研究深度以必要证据和任务完成衡量，不把唯一工具路径、固定措辞或工具调用次数多当作质量标准。

正式报告首页展示能力覆盖率、完整场景回答质量、请求成功率和 Critical Failure 次数，不用单一
平均分概括系统质量。开发时只运行受影响测试与案例；阶段验收再跑约定的完整 Ask 集。关键重复集
在阶段一根据实际 Runtime 能力冻结，优先选择五个 `scope=FULL` 执行变体各重复三次；确定性的
capability gap 不靠重复采样证明。报告波动而不只展示最好结果。阶段二在看候选结果前冻结验收
阈值与可接受延迟 / 成本。

模型正式对比需固定各类 State / Context、Tools、Prompt、输出约定、Fixtures 与运行预算。旧版一轮调用与
新版多轮 Agent 的比较是系统改进实验，不能归因于框架或模型单一因素。

## 7. 当前下一步与记录规则

下一次进入执行时，从阶段一的 P1-T0 开始，先核验 Repository 状态与评测入口；本次没有运行
基线、进行选型、新增依赖或修改 Production。阶段二可先整理待决策清单，最终方案须引用基线证据。

执行时逐项填写阶段计划中的状态与产物位置；未运行的检查、缺失的成本数据、未获批的决策
明确保留为未完成。不要在报告中回填虚构结果。

M10、M12 与 V2 保持现有 Roadmap 状态。新的正式 Milestone、实施 Plan、ADR 与 Release Mapping
在所需 Human Review 与 Spike 证据具备后再创建。当前文档任务不创建 Branch 或 Commit。
评审所说的“V2 级别变化”描述潜在架构影响，不等于将本 Discovery 改名 V2、批准 V2 Release，
或启动 Roadmap 中的 Connected Product。方向性评审已通过，后续不重复请求批准同一方向。
