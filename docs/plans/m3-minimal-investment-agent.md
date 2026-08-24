# M3 — Minimal Investment Agent 执行计划

## 1. 状态与目标

**Status:** IN PROGRESS

M3 完成第一个 Stateful Investment Vertical Slice，验证 Portfolio Snapshot、Native Function Calling 和 Current Quote 是否能够形成可运行、可追溯且个性化的最小投资回答。

## 2. 已批准语义

- V1 使用 Single Investment Agent；M3 使用 Native Function Calling，不引入 LangGraph。
- Portfolio Snapshot 必定注入，并明确 Positions 是完整的当前持仓集合；未出现的 Ticker 表示当前无持仓。
- Transaction History 不在 M3 默认 Context 中，也不引入确定性 Ticker Extraction。
- Current Quote 是唯一 Market Tool；每个请求最多一个 Tool Round，每轮最多三个调用。
- Tool Result 返回后必须生成 Final Response，不允许第二轮 Tool Call。
- Application 依赖通用 `LLMProvider`，初始 Adapter 使用阿里云 Model Studio，默认模型通过 `LLM_MODEL` 配置。
- Market Data Failure 可以安全降级为 `DEGRADED`；LLM Provider Failure 必须返回 Request Failure。
- `FACT`、`INFERENCE`、`UNKNOWN` 是语义边界，不强制固定回答标题。
- `OK` / `DEGRADED` 由确定性 Application Code 计算。

## 3. Scope

- 建立 Provider-neutral LLM Message、Tool Definition、Tool Call、Completion Result 与 Failure Schema。
- 实现阿里云 Model Studio OpenAI-compatible 同步 Adapter、安全配置与失败映射。
- 实现 `InvestmentAgent`，构建 Portfolio Snapshot、执行一次受限 Tool Round，并记录可追溯 Context Source。
- 建立最小投资问答 API Vertical Slice。
- 使用 Fake LLM / Market Data 完成默认 Deterministic Agent Tests。
- 建立约 10～20 个固定 Opt-in Real-Model Behavioral Eval Cases，使用真实 Aliyun LLM 与 Fake Market Data。
- 增加少量真实 LLM + 真实 Market Data Integration Smoke Test，缺少 Credential 时跳过。
- 为 Context Selection、Tool Call、Provider Failure 和关键 Latency 提供不包含 Secret 或用户问题正文的结构化日志。

## 4. Non-Goals

- 不实现 News、Fundamentals、Earnings、VIX、Market Regime、Conversation Memory 或复杂 Technical Analysis。
- 不默认注入 Transaction History，不实现新的 Context Retrieval Tool。
- 不引入 LangGraph、Multi-Agent、Vector Database、Cache、Queue 或后台任务。
- 不建设完整 Evaluation Framework、LLM-as-a-Judge、多模型 Benchmark、历史回测或金融预测准确率评价。
- 不把开发用投资问答 API 视为已具备生产 Authentication / Authorization。

## 5. Acceptance Criteria

- 自然语言问题能够进入 `InvestmentAgent`，且 Portfolio Snapshot 必定进入模型 Context。
- Snapshot 明确声明 Positions 完整，并保留 Available Cash、Shares、Average Cost 与 Position Type；不包含 Transaction History。
- 需要行情时模型可以通过 `get_current_quote` 获取结构化 Current Quote，不需要行情时可以直接回答。
- Tool 名称、Ticker、Arguments、每轮调用数量和 Round Limit 均由 Application 校验。
- 一个 Tool Round 可执行最多三个 Quote；Tool Result 返回后再次请求 Tool 必须明确失败。
- 当前金融事实只来自 Portfolio Snapshot 或 Tool Result；缺失的当前 Context 明确为 `UNKNOWN`。
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
T5 Deterministic Tests + Opt-in Behavioral Eval + Smoke Test
  ↓
T6 Full Tests / Quality Checks
  ↓
T7 主线程 Automated Review → 修复 → 再验证
  ↓
Atomic Commits → Human Acceptance
```

LLM Schema、Adapter、Agent Tool Loop 和 API 共享直接 Contract 依赖，由主线程串行实现。Behavioral Eval 在核心 Contract 稳定后接入，避免把 Mock Orchestration Test 误称为模型行为验证。
