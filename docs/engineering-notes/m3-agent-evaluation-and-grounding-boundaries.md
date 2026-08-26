# M3 Agent Evaluation 与 Grounding 边界 (ADR)

## 一、 问题背景 (Problem)

在 M3 阶段开发中，我们需要验证系统能否将 Portfolio（投资组合结构化状态）、Native Function Calling（原生函数调用）、Current Quote（当前报价）与真实的 LLM 结合，形成一个最小可用的 Stateful Investment Agent。

在开发中，我们发现**确定性的编排测试（Orchestration Test）**、**真实模型行为（Real Model Behavior）**与**系统必须保证的契约（System Contract）**是三个截然不同的问题，不能用同一种测试或同一组 Prompt 规则来一并解决：

*   **Fake LLM 的局限性：** 使用 Fake LLM 能够稳定验证上下文构建、工具校验与执行、错误处理、数据源追踪、轮次限制以及 API 契约；但它**无法证明**真实模型是否会主动选择正确的工具、避免调用无意义工具、正确使用 Portfolio 上下文、区分仓位类型（Position Type），或在数据缺失时保持 Grounded（不脱离事实）。
*   **Prompt 的局限性：** 真实的评估表明，模型可以先在回答中复述“我不得自行判断购买能力”，但随后依然私自利用 Cash（现金）与 Quote（报价）去推导整股的购买能力或生成新的金融数值。**大模型识别了 Prompt 的指令，并不等于系统真正获得了安全保证。**

---

## 二、 架构决策 (Decision)

### 1. 评估机制分层 (Evaluation 分层)
为了解决上述冲突，M3 将 Evaluation 正式划分为以下两层：

*   **Layer 1: Deterministic Agent Tests（确定性 Agent 测试）**
    *   **配置：** Fake LLM + Fake Market Data（假模型 + 假市场数据）
    *   **目的：** 专门用于验证应用层的代码契约（Application Contract）和核心流转逻辑。
*   **Layer 2: Opt-in Real-Model Behavioral Eval（选择性真实模型行为评估）**
    *   **配置：** Real AliyunLLMProvider + Fake Market Data（真模型 + 假市场数据）
    *   **目的：** 在固定的投资组合和行情事实下，观察真实模型的工具选择、事实遵循度（Grounding）和个性化表现。使用假数据是为了避免实时市场行情的波动污染测试结果。
    *   *注：* 真 LLM + 真市场数据 仅保留为少量的集成冒烟测试（Integration Smoke Test），不作为行为评估的主要依据。

### 2. 提示词与系统保证 (Prompt 与 System Guarantee)
*   **职责划分：** Prompt 和结构化的 Context Contract 负责告诉模型“边界在哪”；而真正属于系统不变量（System Invariant）的越界行为，必须由后端确定性的 **Guard（拦截器）**来执行阻断。
*   **拦截与修复机制 (Response Repair)：** 
    *   当触发首次 Guard 拦截时，系统最多向模型发起一次 `tools=()` 的修复请求（不重新执行 Agent 流程或工具选择）。
    *   如果修复后依然越界，直接返回 `LLM_INVALID_PROVIDER_RESPONSE` 错误，绝不允许形成隐式的无限死循环。
*   **高置信度阻断：** 生产环境的 Guard 最终只阻断**代码能够高置信度证明**的违规行为：
    1.  回答中出现了 Context 未提供的明确金融数值。
    2.  回答形成了明确的购买能力或“整股可执行性”结论。
    3.  回答显式复述了结构化的数值关系（如 Cash 与 Quote 的关系，或 Quote 与均价的关系），但与后端派生事实（Derived Fact）完全相反。
    4.  `CURRENT_QUOTE(ticker)` Fact Reference 无法绑定到本轮同 ticker 的成功 Quote Source。Authoritative price 由 Application 解析和渲染，不再由 Guard 从自然语言中识别。

### 3. 拦截器策略收缩 (Guard 收缩)
*   **踩过的坑：** Guard 曾尝试使用复杂的正则表达式（Regex）去检测“略高”、“微利”、“显著”等词汇，以及识别跨 Ticker 的开放式比较，甚至试图从复杂句式中推断操作数。这导致代码层面的 Guard 退化成了一个“自然语言启发式审核器 (Natural-language Heuristic Reviewer)”，并引发了实际的误报（False Positive）。
*   **最终决定：** 彻底删除这些生产环境的阻断规则，以减少无意义的 Repair 修复、额外的 LLM 调用开销、Regex 的复杂度，并消除 Prompt/Guard 之间的重复逻辑。
*   **事实身份演进：** M4 曾尝试用“Ticker + 当前价格关键词 + 明确数值”的 Regex 绑定 Quote Source，但连续暴露 Unicode `\b` 中文边界、全局 `IGNORECASE` 把 `The` 识别为 ticker，以及“当前股价 / current stock price”等同义表达缺口。继续扩词表只会降低 Precision 并产生边际收益递减，因此 Current Quote 已迁移到 Structured Fact Reference；相关自然语言 Regex 已删除。
*   **遗留处理：** 对于“关系幅度词汇、开放式语义比较、回答完整度、投资建议质量、仓位个性化程度、语言风格”等自然语言层面的问题，继续交由 Behavioral Eval（行为评估）或 Human Review（人工审查）去观察，后端代码不再强行介入。

---

## 三、 失败分类处理 (Failure Classification)

当在 Eval 中遇到失败（Failure）时，**不应该默认将其转化为新的 Prompt 或增加新的生产环境代码**。处理前必须先将其归类，判断它属于以下哪一层：
*   Architecture / System Contract（架构/系统契约）
*   Prompt / Tool Description（提示词/工具描述）
*   Context Availability（上下文缺失）
*   Model Behavioral Quality（模型行为质量）
*   Model Selection（模型选型问题）

**核心判断标准：** “如果换成一个行为极好的完美模型，系统是否仍必须强制保证这件事？”
*   如果答案是**“是”**（如：绝不能伪造工具结果、Provider 失败不能伪装成功、API 状态不能由模型瞎定）：属于 **System Contract**，必须用代码阻断。
*   如果答案是**“否”**（如：模型顺手比较了两个报价、LONG_TERM/SWING 的语气差异不够明显）：属于 **Model Behavioral Quality**，不应持续扩大生产环境的 Guard。

---

## 四、 M3 验收时的已知行为限制 (Known Limitations)

在 2026-08-25 最近一次完整的 Real-Model Behavioral Eval 中（使用真实 AliyunLLMProvider 与 Fake Market Data），自动化行为契约测试结果为 **17 / 17 PASS**。其中有 4 个 Case 使用了一次 Guard Repair，未超过 M3 设定的修复上限。

*注意：Automated PASS 仅表示工具链路、状态、最终回答未触发代码阻断，并不代表完全满足人类审查标准（Human Rubric）。*

**M3 阶段当前接受并保留的模型行为瑕疵（Limitations）包括：**
1.  `compare_two_quotes` 仍可能根据两个已知报价，生成未经后端提供的绝对价格比较。
2.  在 LONG_TERM / SWING 分析中，回答仍可能使用“略高”、“微利”等关系幅度措辞。
3.  在相同问题下，LONG_TERM / SWING 虽然能读取正确的 Position Type，但具体的分析差异仍可能偏弱。
4.  某些回答可能没有完整复述非关键的 Snapshot 字段（例如当前的具体 Shares 数量）。
5.  Portfolio 级别的回答，可能没有主动声明人类审查员希望看到的 `UNKNOWN` / `UNAVAILABLE` 字段（例如“当前市值权重不可用”）。

**结论：** 这些限制没有伪造工具结果、没有改变应用状态、没有突破 Provider 故障边界或绕过轮次限制，因此**不作为 M3 System Contract Failure**。它们被保留作为后续 Evaluation、Prompt 演进和模型选型的输入依据。

---

## 五、 权衡与未来触发条件 (Trade-off 与 Future Trigger)

*   **注重精准度 (Precision)：** 收缩后的 Guard 优先保证 Precision，会有意放过那些无法被高置信度解析的自然语言质量问题。
*   **Evaluation 的定位：** M3 Evaluation 的核心作用是暴露模型的行为特征（Behavioral Profile），帮助确认问题应该由哪一层（架构、工具、提示词还是换模型）来解决，**而不是把每一次模型失误都硬修成生产环境的拦截规则。**
*   **未来的触发条件：** 只有当后续的 Evaluation 明确证明某类 Failure 必须跨模型稳定阻断，并且能够通过结构化事实或低误报规则进行可靠验证时，才重新评估是否需要修改 Production Guard。
*   **演进方向：** M4～M6 阶段应当在现有 Case 基础上继续积累证据，而不是去建设一个通用庞大的自然语言审核框架。

## Summary
Eval 遇到 failure 时是看LLM的回答是什么样的问题，如果是模型行为质量相关的问题，那么可以不用在代码/prompt里进行修改，因为这可能能随着模型的更换或者上下文信息量（证据）的增加而改善。核心就是“如果换成一个行为极好的完美模型，系统是否仍必须强制保证这件事？”如果是的话才需要进行修改。因为你永远写不完拦截规则。

## M4 Current Quote Structured Fact Reference

### Problem

Quote Grounding 先后用全局 Decimal allow-list 和 Current Quote 自然语言 Regex 尝试事后证明数值来源。前者丢失 fact type / ticker / source，后者需要持续 hard-code 中文边界、大小写和同义词，既能漏放错误 ticker，也会误拦正确英文回答。

### Decision

LLM Final Completion 改为严格 JSON Answer Parts。`TextPart` 只承担解释和连接；`FactReferencePart` 当前只允许 `CURRENT_QUOTE + ticker`，Schema 不包含也拒绝 `price`。成功 Quote Tool Result 向 LLM 隐藏 authoritative price，只提供可引用 Fact 身份与派生关系；Application 持有完整 Quote，校验同 ticker 成功 Result，填充值并渲染最终字符串。无 Result、Provider Failure、wrong ticker 或非法 Parts 使用现有一次 Repair，仍失败则返回 `LLM_INVALID_PROVIDER_RESPONSE`。

当前 Aliyun Adapter 不依赖 Provider-native `response_format`：Assistant `content` 使用严格 JSON Contract，由 Application 解析。这复用已存在的 OpenAI-compatible 消息能力，不增加 SDK 或 Provider 特有类型。

### Boundary / Future

本次只迁移 CURRENT_QUOTE。Cash、Average Cost、Position Value、Price History 与 News 继续使用现有 Context / Guard；它们只有在真实 Eval 证明相同 Failure Mode 时才逐类迁移。LLM 选择引用哪个 Fact 并解释含义；Application 独占 authoritative value、Fact Resolution、Validation、Rendering 与 Source Tracking。
