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
*   **Behavioral 信号必须分离：** Tool Selection 来自 Fake Provider 实际收到的请求；Source Declaration 来自 Final `result.sources`；Repair Rate 来自实际 Tool Round 所需 Completion 数。三者不能互相反推，否则漏报 `source_ref` 会同时伪造成“未调用 Tool”和“发生 Repair”。Failure Diagnostics 同样只使用本轮实际 Retrieve 成功的 Context，不能把 Fixture 中尚未请求的数据视为可用来源。

### 2. 提示词与系统保证 (Prompt 与 System Guarantee)
*   **职责划分：** Backend 强约束 Portfolio / Ledger、确定性计算、Tool Result 与 Source 是否真实存在；Prompt、Behavioral Eval 与 Human Review 负责最终自然语言的事实使用和表达质量。V1 不把 Backend 扩张成逐 Claim 的形式化验证器。
*   **拦截与修复机制 (Response Repair)：**
    *   Final Completion 的外层 `{answer, source_refs}` JSON 非法，或声明了本轮未成功取得的 Source 时，最多向模型发起一次 `tools=()` 的修复请求。
    *   如果修复后仍违反 Structured Source Contract，返回 `LLM_INVALID_PROVIDER_RESPONSE`；不形成隐式循环。
*   **高置信度阻断：** Application 当前只阻断代码能够不依赖自然语言推断证明的错误：非法 Structured Output、未知 Source Type、缺少 ticker，以及无法绑定到本轮成功 Context 的同类型 / 同 ticker Source Reference。`answer` 内的数字、关系、购买能力措辞与其他 Claim 不再由确定性代码扫描。

### 3. 拦截器策略收缩 (Guard 收缩)
*   **踩过的坑：** Guard 曾尝试使用复杂的正则表达式（Regex）去检测“略高”、“微利”、“显著”等词汇，以及识别跨 Ticker 的开放式比较，甚至试图从复杂句式中推断操作数。这导致代码层面的 Guard 退化成了一个“自然语言启发式审核器 (Natural-language Heuristic Reviewer)”，并引发了实际的误报（False Positive）。
*   **最终决定：** 删除生产环境的自然语言金融数字、购买能力、显式关系与方向 Guard，以减少误报、无意义 Repair、额外 LLM 调用和 Prompt / Guard 重复逻辑。
*   **事实身份演进：** M4 依次经历“全局 Decimal allow-list / Current Quote Regex”与“Structured Fact Reference + deterministic rendering”。前者连续暴露 Unicode `\b`、大小写和同义词缺口；后者虽然避免 Regex，却把 V1 推向逐事实结构化渲染，并迫使 Quote 数值从 LLM Context 隐藏。最终收敛为 Free-form Answer + validated Structured Sources：模型自由组织事实，Application 只证明声明来源真实存在。
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

*   **注重边界清晰：** Application 不再对自然语言 Claim 做启发式阻断，会有意放过模型抄错数字、遗漏来源声明或错误解释 Derived Fact 等回答质量问题；这些进入 Behavioral Eval，而不是继续扩充 Regex。
*   **Evaluation 的定位：** M3 Evaluation 的核心作用是暴露模型的行为特征（Behavioral Profile），帮助确认问题应该由哪一层（架构、工具、提示词还是换模型）来解决，**而不是把每一次模型失误都硬修成生产环境的拦截规则。**
*   **未来的触发条件：** 只有当后续的 Evaluation 明确证明某类 Failure 必须跨模型稳定阻断，并且能够通过结构化事实或低误报规则进行可靠验证时，才重新评估是否需要修改 Production Guard。
*   **演进方向：** M4～M6 阶段应当在现有 Case 基础上继续积累证据，而不是去建设一个通用庞大的自然语言审核框架。

## Summary
Eval 遇到 failure 时是看LLM的回答是什么样的问题，如果是模型行为质量相关的问题，那么可以不用在代码/prompt里进行修改，因为这可能能随着模型的更换或者上下文信息量（证据）的增加而改善。核心就是“如果换成一个行为极好的完美模型，系统是否仍必须强制保证这件事？”如果是的话才需要进行修改。因为你永远写不完拦截规则。

## M4 Free-form Answer + Validated Structured Sources

### Problem

Quote Grounding 先后用全局 Decimal allow-list 和 Current Quote 自然语言 Regex 尝试事后证明数值来源。前者丢失 fact type / ticker / source，后者需要持续 hard-code 中文边界、大小写和同义词。随后采用的 `TextPart + FactReferencePart + deterministic renderer` 解决了 Quote 数值替换问题，却把系统职责扩大到逐事实结构化渲染，并限制模型不能在自由文本中自然复述价格。

### Decision

LLM Final Completion 使用严格外层 JSON：`answer` 是不做 Claim Parsing 的自由文本，`source_refs` 是模型声明实际使用的 Context 身份。Portfolio Snapshot 不需要 ticker；Current Quote、Price History 与 Recent News 使用 `type + ticker`。Application 只接受本轮成功取得的同类型、同 ticker Source，缺失结果、Provider Failure 或 wrong ticker 进入一次 Repair。成功但未声明使用的 Context 不进入 Final Source Tracking；失败 Tool Attempt 继续保留 status 供降级诊断，但不能成为成功 Source Reference。

Quote Tool Result 再次向 LLM 提供实际 price。Backend 不负责把 answer 中的 `210.25` 与 Tool Result 逐句比对，也不再校验 Cash、Average Cost、History 数字或购买能力措辞。确定性 Portfolio / Transaction / Cash / Market Data / Derived Facts 的生成与校验仍留在代码边界。

M5 真实 Qwen Behavioral Eval 证明 Prompt-only JSON enforcement 会让非法 JSON 与 Repair 频繁进入正常路径。当前 Application 使用 provider-neutral `JSON_OBJECT` 能力请求结构化 Final Completion，Aliyun Adapter 才将其映射为 OpenAI-compatible `response_format={"type":"json_object"}`。Parser、Structured Source Validation 与一次 Repair 仍保留；Provider 原生约束只减少 JSON 语法失败，不能替代来源真实性验证。

M5 同时把 Required Context Policy 限定为极窄的 model-declared minimum context floor：LLM 仍是 Optional Tool 的 primary router，并在 Current Quote Native Tool 参数中结构化声明请求语义。只有模型声明“无既定规则的当前风险动作判断”且漏选 Market Context 时，Application 才补足无参数 `get_market_context`。该机制不扫描问题关键词，不扩展成完整 Intent Router，也不为购买能力或既定规则执行机械获取 Market Context；模型漏掉 Quote 或误分类 purpose 仍是 Routing Quality，而不是 Application 独立语义分类保证。

### Boundary / Future

该方案不是 sentence-level citation，也不证明每个 Claim 都由 `source_refs` 支撑；没有 `[1]`、claim-to-evidence mapping 或 Citation UI。已知残余 Failure 包括：模型可能抄错已提供数字、用错误方式解释确定性关系、在 answer 使用某来源却漏报 source ref，或声明来源但实际文本没有使用。PositionPilot V1 通过 Prompt 与 Behavioral Eval 衡量这些模型级 Grounding Failure；若未来产品明确需要逐 Claim 可审计性，再单独评估更强的 Citation Contract。

## M6 Bounded Historical BUY Context

### Problem

M6 Coverage Audit 发现，V1 Success Criteria 要求使用历史买入位置，但 Agent 只接收重建后的当前 `PortfolioState`；即使模型行为完美，也无法获得历史 BUY 事实。

### Decision

`PortfolioService` 在同一 UoW 中读取 Transaction / Cash Event Ledgers，重建当前 State，并生成 Agent 专用的 `historical_buy_facts`。投影只包含当前 Positions 的 BUY，每个 `(ticker, position_type)` 保留最近 5 条，并声明总数与截断状态；不包含 User / Transaction ID、自由文本原因、完整 Ledger 或 Cash Event History。它继续属于 `PORTFOLIO_SNAPSHOT`，不新增 Tool、Source Type、调用预算或公共 API。

### Boundary / Future

当前 State 仍是 Cash、Position、Shares 与 Average Cost 的 Source of Truth；历史 BUY Facts 不能用于重算这些值或收益。只有未来 Evaluation 证明需要查询已清仓标的、任意时间范围或完整 Ledger 时，才重新评估独立 Transaction History Tool。
