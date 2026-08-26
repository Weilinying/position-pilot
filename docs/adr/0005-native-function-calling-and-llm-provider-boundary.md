# ADR 0005：M3 使用 Native Function Calling 与通用 LLM Provider 边界

## 状态

已接受（2026-08-24）

## 背景

M3 需要完成第一个 Stateful Investment Vertical Slice，让 Single Investment Agent 读取 Portfolio Snapshot、按需获取 Current Quote，并生成个性化回答。`PROJECT.md` 已确定 V1 使用 Single Investment Agent；M3 仍需选择最小 Agent Orchestration 方式与初始 LLM Integration，同时避免具体 Provider 或 Model 进入核心业务边界。

这些选择会影响 Agent Tool Use、Provider 可替换性、Failure Handling 和 Evaluation，属于 Human Review Gate。2026-08-24 经 Human Review 批准使用 Native Function Calling，并以阿里云 Model Studio 作为 V1 默认 LLM Provider。

## 候选方案

### Native Function Calling

- 直接围绕当前唯一的 Current Quote Tool 建立一次 Tool Round，依赖面和运行状态最小。
- Application 可以自行限制 Tool 名称、参数、调用数量和 Round 数，并保留完整 Tool Trace。
- 不能直接获得 LangGraph 提供的图状态、Checkpoint 或复杂分支编排，但 M3 尚无对应需求。

### LangGraph

- 适合多阶段、有循环、需要持久化图状态或复杂恢复的 Agent Workflow。
- M3 只有 Portfolio Snapshot、Current Quote 和一次 Tool Round，引入图框架不会解决当前已观察到的 Failure Mode。

### 阿里云 Model Studio OpenAI-compatible API

- 提供支持 Function Calling 的模型与 OpenAI-compatible HTTP 接口，适合国内直连并可控制当前成本。
- OpenAI-compatible 请求、响应和错误语义需要限制在 Integration Adapter，不能成为 Application Contract。
- `qwen3.7-plus` 可作为当前默认配置，但模型别名可能演进，不应成为领域或架构类型。

## 决策

- M3 使用 Native Function Calling，不引入 LangGraph。
- 每个请求最多一个 Tool Round；该 Round 最多包含三个 `get_current_quote` 调用。Tool Result 返回后必须生成 Final Response，不允许第二轮 Tool Call。
- Portfolio Snapshot 在首次 LLM 调用前由 Application 必定读取并注入，不作为可选 Tool。Snapshot 明确声明 Position 列表是完整的当前持仓集合，未出现的 Ticker 表示当前无持仓。
- Application 自动生成当前 Evaluation 已证明需要的轻量 Deterministic Derived Facts，并注入结构化 Context Capability Manifest。LLM 只解释已提供事实，不负责金融数值计算，也不得用训练知识补足不可用能力。
- Final Response 返回用户前由确定性 Grounding Guard 检查高置信的 Contract 越界：未提供的金融数值、明确购买能力结论，以及显式复述且与代码相反的结构化关系值。Guard 不从开放自然语言推断操作数，也不判断投资观点是否合理。
- 首次 Guard Failure 最多触发一次 `tools=()` 的 Response Repair。Repair 复用原 Context、Tool Results、无效回答和结构化违规信息，不重新执行 Agent 或 Tool Selection；Repair 后仍失败则返回 `LLM_INVALID_PROVIDER_RESPONSE`。
- Portfolio-level Ticker 聚合不覆盖 `LONG_TERM` / `SWING` Position 语义；历史成本权重与当前市值权重明确区分。
- Transaction History 不在 M3 默认 Context 中；后续仅由真实需求、Evaluation Failure 或新的 Context Retrieval 能力引入。
- Application 只依赖通用 `LLMProvider`。Message、Tool Definition、Tool Call 和 Completion Result 使用项目自身的 Application Schema。
- 初始 Integration Adapter 使用阿里云 Model Studio OpenAI-compatible API；Provider 请求、响应、Credential 和错误映射只存在于 Adapter。
- `qwen3.7-plus` 是 `LLM_MODEL` 的 V1 默认配置，可通过环境变量覆盖，不创建绑定具体模型的业务类型。
- Market Data Provider Failure 与 LLM Provider Failure 使用不同 Failure Taxonomy。Market Data Failure 可以在明确缺失事实后降级为 `DEGRADED`；LLM Provider Failure 无法形成 Final Response，必须返回 Request Failure。
- `OK` / `DEGRADED` 由 Application 根据 Tool Execution Result 确定，不交给 LLM 判断。

## 理由

- Native Function Calling 足以验证 M3 的最小 Tool Use，同时保留以后替换 Orchestration 的空间。
- Portfolio Snapshot 必定注入可以避免模型遗漏结构化用户事实，也不需要在 M3 增加确定性 Ticker Extraction。
- 通用 LLM Contract 保持 Agent、Domain 与具体 Provider / Model 解耦，便于测试和后续替换。
- 固定 Tool Round 与调用上限让成本、Latency 和错误边界可预测。
- Derived Facts 直接由已有 Portfolio 与 Quote 生成，不增加 Calculator Tool、Tool Routing 或外部数据依赖。
- 真实 Evaluation 已证明模型即使能复述 Prompt Policy，仍可能输出相反的确定性推导；Guard 将该边界从 Prompt 约定提升为 Application 可执行约束，一次 Repair 在不形成循环的前提下改善用户体验。

## Trade-off

- Native Function Calling 的 Tool Selection 质量依赖真实模型，Fake LLM 测试只能验证 Orchestration，不能证明模型行为正确。
- M3 只有 Portfolio Snapshot 与 Current Quote，无法高质量回答依赖 News、Earnings、Fundamentals 或整体 Market Context 的问题；这些信息必须表达为 `UNKNOWN`。
- M3 不具备 Asset Metadata，无法确认真实交易资格或可执行购买数量；Cash 与 Quote 的数值关系不能被解释为订单一定可执行。
- 默认 Provider 会形成运维依赖，但 Application Contract 与模型配置保持独立，降低未来替换成本。
- 单个 Tool Round 不支持需要多阶段检索的问题；这是 M3 的有意范围限制。
- Guard 只能覆盖明确可编码的 M3 Contract 越界，关系幅度、跨 Ticker 自然语言比较等模糊语义保留给 Human Behavioral Review；Repair 最多增加一次 LLM Latency 与 API Cost。

## Evaluation

- 默认 Tests 使用 Fake LLM 与 Fake Market Data，验证 Context Construction、Tool Validation、Tool Execution、Failure Handling、Source Tracking、Round Limit 和 API Contract。
- Opt-in Behavioral Eval 使用真实 `AliyunLLMProvider` 与 Fake Market Data，固定市场事实后验证真实模型的 Tool Selection、Grounding 和 Personalization，不进入默认 CI。
- 真实 LLM + 真实 Market Data 只用于少量 Integration Smoke Test，不作为 Behavioral Eval 的主要依据。

## M5 Structured Final Response 演进

- 真实 Qwen Behavioral Eval 暴露 Prompt-only JSON Contract 会频繁产生非法 JSON，并让一次性 Repair 接近正常路径。Application 因此新增 provider-neutral `TEXT / JSON_OBJECT` Completion Capability；具体 OpenAI-compatible `response_format={"type":"json_object"}` 只由 Aliyun Adapter 映射。
- 可能直接形成 Final Answer 的首轮 Completion、Tool Result 后的 Final Completion 与异常 Repair 均请求 `JSON_OBJECT`。首轮同时暴露 Native Tools，是因为它也允许模型在无需 Tool 时直接返回 Final Answer；并未为纯 Tool 阶段新增第二套 Provider 参数。
- Provider-native JSON 只约束 JSON 语法，不证明 `answer / source_refs` Schema 或来源真实性。Application Parser、Structured Source Validation 与最多一次 No-Tool Repair 全部保留，形成 defense-in-depth。
- 默认 `qwen3.7-plus` 支持该模式；若通过配置替换模型，所选模型必须兼容 `JSON_OBJECT`。Provider 拒绝该能力时保持既有 LLM Failure Taxonomy，不静默回退到 Prompt-only TEXT。

## 重新考虑条件

- Evaluation 证明 Native Function Calling 持续无法稳定完成 Tool Routing。
- 后续出现多阶段检索、循环、Checkpoint、长流程恢复或复杂并行 Tool 编排需求。
- 阿里云 Model Studio 在可用性、合规、成本、模型能力或接口兼容性上不再满足 V1 需求。
- 新 Provider 在真实 Evaluation 中形成可验证的质量、Latency 或成本优势。
