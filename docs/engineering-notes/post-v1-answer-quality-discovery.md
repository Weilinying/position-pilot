# Post-v1 Answer Quality Discovery Boundary

## Problem

`v1.0.0` 已证明 Structured Portfolio、有限 Market / News Context 与 Single Agent Tool Routing 能形成可追溯闭环，但真实回答仍可能因为缺少用户策略、跨轮上下文和开放外部信息而过度保守。该 Failure 不能可靠归因于单一 Model：当前 Prompt / Response Contract、Context Capability、Strategy / Conversation 缺失和 Tool Coverage 会共同限制回答。把所有过去信息统称为 Memory，又会混淆业务事实、用户规则与模型可读写背景。

## Decision

Answer Quality、State / Context 分离与 Open Web Research 作为一个 Discovery Track，不映射到既定 Release。2026-09-13 Human Review 已批准方向及下述原则；具体选型、数据模型和 API 仍待 Spike / Decision Proposal，不通过放宽 Prompt、切换 Model 或增加通用基础设施直接宣称问题解决。

对 Product Agent 而言，Web Search 本身属于 Tool / Provider Boundary。Agent 只能调用 Application 明确授权、可观测并具有 Failure / Source Contract 的搜索能力；专用 Financial Tools 继续负责 Quote、Asset Metadata、Ledger 与其他高结构化事实，开放搜索负责候选发现和跨来源当前信息，不得绕过来源验证或把网页内容当作指令。

Memory 不是所有过去信息的统称，五类状态分别管理：

- **Domain State：** Portfolio、Cash、Transaction、Batch / Lot 属于确定性 Ledger 事实，不进入 Memory 读写体系。
- **User Strategy State：** Thesis、期限、Risk Budget、投入计划与退出条件是结构化、可确认、可版本化的业务记录；不能由 LLM 自由写通用 Memory。
- **Conversation State：** Thread / Message History 与本轮预算、指代和澄清，生命周期由 Application 管理。
- **Long-term Memory：** 不适合固定字段的长期偏好 / 背景，独立处理候选、确认、来源、编辑 / 删除、冲突、过期与 Retrieval。
- **Agent Execution State：** 单次 Run 的 Tool / Observation / Next Action；持久化 Checkpoint 也不成为产品 Memory。

Framework 负责执行与状态保存适配，PositionPilot 拥有 portfolio / strategy / memory truth，以及 source / confirmation / staleness semantics。模型提案不自动升级为已确认策略或记忆。现行 PROJECT 中“Structured Memory”的历史总称不改变这些事实原有的 Ledger 权威来源。

首轮正式 Runtime 比较限 Current Runtime vs Pydantic AI；LangChain 需明确缺口，LangGraph 需持久执行 / 中断恢复 / 复杂 HITL / 显式状态图需求，smolagents 仅技术参考。Runtime、Model / Provider、Research Provider、Memory / Persistence 四类分别评分，不把组合效果误归因于框架。

## Alternatives / Trade-off

- 只改 Prompt 成本低，但没有补足策略和外部事实，容易用更自信的语言掩盖同一 Context 缺口。
- 只增加 Web Search 能扩大信息覆盖，但不能解释用户希望长期还是波段、接受多大风险，也会增加来源质量、时效、延迟和 Injection 风险。
- 只增加 Conversation History 能改善追问连续性，但长期对话会带来 stale context、成本和干扰，且不等于 confirmed Strategy 或有效 Long-term Memory。
- 立即引入通用 Memory Framework、Vector Database 或 Multi-Agent 会扩大架构和 Evaluation 面，当前没有证据证明是最小必要方案。
- 阶段四内部采用 4A 研究 / 对话循环 → 固定 Eval → 4B 最小持久 Strategy → 连续 Ask Eval，可区分增益而不增加顶层阶段；Long-term Memory 根据独立需求在阶段五完善。

## Trigger / Future

当固定 Failure Cases、各类 State / Context Schema、Web Source Policy、Answer Contract 与 Evaluation Rubric 足以形成最小 Vertical Slice 时，提交具体 Human Decision Proposal；不重复提审已批准方向。Model Comparison 冻结同一 Context、Tool、Prompt 与 Evaluation Contract，真实 Provider 验证单独报告。

Critical Failure Gate 将虚构来源、错误 Portfolio / cash / budget、未经确认把 Strategy / Long-term Memory 提升为有效状态、覆盖有效记录或用于后续决策，以及复用失效 / 已删除策略等关键错误判为当次 Case FAIL，不能被平均分或其他重复成功抵消。按获批规则生成但保持 `PENDING`、不参与决策的 Candidate 本身不是关键失败。阶段一以 scope=FULL / DIAGNOSTIC 表示目标场景能否完整测试，以 execution_status 表示实际是否运行成功；DIAGNOSTIC 保留适用维度的局部评分但不进入完整场景质量。报告首页固定展示能力覆盖率、完整场景回答质量、请求成功率与 Critical Failure 次数；后续实现验收修复后重测。

具体顺序与前两阶段指导见 [Discovery 执行路线](../plans/ask-quality-discovery.md)。方向批准及文档修订不表示阶段已执行。“V2 级别”仅描述架构影响，Release Mapping 仍未决定。
