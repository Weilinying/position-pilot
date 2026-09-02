# Post-v1 Answer Quality Discovery Boundary

## Problem

`v1.0.0` 已证明 Structured Portfolio、有限 Market / News Context 与 Single Agent Tool Routing 能形成可追溯闭环，但真实回答仍可能因为缺少用户策略、跨轮上下文和开放外部信息而过度保守。该 Failure 不能可靠归因于单一 Model：当前 Prompt / Response Contract、Context Capability、Memory 缺失和 Tool Coverage 会共同限制回答。

## Decision

Answer Quality、Conversation Memory、Investment Memory 与 Open Web Research 暂作为一个 Discovery Track，不映射到 `v1.1.0` 或其他既定 Release，也不先通过放宽 Prompt、切换 Model、引入 Vector Database 或增加 General Browser 宣称解决。

对 Product Agent 而言，Web Search 本身属于 Tool / Provider Boundary。Agent 只能调用 Application 明确授权、可观测并具有 Failure / Source Contract 的搜索能力；专用 Financial Tools 继续负责 Quote、Asset Metadata、Ledger 与其他高结构化事实，开放搜索负责候选发现和跨来源当前信息，不得绕过来源验证或把网页内容当作指令。

Memory 至少区分 Thread-scoped Conversation Continuity 与跨 Session Investment Memory。用户 Thesis、Holding Horizon、Risk Budget、Accumulation Plan 或 Exit Conditions 若进入长期 Memory，应支持来源追溯、Human Confirmation、编辑 / 删除、冲突和过期语义，不得从一次模型回答自动升级为用户既定策略。

## Alternatives / Trade-off

- 只改 Prompt 成本低，但没有补足策略和外部事实，容易用更自信的语言掩盖同一 Context 缺口。
- 只增加 Web Search 能扩大信息覆盖，但不能解释用户希望长期还是波段、接受多大风险，也会增加来源质量、时效、延迟和 Injection 风险。
- 只增加 Conversation History 能改善追问连续性，但长期对话会带来 stale context、成本和干扰，且不等于用户确认过的 Investment Memory。
- 立即引入通用 Memory Framework、Vector Database 或 Multi-Agent 会扩大架构和 Evaluation 面，当前没有证据证明是最小必要方案。

## Trigger / Future

当固定 Failure Cases、Memory Schema、Web Source Policy、Answer Contract 与 Evaluation Rubric 都足以形成最小 Vertical Slice 时，提交 Human Decision Proposal。批准后再决定 Release、Provider、数据模型和是否需要新 Infrastructure；任何 Model Comparison 必须冻结相同 Memory、Tool、Prompt 与 Evaluation Contract。
