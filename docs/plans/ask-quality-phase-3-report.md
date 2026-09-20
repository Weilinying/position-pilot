# Ask Quality Discovery — Phase 3 Capability Spike Report

## 1. 状态与结论

**Status:** EXECUTION CONCLUDED — NO-GO / HUMAN REVIEW REQUIRED；固定模型与 Research Live Evidence
因当前进程没有显式 Provider Credential 而为 `NOT_MEASURED`。PostgreSQL 17 临时 Schema Integration
已补测通过。

Phase 3 已完成 Runtime、Research、安全、最小 Persistence、AQ05 / AQ06 和代表性证据的离线
Capability Spike。Spike 没有修改 Production Runtime、Provider、Schema、Public API 或默认模型，所有
实现位于 `tests/spikes/ask_quality_phase3/`，新增依赖只在 `spike` Dependency Group。

当前结论：

- **Runtime：** 两个候选都证明架构可支持目标边界。Current Runtime 是 Phase 4 的暂定推荐；
  PydanticAI 保留为可行候选，不判定为 `ARCHITECTURE_LIMIT`。
- **Research：** 两条路径的 Contract 与安全边界可支持，但没有受控 Live Evidence，暂不选择
  Production Research 路径。
- **Persistence：** PositionPilot-owned Conversation、Confirmed Strategy 与 Account Ownership 的
  Application Boundary，以及 PostgreSQL 17 临时 Schema Integration 均已验证。
- **Phase 4 Entry：** `NO_GO_PENDING_LIVE_EVIDENCE`。这是一项证据不足的 No-go，不是架构失败。

### 1.1 收口 Review 修订（2026-09-20）

本次 Review 不改写既有离线运行结果，只修订其解释与后续 Gate。AQ06 改为金额分析优先，旧的
Fractional / Account Permission Gate 作为历史 Baseline 保留；当前规则见
[AQ06 Eval Revision](../evaluation/ask-quality-policy-revision-2026-09-20.md)。同时确认 Research 原型
尚未提供真实端到端回答质量证据，离线 Fixture 不得被解释为 Runtime 质量、性能或稳定性优势。

## 2. 实验合同与隔离

固定实验模型为 `qwen3.7-max`，与当前 Production Default `deepseek-v4-pro-0813` 明确区分。Safety
Ceiling 为 4 次 Model Request、4 次 Tool Call、2 次 Search、2 次 Fetch 和 30 秒；它只防止 Spike
失控，不是 Production SLO。

两个 Runtime 使用相同的 Application Input、Prompt 语义、事实、Tool Contract、Budget 和场景；
没有强制内部 Message 或 Request Payload Hash 一致。Artifact 记录规范化 Input Hash、候选实际 Trace、
Usage、Latency 和差异。外部 Tool 数据使用统一 `UNTRUSTED_TOOL_DATA` 包装。

统一 Comparison Runner 已用两个真实离线 Runtime 候选和两个真实 Research Adapter 执行同一输入 / 请求，
校验 Input / Request Hash 等价，同时保留 Message、Trace、Usage、Provider-managed / Application-owned
Search 和 Fetch Observability 差异。

Artifact Reporter 使用字段 Allowlist、必填 Provenance、Credential Value 检查与字符串长度限制；
Research Artifact 不允许原始网页正文或私有 Context 字段。调用方仍只允许使用冻结的公开 Fixture。
Fake Fixture 默认是 `NOT_MEASURED`，只有真实候选执行的确定性能力测试才能成为 `SUPPORTED`。

## 3. Runtime 对照结果

| 项目 | Current Runtime | PydanticAI 1.107.6 |
|---|---|---|
| 0 / 1 / 2+ Tool Loop | `SUPPORTED` | `SUPPORTED` |
| History / Confirmed Strategy | `SUPPORTED` | `SUPPORTED`，使用框架原生 `message_history` |
| Tool / Request Budget | Application-owned 检查 | 原生 `UsageLimits` + Search / Fetch / Wall-clock Bridge |
| Source Validation | `SUPPORTED` | `SUPPORTED` |
| Provider Failure / Tool Failure | 显式状态 / Warning；无 UNKNOWN 保留则拒绝 Final | 同左 |
| Alibaba 接入 | 复用现有 Provider-neutral Adapter | 原生 `AlibabaProvider` 可构造 |
| Provider Live Smoke | `NOT_MEASURED` | `NOT_MEASURED` |
| 主要 Production Gap | 无 Streaming / Cancellation / Production 接线 | 仅实现三个代表性 Tool 的薄 Bridge；最终 Tool Schema 接线未完成 |

Current Runtime 候选约 433 行，包含 JSON Schema 子集校验、循环、预算、Trace 和来源边界；
PydanticAI 候选约 348 行，但额外引入 `pydantic-ai-slim`、`openai` 及其锁定依赖，并需要维护
PositionPilot Tool Observation 与框架 Function Tool 之间的 Bridge。PydanticAI 的内部 Message、Tool
Schema 和 Usage 估算与 Current Runtime 不同；这些差异已保留，没有为了 Payload 一致性改写框架。

离线结果证明 PydanticAI 可以支持目标结构，但尚未证明新增依赖与 Bridge 能带来足以抵消维护成本的
实际质量、Latency 或可靠性收益。因此暂定推荐 Current Runtime，而不是把 PydanticAI 的 Prototype
Bridge 缺口误判为框架不合适。

### 3.1 证据等级

| 能力 | Current Runtime | PydanticAI | 结论边界 |
|---|---|---|---|
| 真实执行代码 | 0 / 1 / 2+ Tool、Failure、Budget、History、Source / Mutation Boundary | 同类能力通过框架 FunctionModel 与薄 Bridge 执行 | 证明代码路径可运行，不证明真实模型质量 |
| Scripted / Fixture | `ScriptedLLM` 决定 Tool Call 与 Final | `FunctionModel` / `ScriptedModel` 决定 Tool Call 与 Final | 不证明真实 Tool Selection、Arguments 或稳定性 |
| 真实模型 | 现有 Live Smoke 仅 No-tool | 现有 Live Smoke 仅 No-tool | One-tool / Multi-tool 测试已补入显式 opt-in Suite，但当前进程未运行 |
| Provider Failure | Fake Provider / Tool Failure 已验证统一 Contract | 同左 | 没有故意制造 Live Failure；真实发生时才记录 |
| Latency / Token | Contract 可记录 | Contract 可记录 | 当前没有可比较 Live 样本，不做性能结论 |

因此两个候选目前都没有回答质量、性能或稳定性优胜证据。若最小 Live Smoke 后仍同时满足需求，
继续优先比较现有 Runtime 的维护成本与框架的实际收益，不因框架能力列表更长而迁移。

## 4. Research 对照结果

### 4.1 Alibaba Native Research

实现通过 OpenAI-compatible Responses API 启用 `web_search` 与 `web_extractor`，只把实际
`url_citation` 映射为 Source。固定模型始终是 `qwen3.7-max`；若当前 Region / Endpoint 不支持，
Gateway 返回显式 Failure，不换模型完成对照。

Alibaba 当前官方文档说明 `qwen3.7-max` 的 Web Search 应使用 Responses API；同时说明普通
OpenAI-compatible Chat Completions 不返回搜索来源。因此 Source Integrity 对照不能用
`enable_search` 的 Chat Completion 结果替代 Responses Citation Evidence。参考：
[Alibaba Web Search](https://www.alibabacloud.com/help/en/model-studio/web-search)、
[Alibaba Text Generation API](https://www.alibabacloud.com/help/en/model-studio/qwen-api-reference)。

离线 Source Mapping、公开 Query 和 Failure Contract 为 `SUPPORTED`；固定 Region / Endpoint 的真实
Search、Fetch、Citation、Usage、Latency 与 Cost 均为 `NOT_MEASURED`。

### 4.2 Application-owned Research

只选择一个 Search Provider 候选：Brave Search。Page Fetch 使用独立受控 Prototype，不把它算作
第二个 Research Provider。已验证：

- Query 只由 ticker、company、event、time window 构造；
- Search、Fetch、空结果、Provider Failure 与部分成功可观察；
- Source Identity、URL、读取状态与内容范围被保留；其他 Metadata 允许 `UNKNOWN`；
- Fetch 只允许 HTTP(S)，拒绝 Credential、loopback、private、link-local 与非公开 DNS 结果；
- 每次 Redirect 重新校验，并核对实际连接 Peer 防止 DNS Rebinding，限制 Timeout、Response Size 和
  Content Type；
- 网页正文只作为不可信数据，不具有 Mutation 或状态写入接口。

Search Provider 和受控 Fetch 的离线路径为 `SUPPORTED`；真实搜索、页面读取、相关性、时效、Latency
与费用为 `NOT_MEASURED`。

### 4.3 Existing Financial Data（非第三套 Runtime）

现有 Alpaca / Application 服务优先覆盖结构化金融事实：Current Quote 提供 IEX Snapshot 的价格、
bid / ask 与时间；History 提供 SIP consolidated 日线 OHLCV；Recent News 提供 5 日 / 5 篇窗口内的
标题、摘要、来源、URL 与时间；Market Context 使用 SPY completed daily bars 形成 21-bar 确定性
heuristic。它们适合当前报价、近期价格路径、现有新闻摘要和组合风险背景。

能力边界也必须随结果暴露：Quote 是 single-exchange IEX 而非 consolidated quote，现行 freshness 上限
为 7 个日历日，因此“latest available”不等于严格盘中实时；History 只有 1Day OHLCV 且至少延迟
15 分钟；News 不请求文章正文；Market Context 只是 SPY 日线代理，不包含 VIX、breadth、宏观新闻
或盘中状态，也不是交易信号。

这些能力不提供开放网页发现、文章全文、跨来源核验、最新财报 / Filing、完整宏观事件或券商账户
权限。只有问题需要这些缺口时才考虑 A（Alibaba Native Research）或 B（Application-owned Search /
Fetch）；C（Existing Financial Data）不是与 A / B 互斥的 Runtime。当前没有证据要求新增 Yahoo
Finance、Finnhub 或其他金融数据 Provider；Skills 只记录为未来扩展候选，不进入本实验。

### 4.4 Research 内容与 Citation 的实际状态

Application-owned Adapter 已真实执行 Search / Fetch 代码，但 `FetchResult.text` 当前只在受控 Fetch
边界内存在，`ResearchResult` 只保存 Source Metadata，没有把正文接入真实模型。Runtime 的
Search → Fetch → Final 测试使用 Fake Tool Observation；它证明 Runtime 能消费内容，不证明 Brave
结果已端到端进入模型。Native Adapter 目前只从合成 Responses Payload 验证 `url_citation` 映射，
Live Provider Answer 与 Citation 尚未验证。现有能力只能称为 URL Source Mapping，不是 claim-level
Citation 或真实 Research 质量证据。

## 5. Persistence 与 Ownership

最小 Prototype 提供 Account-owned Thread、有序 Message、按 Owner / Scope 读取的 Confirmed Strategy
以及统一 State Injection Boundary。测试证明：

- Conversation 可有界恢复并被两个 Runtime 使用；
- 未确认模型建议不会进入 Confirmed Strategy Context；
- Account B 无法读取 Account A 的 Thread 或 Strategy；
- Runtime 不拥有 Conversation、Strategy、确认或 Portfolio Truth。

另有只接受显式 `SPIKE_DATABASE_URL` 的 PostgreSQL 临时 Schema Prototype。缺少该变量时直接拒绝，
不会回退 `DATABASE_URL`、`get_settings()` 或 Repository `.env`。已在隔离的本地 PostgreSQL 17 数据库
运行临时 Schema Integration Test，Owner 与 Confirmed Strategy Boundary 通过。没有创建 Production
Migration、API 或最终 Schema。

## 6. AQ05 / AQ06 与代表性 Case

原 Phase 3 结果验证了 Ledger Cash `4875.77`、本轮 Budget `500 / 200` 与 Quote `210.25` 不互相覆盖，
以及旧 Fractional / Account Permission UNKNOWN 边界；该结果保留为历史记录。修订后的最小测试进一步
验证：`200` 美元可形成任意预算内金额方案，不要求碎股搜索；用户声明支持碎股时不重复验证；明确
要求股数时理论值为 `0.9512`，同时实际可执行数量保持 `UNKNOWN`；超过 Budget 的方案被拒绝。

| Case | 状态 | 主要证据 / 限制 |
|---|---|---|
| AQ01 | `NOT_MEASURED` | Research Contract 已验证；无 Live Research |
| AQ03 | `PROTOTYPE_GAP` | Quote Loop / Source Validation 已验证；固定模型 Live 纠错未测 |
| AQ05 | `PROTOTYPE_GAP` | Cash / Budget 对照已验证；固定模型 Final 未测 |
| AQ06 | `PROTOTYPE_GAP` | 修订后的金额 / 理论股数边界已验证；固定模型 Final 未测 |
| AQ08 | `SUPPORTED` | Portfolio-only / No-tool Regression |
| AQ12 | `SUPPORTED` | GOOG → MSFT → GOOG History 与 State Injection |
| AQ17a | `SUPPORTED` | `NO_RESULTS` 独立状态 |
| AQ17b | `SUPPORTED` | `PROVIDER_FAILURE` 独立状态 |
| AQ19 | `PROTOTYPE_GAP` | 不可信 Tool Payload、静态只读 Allowlist、Fetch Security 已验证；真实模型恶意页未测 |

这些状态是 Capability Evidence，不是 Phase 4 Acceptance。

## 7. Budget 与可观察性

确定性脚本分别使用 1 次 No-tool Request、2 次 One-tool Request 和 3 次 Search / Fetch Request；
这不是代表性组合运行的统计。Phase 4 初始安全上限建议继续沿用本次 4 / 4 / 2 / 2 / 30 秒，直到
Live Evidence 可用于收窄。代表性组合预算估算整体保持 `NOT_MEASURED`。

以下值保持 `NOT_MEASURED`：真实 Provider Latency、Token / Tool Usage 可比性、Search / Fetch 费用、
慢请求分布和 Production SLO。不得把离线 FunctionModel Usage 或本次 Safety Ceiling 当作生产预算。

## 8. 验证与已知限制

已运行 Phase 3 Spike 的 `ruff check`、`mypy`、定向 `pytest`、相关 LLM / Ask Quality Regression 与
`git diff --check`。本次收口在隔离 PostgreSQL 下的受影响回归为 288 passed、29 skipped；其中 8 个
Phase 3 Live Smoke 和 21 个既有真实模型评测因未显式启用而跳过。在线测试为显式
`RUN_PHASE3_LIVE=1` Opt-in；当前因缺少 Credential 按设计跳过。PydanticAI 离线测试产生一条其内部
Event Loop 获取方式的 Deprecation Warning，不影响本次结果，但在正式采用前需要随锁定版本复核。

已知限制：

- 两个 Runtime 尚无同一固定模型的 Live 对照；
- 两条 Research 路径尚无同一时间窗的 Live Evidence；
- Current Runtime 与 PydanticAI 的真实 Latency / Usage / Cost 差异未测量；
- 代表性组合运行与预算聚合尚未测量；
- PydanticAI Bridge 只覆盖三个代表性 Tool，不是 Production Adapter；
- AQ01 / AQ03 尚不能作为 Phase 4 质量通过证据。

## 9. 配置、完成范围与后续验证

无需 Brave Key 即可先完成 Runtime 证据：`LLM_API_KEY` 用于固定模型认证，`LLM_BASE_URL` 必须指向
同一 Region / Endpoint，用于 Current Runtime、PydanticAI 与 Alibaba Native Capability Smoke。
Repository 规则禁止 Agent 读取或 source `.env`，因此即使其中已有 Key，也必须由用户把这些变量
显式暴露给执行测试的 Process。`SPIKE_DATABASE_URL` 仅用于隔离的 Persistence Integration；该项已在
本地 PostgreSQL 17 临时数据库验证，不需要生产数据库。

`BRAVE_SEARCH_API_KEY` 只用于验证 B 路径的真实搜索相关性、受控 Page Fetch、正文进入模型与来源
绑定；缺少它不阻塞模型 / Runtime / Native Research Smoke，也不意味着 Brave 已成为生产依赖。

本轮已完成：AQ06 产品规则、Prompt / Response Contract、确定性 Revision Fixture、A / B / C 定位、
证据分级、Live Tool Calling 测试入口与历史 Baseline 保留。仍需真实环境验证：两个 Runtime 的固定
模型 No-tool / One-tool / Multi-tool、Native Search / Citation，以及 Brave Search → Fetch → Model
端到端链路。Phase 4 才处理 Production Conversation / Strategy Schema、Migration、API、UI、Retention、
完整 Citation Contract、预算 SLO 与 Acceptance；未来真实接入 Broker Order 时再独立设计执行 Contract。

没有新增 ADR 或更新 `ARCHITECTURE.md`：尚未作出 Production 架构选择。完整 Strategy Lifecycle、
API / Schema、Retention、Streaming、预算冻结和 Phase 4 Acceptance 仍按计划推迟。
