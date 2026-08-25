# M3 — Minimal Investment Agent 执行计划

## 1. 状态与目标

**Status:** DONE

M3 完成第一个 Stateful Investment Vertical Slice，验证 Portfolio Snapshot、Native Function Calling 和 Current Quote 是否能够形成可运行、可追溯且个性化的最小投资回答。

## 2. 已批准语义

- V1 使用 Single Investment Agent；M3 使用 Native Function Calling，不引入 LangGraph。
- Portfolio Snapshot 必定注入，并明确 Positions 是完整的当前持仓集合；未出现的 Ticker 表示当前无持仓。
- Transaction History 不在 M3 默认 Context 中，也不引入确定性 Ticker Extraction。
- Current Quote 是唯一 Market Tool；每个请求最多一个 Tool Round，每轮最多三个调用。
- Tool Result 返回后必须生成 Final Response，不允许第二轮 Tool Call。
- Final Response 返回用户前经过确定性 Grounding Guard；首次越界最多执行一次不带 Tool Choice 的 Response Repair，Repair 后仍越界则返回 `LLM_INVALID_PROVIDER_RESPONSE`。
- Application 依赖通用 `LLMProvider`，初始 Adapter 使用阿里云 Model Studio，默认模型通过 `LLM_MODEL` 配置。
- Market Data Failure 可以安全降级为 `DEGRADED`；LLM Provider Failure 必须返回 Request Failure。
- `FACT`、`INFERENCE`、`UNKNOWN` 是语义边界，不强制固定回答标题。
- `OK` / `DEGRADED` 由确定性 Application Code 计算。
- M3 不提供 Asset Trading Capability；`tradable` 与 `fractionable` 保留为后续确定性 Provider 扩展点，当前缺失时均为 `UNKNOWN`。
- Average Cost 只表示用户历史成本，不等同于市场估值或未来收益概率。
- Snapshot 提供当前 Eval 已证明需要的 Ticker 数量、总持仓历史成本和按 Ticker 聚合、保留两位小数的历史成本权重百分比；该权重不包含 Available Cash，也不表示当前市值权重。Quote 成功后由代码提供 Cash / 单股价格及 Quote / Average Cost 关系。
- 每次请求注入结构化 Context Capability Manifest；Capability 描述数据来源是否可用，不承载具体 Ticker 的 Asset Fact。
- Trading Plan、Exit Conditions 与 Risk Budget 在 M3 Decision Context 中明确为 `UNKNOWN`，不从 Conversation Memory 或模型知识推断。
- 语义相同的重复 Quote Call 按规范化 Ticker 复用一次 Provider Result，同时满足每个 Native Tool Call 的响应协议。

## 3. Scope

- 建立 Provider-neutral LLM Message、Tool Definition、Tool Call、Completion Result 与 Failure Schema。
- 实现阿里云 Model Studio OpenAI-compatible 同步 Adapter、安全配置与失败映射。
- 实现 `InvestmentAgent`，构建 Portfolio Snapshot、执行一次受限 Tool Round，并记录可追溯 Context Source。
- 实现只保护 M3 Context Contract 的 Final Response Guard，检测未提供的金融数值、明确购买能力结论，以及显式复述且与代码相反的结构化关系值。关系幅度、跨 Ticker 自然语言比较等模糊语义不进入生产阻断。
- 建立最小投资问答 API Vertical Slice。
- 使用 Fake LLM / Market Data 完成默认 Deterministic Agent Tests。
- 建立约 10～20 个固定 Opt-in Real-Model Behavioral Eval Cases，使用真实 Aliyun LLM 与 Fake Market Data。
- 增加少量真实 LLM + 真实 Market Data Integration Smoke Test，缺少 Credential 时跳过。
- 为 Context Selection、Tool Call、Provider Failure 和关键 Latency 提供不包含 Secret 或用户问题正文的结构化日志。

## 4. Non-Goals

- 不实现 News、Fundamentals、Earnings、VIX、Market Regime、Conversation Memory 或复杂 Technical Analysis。
- 不默认注入 Transaction History，不实现新的 Context Retrieval Tool。
- 不接入 Trading / Asset Metadata Provider，不判断具体标的是否 `tradable` 或 `fractionable`，也不计算可执行购买数量或建议买入金额。
- 不引入 LangGraph、Multi-Agent、Vector Database、Cache、Queue 或后台任务。
- 不建设完整 Evaluation Framework、LLM-as-a-Judge、多模型 Benchmark、历史回测或金融预测准确率评价。
- Guard 不判断投资观点、建议质量或语言风格，不建设通用事实验证或自然语言审核框架。
- 不把开发用投资问答 API 视为已具备生产 Authentication / Authorization。

## 5. Acceptance Criteria

- 自然语言问题能够进入 `InvestmentAgent`，且 Portfolio Snapshot 必定进入模型 Context。
- Snapshot 明确声明 Positions 完整，并保留 Available Cash、Shares、Average Cost 与 Position Type；不包含 Transaction History。
- 需要行情时模型可以通过 `get_current_quote` 获取结构化 Current Quote，不需要行情时可以直接回答。
- Tool 名称、Ticker、Arguments、每轮调用数量和 Round Limit 均由 Application 校验。
- 一个 Tool Round 可执行最多三个 Quote；Tool Result 返回后再次请求 Tool 必须明确失败。
- Final Response 越过 M3 Context Contract 时只允许一次 `tools=()` Repair；Repair 不重新执行 Agent 或 Tool Selection，仍不合规时返回明确 Request Failure。
- 当前金融事实只来自 Portfolio Snapshot 或 Tool Result；缺失的当前 Context 明确为 `UNKNOWN`。
- 未提供 `fractionable` 时不得默认整股或碎股交易，不得以 Cash 低于单股价格直接推导无法买入；具体可购买股数不交给 LLM 计算。
- 历史成本权重、Quote 关系和 Cash 关系由 Application 自动计算；当前市值权重、技术面、当天市场和行业关系在对应 Capability 不可用时保持 `UNKNOWN`。
- 发给外部 LLM 的 Snapshot 不包含内部 `user_id`；相同问题的 Cash 与 Position Type A/B Cases 能供 Human Review 比较实际回答差异。
- Market Data Failure 与 LLM Provider Failure 明确区分，只有前者可以产生 `DEGRADED` Final Response。
- `OK` / `DEGRADED`、Source Tracking 和 Request Failure 由确定性代码产生。
- LLM Provider Contract 不包含 Aliyun/OpenAI-compatible 类型或模型绑定命名。
- 默认 Tests 不依赖真实 LLM 或 Market API；Opt-in Behavioral Eval 不进入默认 CI。
- 约 10～20 个真实模型 Behavioral Cases 覆盖 Tool Selection、Portfolio Awareness、Grounding、Position Type 与 Missing Data。
- 端到端 API Vertical Slice 可运行；超出 M3 能力的问题不会把模型训练知识表述为当前事实。

## 6. 执行顺序

```text
T1 ADR / Plan / Config Contract
  ↓
T2 Provider-neutral LLM Contract + Aliyun Adapter
  ↓
T3 InvestmentAgent + Tool Round + Failure Taxonomy
  ↓
T4 FastAPI Vertical Slice + Dependency Wiring
  ↓
T5 Deterministic Tests + Final Response Guard + Opt-in Behavioral Eval + Smoke Test
  ↓
T6 Full Tests / Quality Checks
  ↓
T7 主线程 Automated Review → 修复 → 再验证
  ↓
Atomic Commits → Human Acceptance
```

LLM Schema、Adapter、Agent Tool Loop 和 API 共享直接 Contract 依赖，由主线程串行实现。Behavioral Eval 在核心 Contract 稳定后接入，避免把 Mock Orchestration Test 误称为模型行为验证。

## 7. Completion Summary

**Status:** DONE（2026-08-25）

### Implemented

- Provider-neutral LLM Contract、阿里云 Model Studio Adapter 和可配置默认模型。
- 必定注入完整 Portfolio Snapshot 的 Single Investment Agent，以及最多一个 Round、三个 Current Quote 调用的 Native Function Calling。
- 由 Application 生成的 Portfolio / Quote Derived Facts、Context Capability Manifest、Source Tracking 和确定性 `OK` / `DEGRADED` 状态。
- Market Data Failure 与 LLM Provider Failure 的独立 Taxonomy，以及 Missing / `UNKNOWN` Data 的安全降级。
- 只阻断高置信 Context Contract 越界的 Final Response Guard，以及最多一次 no-tool Repair。
- 默认 Fake Provider Tests、17 个真实模型 + Fake Market Data Behavioral Cases，以及独立的真实 LLM + 真实 Market Data Smoke Test。

### Evaluation Result

- 最近一次完整 Real-Model Behavioral Eval 的 Automated Contract 为 17 / 17 PASS。
- Human Review 仍观察到跨 Ticker 自然语言比较、关系幅度措辞、Position Type 个性化差异偏弱和部分非关键字段未完整复述。
- 上述 Model Behavioral Quality Limitation 已记录在 `docs/engineering-notes/m3-agent-evaluation-and-grounding-boundaries.md`，不通过扩大 Production Guard 消除。

### Deferred

- News、Fundamentals / Earnings、VIX、Market Regime、Conversation Memory 和复杂 Technical Analysis。
- Trading / Asset Metadata、`tradable`、`fractionable` 和可执行购买数量。
- 多阶段 Tool Retrieval、LangGraph、Multi-Agent 和完整 Evaluation Platform。
- Human Behavioral Quality 的持续改进保留给后续 Evaluation、Prompt / Context 演进与 Model Selection。

### Verification

- 默认 pytest：151 passed，26 skipped；跳过项为显式启用的真实模型、真实 Market Data 和 PostgreSQL Integration Tests。
- M3 核心 Agent / Guard / API / Provider Contract 定向测试：76 passed。
- Ruff format / lint（项目配置的 `backend`、`tests` Scope）：PASS。
- mypy strict：PASS（40 source files）。
- `uv lock --check`：PASS。
- M3 修改文件的 `git diff --check`：PASS。
- 主线程 Automated Review 未发现新的 Blocking Issue。

### Decision Records

- ADR 0005：Native Function Calling、通用 LLM Provider Boundary、单轮 Tool Use 与 Grounding Guard。
- Engineering Note：M3 Evaluation 分层、Guard 演化、System / Model Failure 分类和验收时已知行为限制。
