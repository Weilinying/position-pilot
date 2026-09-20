# Ask Quality Discovery — Phase 3 Framework / Capability Spike 实现计划

## 1. 目标、状态与进入门槛

**Status:** SPIKE EXECUTION CONCLUDED — NO-GO / HUMAN REVIEW REQUIRED（2026-09-20）；固定模型、
Research 与 PostgreSQL Live Evidence 因当前进程没有显式 Credential / `SPIKE_DATABASE_URL` 而为
`NOT_MEASURED`，Phase 4 Entry 为 `NO_GO_PENDING_LIVE_EVIDENCE`。执行结果见
[Phase 3 Report](ask-quality-phase-3-report.md) 与
[Phase 4 Decision Proposal](ask-quality-phase-4-decision-proposal.md)。本文只授权执行 Capability Spike，
不授权生产替换、Production Migration、Public API 变化或 Release Mapping。

Phase 3 是用于决定 Phase 4 技术路线的最小 Capability Spike，不提前完成 Phase 4 的生产实现。
它只回答以下问题：

1. Current Runtime 与 Pydantic AI 哪个更适合 PositionPilot 的 Single Agent 多轮 Tool Loop；
2. Alibaba Native Research 与一个实际可运行的 Application-owned Search / Fetch 候选，哪个更适合
   PositionPilot 的来源、失败、安全和预算边界；
3. 候选 Runtime 能否接入 Account-owned Conversation 与已确认 Strategy，而不把业务状态交给框架；
4. 在 AQ05 / AQ06 中，现有事实与 UNKNOWN 边界能否阻止错误执行结论；
5. 使用一个当前可用的实验模型时，候选 Runtime / Research 路径能否真实运行并提供决策所需证据。

Phase 3 的产物是代表性测试证据、Runtime / Research 比较结果、最小 Persistence 验证、预算估算和
Phase 4 Decision Proposal。任何进入 Production 的 Runtime、Research Provider、Schema、Public API、
Security Boundary 或主要 Agent 架构变化仍须 Human Review。

开始执行前必须满足：

- [Phase 2 Decision Proposal](ask-quality-decision-proposal.md) 的六项请求已经 Human Accepted，
  或修改意见已经回写且状态明确；
- Phase 3 的候选、固定模型、代表性 Case、Critical Gate、实验预算和 Artifact 字段已经冻结；
- 开始 P3-T0 前，将已通过检查和 Human Acceptance 的 Phase 2 Branch 合并到本地 `main`；
- 从 `main` 创建独立 `codex/spike/ask-quality-phase3` Branch，工作区没有会被覆盖的用户修改。

若 Phase 2 未获批准，可以审阅和修改本文，但不安装候选依赖、不调用真实 Research Provider，
也不开始会暗含生产方向的实现。

## 2. 当前基线与不变边界

当前生产路径已经具备：

- `InvestmentAgent` 单轮 Native Function Calling，最多四个 Context Tool Call；
- Provider-neutral `LLMProvider`、Message、Tool 与 Result Contract；
- Quote、Price History、Recent News、SPY Market Context 和明确的 Provider Failure；
- 自由文本 Answer 外层 `{answer, source_refs}`、Source Reference Validation 与一次 No-Tool Repair；
- Session-derived Account / Portfolio Ownership、PostgreSQL、SQLAlchemy Unit of Work 与 Alembic；
- Ask Quality Dataset `0.1`、Fixture / Reporter / Artifact，以及 `qwen3.7-max` Phase 1 Evaluation
  Baseline；当前 Production Config 默认模型仍是 `deepseek-v4-pro-0813`，两者不能混称。

Phase 3 不改变以下边界：

- Portfolio、Cash、Transaction、Lot 与 Position Type 继续以现有确定性 Ledger 为 Source of Truth；
- 当前金融事实必须来自足够新的结构化 Provider 或本轮实际取得的 Research Evidence；
- Framework 不拥有 Portfolio、Strategy、确认、来源或状态有效性语义；
- Search Query 不包含持仓数量、成本、现金、Strategy、完整 Conversation、Account / Session 标识；
- External Content 始终是不可信数据，不能改变指令、权限、Strategy 或 Ledger；
- 继续使用 Single Agent；不引入 Multi-Agent、LangGraph、Vector Database、完整 Memory Framework、
  Queue、Durable Workflow、Broker Connection、CashReconciliation 或 Long-term Memory；
- 不修改旧 `/v1/investment/questions` 的单问兼容行为；Spike 代码与 Production Code 隔离。

### 2.1 外部能力核验基线（2026-09-19）

Phase 3 开始时重新核验以下官方文档，不把本文记录当作长期不变事实：

- Pydantic AI 提供 Agent Loop、`message_history` 与 Usage Limits，但 Conversation Ownership、持久化和
  业务状态仍由 Application 管理；
- Pydantic AI Native Tool 的实际支持依赖 Model Provider，因此 Runtime 与 Research 分开评价；
- Alibaba OpenAI-compatible Chat Completions 与 Responses / Native Research 的来源和调用事件能力
  不同，必须以当前 Model、Region、Endpoint 的实际结果为准。

核验入口：[Pydantic AI Agent](https://pydantic.dev/docs/ai/core-concepts/agent/)、
[Pydantic AI Message History](https://pydantic.dev/docs/ai/core-concepts/message-history/)、
[Pydantic AI Native Tools](https://pydantic.dev/docs/ai/tools-toolsets/native-tools/)、
[Alibaba Web Search](https://www.alibabacloud.com/help/en/model-studio/web-search)。

## 3. 实验隔离与交付物

Phase 3 可以在 `tests/spikes/ask_quality_phase3/` 中维护最小 Harness、Fixture、候选 Adapter、
Persistence Prototype 和 Reporter；不要求为未来 Production 目录提前设计最终模块结构。

若 Pydantic AI 或 Research SDK 需要新依赖，将其放入独立 `spike` Dependency Group 并锁定版本，
不加入 Production Dependencies。最终未被选中的依赖和 Adapter 在证据保留后删除。

Artifact 默认写入 Git 忽略目录：

```text
build/evaluation-runs/ask-quality-phase3-<run-id>/
├── manifest.json
├── runtime/{current,pydantic-ai}/...
├── research/{native,application-owned}/...
├── persistence/...
└── decision-evidence.json
```

Artifact 至少记录 Revision、候选与版本、Provider / Model、Endpoint 类别与 Region（脱敏）、
Prompt / Tool / Fixture Hash、实验预算、Tool / Research Trace、失败状态、Latency、Token Usage、
Search / Fetch Count 和可得 Cost。Secret、Credential、用户私有 Context 和不必要的完整网页正文
不得进入 Git 或日志。

## 4. 评价方式与 Gate

Phase 3 不使用跨类别总分，也不要求 Prototype 达到生产完整度。每项结果使用：

- `SUPPORTED`：候选已用代表性证据证明能够支持；
- `PROTOTYPE_GAP`：架构可支持，但 Spike 尚未完成生产级实现；
- `ARCHITECTURE_LIMIT`：候选无法在可接受边界内支持；
- `NOT_MEASURED`：本轮没有足够证据，不能当作通过或失败。

只有以下风险属于 `HARD` Gate，推荐进入 Phase 4 的候选必须通过：

- Security / Query Privacy / Prompt Injection 边界；
- Account Ownership 隔离；
- Ledger 与 Confirmed Strategy 的 Source of Truth、Mutation Boundary；
- Source Integrity：引用必须来自本轮实际取得且可识别的来源，失败或空结果不能伪造 Source；
- Phase 2 Critical Gate：错误 Portfolio / Cash / Budget、未核验关键事实被当真、Execution UNKNOWN
  被写成确定行动结论等。

非安全性的缺口，如 Streaming、完整 Trace UI、自动裁剪、Production Repository、最终 API、精确预算
或全部错误码，可以记录为 `PROTOTYPE_GAP`，进入 Phase 4 再完成。`NOT_MEASURED` 需要在 Decision
Proposal 中说明影响，不能通过增加无关实验范围强行补齐。

### 4.1 Runtime 对照表

| 项目 | 要求 | 证据 |
|---|---|---|
| 0 / 1 / 2+ Tool Call 的继续与停止 | 必测 | 固定 Fake Script |
| Tool 参数、未知 Tool、Failure 与预算终止 | `HARD` 相关项通过 | 确定性测试 |
| Conversation History 与 Confirmed Strategy 注入 | 必测 | 多轮 Fixture |
| Structured Output 与 Source Validation 兼容 | `HARD` | AQ17a/b 类 Fixture |
| Usage / Trace / Latency 可取得程度 | 记录差异 | Artifact |
| Provider 接入方式与维护成本 | 记录差异 | Adapter Review |
| 接入代码量、依赖与可测试性 | 比较 | Diff / 设计审阅 |

### 4.2 Research 对照表

| 项目 | 要求 | 证据 |
|---|---|---|
| Search / Fetch 是否真实执行且可观察 | 必测 | Tool Trace / Provider Usage |
| Source Identity、URL / Provider Reference 与读取状态 | `HARD`；其他元数据可 UNKNOWN | Source Artifact |
| 空结果、Provider Failure、Blocked、Timeout 可区分 | `HARD` | Fake Failure Matrix |
| Query Privacy、Prompt Injection 与必要 Fetch Security | `HARD` | Security Tests |
| 相关性、时效、冲突保留和可得正文 | 比较 | 固定任务 + 同时段 Live Run |
| Search / Fetch Count、Latency、Token 与可得费用 | 记录；允许 UNKNOWN | Artifact |
| Provider / Model 耦合与维护成本 | 比较 | Adapter Review |

Publisher、发布时间、事件时间、摘要 / 全文范围等字段应尽可能保留；Provider 未返回时明确为
`UNKNOWN`。Phase 3 不把每个来源的全部 Metadata 完整性设为统一淘汰条件，但不得把 UNKNOWN
补造成已知，也不得把只取得摘要说成已读取全文。

### 4.3 最小 Persistence 验证表

| 项目 | 要求 | 证据 |
|---|---|---|
| Account-owned Thread / Message 读取隔离 | `HARD` | 跨 Owner Integration Test |
| 有界 Conversation 可被两个 Runtime 使用 | 必测 | 多轮 Fixture |
| Confirmed Strategy 可按 Owner / Scope 读取 | `HARD` | Repository Fixture |
| 未确认内容不进入 Confirmed Strategy Context | `HARD` | Negative Fixture |
| PostgreSQL / UoW 与候选 Runtime 的接入成本 | 比较 | Prototype Review |

## 5. Task 分解与执行顺序

### P3-T0 — 冻结最小实验合同

1. 记录 Phase 2 Human Decision，更新 Phase 2 / Phase 3 状态；
2. 保留 Phase 1 Baseline，不回写旧 Dataset、Scope 或分母；
3. 冻结一个当前可用的实验模型、两个 Runtime、两个 Research 路径、代表性 Case 与安全预算；
4. 固定 Prompt 语义、输入事实、Tool Contract、Answer / Source Contract 和 Artifact Schema；
5. 用当前 Production Path 跑定向 deterministic Regression，确认 Spike 起点可追溯。

Phase 3 Case 只用于 Capability Decision，不冒充 Phase 4 Acceptance。AQ01、AQ12、AQ19 只有在对应
Research、Conversation、Fetch Security 能力真实接入时才按 FULL 评价；否则保留 DIAGNOSTIC。

**完成标准：** 固定项、允许变化项、代表性 Case、Gate 和 Artifact 已在候选运行前记录。

### P3-T1 — 建立最小 Provider-neutral Harness

Harness 只提供两组对照共同需要的 Contract：

- Runtime Input：Conversation、current-turn Context、Portfolio Context、Confirmed Strategy、Tools、Budget；
- Runtime Result：Answer / Failure、实际使用的 Source、Model / Tool Trace 与可得 Usage；
- Research Result：Query、Source Identity、URL / Provider Reference、读取状态、可得 Metadata 与 Failure；
- Artifact Reporter：固定配置、结果、差异与 `SUPPORTED / PROTOTYPE_GAP /
  ARCHITECTURE_LIMIT / NOT_MEASURED`。

可以使用实验性 Evidence / Claim 结构验证 Source Integrity，但不在 Phase 3 定义最终 Production
Answer Schema 或 Claim-level Citation API。

Fixture 至少覆盖：无 Tool、一次 Tool、多轮 Research、无结果、Provider Failure、Budget Exhausted、
GOOG → MSFT → GOOG、current-turn budget 纠正、冲突来源和恶意网页文本。

**完成标准：** 两个 Runtime 与两个 Research 路径可以消费等价 Fixture，并输出可比较 Artifact；
Harness Failure 与 Candidate Failure 可区分。

### P3-T2 — Current Runtime 多轮候选

在 Spike 层实现最小 Application-owned Loop，不修改生产 `InvestmentAgent`：

```text
Trusted Context
→ Model Action
→ validate + budget check
→ execute allowed tools
→ append observation
→ Model Action / Final
→ answer + source validation
```

只实现验证候选所需的继续 / 停止、Tool Validation、Failure Observation、调用预算和 Final Validation。
Streaming、Durable Resume、完整 Cancellation Lifecycle、Production Logging 与 UI Progress 不进入本 Task。

**完成标准：** 固定 Fake Fixture 通过；使用固定实验模型完成最小 Live Smoke；Production 行为不变。

### P3-T3 — Pydantic AI 候选

使用锁定版本的最小 Pydantic AI 安装，验证：

- Agent Loop、Tool Validation、History、Structured Output、Usage Limit 与 Trace；
- 使用等价的 Model、Prompt 语义、输入事实、Tool Contract、Budget 和测试场景；
- Pydantic AI 原生 Alibaba / OpenAI-compatible Provider 集成的实际兼容性；
- 如原生集成不足，评估薄 Bridge 到现有 Provider-neutral Adapter 的可行性和维护成本；
- Framework History 只负责 Runtime Message，不成为 Conversation、Strategy 或 Portfolio Truth。

不同框架不要求内部 Message、Tool Event 或 Request Payload Hash 完全一致。报告必须记录这些差异，
说明它们是否可能影响 Tool Selection、Structured Output、Usage 或 Latency；不得为追求 Payload 一致
而重写 Pydantic AI 的核心运行方式。

**完成标准：** 与 Current Runtime 使用等价输入和场景完成对照；原生 Provider 能力、可选 Bridge
成本和未完成的 Production Gap 分开记录。

### P3-T4 — Research Provider 对照

只比较两条路径：

**A. Alibaba Native Research**

- 验证当前实验 Model、Region、Endpoint 的 Search / Fetch 或等价能力；
- 记录 Search 是否实际执行、Source Identity、URL / Citation、Failure、Usage 和可得费用；
- Provider-managed Search 只接收 Application 构造的 Public-only Research Request，不携带 Portfolio、
  Strategy 或私有 Conversation。

若固定实验模型在当前 Region / Endpoint 下不支持所需 Native Research 能力，记录实际限制，不为
完成对照而修改 Runtime 实验的固定模型。确有必要时，可以使用另一个模型执行隔离的 Native
Research Capability Test，但必须明确记录模型差异；其结果不得用于同模型条件下的 Research 质量
或 Runtime 性能比较，也不得被归因于 Research 实现方式本身。

**B. Application-owned Research**

- 最多选择一个实际可运行的 Search Provider；Page Fetch 可以使用该 Provider 的能力，也可以使用
  PositionPilot 独立的受控 Fetch Prototype，不因此扩展为多个 Research Provider 的横向比较；
- Search 与 Fetch 保持可观察，结果归一化到同一 Research Result；
- Fetch Prototype 只实现必要安全边界：允许的网络 Scheme、拒绝 loopback / private / link-local、
  Redirect 重新校验、Timeout / Size Limit，以及外部文本无指令或状态写入权限；
- Query 只包含公开 ticker、公司、事件与时间窗口。

两条路径使用相同研究任务和时间窗口。真实 Web 结果用于覆盖、时效、来源和体验比较；Runtime
行为比较使用冻结 Fixture。Provider 缺失的非关键 Metadata 明确为 UNKNOWN，不为补齐字段扩展抓取。

**完成标准：** 两条路径各有受控 Live Evidence、Failure Fixture、安全测试和简明比较结论；若
Application-owned 候选不可运行，记录可复现原因，不再追加第二个候选。

### P3-T5 — 最小 Conversation / Confirmed Strategy Persistence Prototype

只验证候选 Runtime 能否接入 PositionPilot-owned State：

- Account-owned `Thread` 与有序 `Message` 可以跨两个请求恢复最小 Conversation；
- Repository 按当前 Account 读取少量已确认 Strategy Fixture，并保留 scope / source / confirmed 状态；
- 未确认文本或模型建议不会进入 Confirmed Strategy Context；
- 两个 Account 不能读取彼此的 Conversation 或 Strategy；
- Current Runtime 与 Pydantic AI 都通过相同 Application Boundary 取得 Context。

Prototype 优先使用显式 `SPIKE_DATABASE_URL` / 临时 PostgreSQL Schema，缺失时拒绝运行，禁止回退到
Application `DATABASE_URL`、`get_settings()` 或 Repository `.env`。不创建 Production Migration、
Public API 或最终 Schema。

本 Task 不实现 StrategyCandidate 状态机、确认写入、版本替代 / 失效、删除生命周期、并发确认、
幂等重试、Durable Run 或 Production Repository。这些进入 Phase 4 Implementation Plan。

**完成标准：** Conversation、Confirmed Strategy 和 Account Ownership 的最小读取 / 注入路径在两个
Runtime 上可验证；跨 Owner 与未确认 Strategy Negative Fixture 通过。

### P3-T6 — AQ05 / AQ06 Execution UNKNOWN 验证

不设计完整 Execution Fact / Fractional Share Domain Contract，只冻结当前问题所需边界：

- Account Cash、current-turn budget、Quote 和 `budget < one-share quote` 保持不同事实；
- Broker / Ticker Fractional Eligibility 与当前 Account Permission 未经权威来源确认时保持 UNKNOWN；
- UNKNOWN 时可以给整股 / 碎股条件分支，但不能输出确定可买数量、确定执行限制或“提高预算”的建议；
- Public Research 可以支持公开 Broker / Ticker 规则，不能冒充当前 Account 权限；
- Provider Failure 与 No Result 不得被改写成已确认规则。

**完成标准：** AQ05 / AQ06 的固定 Fixture 不触发对应 Critical Gate。完整 Broker、Account、Minimum
Notional / Quantity、Precision、Rounding 与 Execution Constraints 设计移至后续独立任务。

### P3-T7 — 固定模型与 Provider Compatibility Smoke

Phase 3 只使用 P3-T0 冻结的一个当前可用实验模型，不进行模型排名或 Challenger 对照。该模型用于：

- 两个 Runtime 的最小 Live Smoke；
- 两条 Research 路径的实际能力验证；
- Structured Output、Tool Calling、Usage / Failure Metadata 的 Provider Compatibility 检查。

实验报告明确区分实验模型与当前 Production Default。模型切换能力继续由现有 Provider-neutral
Adapter Contract 保证；正式更换默认模型时再执行独立 Model Eval 和 Human Review。

**完成标准：** 固定模型的实际配置、Region / Endpoint、成功 / 失败和可得 Usage 已记录；没有模型横评。

### P3-T8 — 代表性组合验证与预算估算

用通过 `HARD` Gate 的候选组合运行代表性 Case：

- AQ01 / AQ03：关键前提 Research 与已有证据足够时停止；
- AQ05 / AQ06：Budget、Cash 与 Execution UNKNOWN；
- AQ12：Conversation 恢复；
- AQ17a / AQ17b：空结果与 Provider Failure；
- AQ19：External Content / Prompt Injection；
- AQ08 或 AQ20：Portfolio-only / No-tool Regression。

这不是 Phase 4 Acceptance，不要求运行完整 4A Target FULL、全部 Repeat 或 unseen Set。报告记录
Capability Coverage、Critical Failure、Request Failure、Model / Tool / Search / Fetch Count、Latency、
Token 和可得费用，并据此给出 Phase 4 初始预算区间或 Ceiling 建议。缺少 Cost 或慢请求样本时保持
`NOT_MEASURED`，列为 Phase 4 风险，不为补齐统计扩大 Phase 3。

**完成标准：** 形成足以判断组合可行性的代表性证据和预算估算；No-go 也是有效结论。

### P3-T9 — Review 与 Phase 4 Decision Proposal

1. Automated Review 检查实验公平性、Source / Security、Owner / State Boundary 与证据完整性；
2. 修复 Review Finding 后重跑受影响的定向测试；
3. 形成简明 Phase 3 Report：Runtime 对照、Research 对照、Persistence 验证、AQ05 / AQ06、
   Provider Smoke、预算估算、已知 `PROTOTYPE_GAP / NOT_MEASURED`；
4. 形成 Phase 4 Decision Proposal：推荐 / No-go、理由、Trade-off、需要在 Phase 4 完成的工作；
5. 暂停并等待 Human Review。批准后再创建 / 更新必要 ADR 和 Phase 4 Implementation Plan。

**完成标准：** 证据足以支持技术路线决策；Human Review 前没有 Production Runtime、Provider、
Schema、API 或 Security Boundary 替换。

## 6. 测试与验证矩阵

| 范围 | 最小检查 | 不要求 |
|---|---|---|
| Harness / Runtime | Fake 0 / 1 / 2+ Tool、Failure、Budget、History、Source Validation | 完整 Production Runtime Test Suite |
| Research | Fake Failure、Query Privacy、Prompt Injection、必要 Fetch Security、每条路径 Live Smoke | 大规模 Provider Benchmark |
| Persistence | 临时 PostgreSQL、跨 Owner、Conversation 恢复、Confirmed / Unconfirmed Strategy | Candidate 状态机、并发 / 删除 / Migration |
| AQ05 / AQ06 | 固定 Fixture 与 Critical Gate | 完整 Execution Constraints Model |
| Integration | 代表性 Case、定向 Regression、Artifact 完整性 | Phase 4 全量 Acceptance / unseen |

Phase 3 实现期间运行受影响文件的 `ruff check`、`mypy` 和 `pytest`；修改共享 LLM / Evaluation
Contract 时回归对应现有测试。Online Test 必须显式 opt-in，记录 Provider / Model / Region / Run ID，
不作为普通 CI Gate。完成前运行 `git diff --check`。

本次计划修订只修改 Markdown，不运行上述 Phase 3 检查。

## 7. Git 边界

只有用户明确开始 Phase 3 后才创建 Branch 和 Atomic Commits。本计划修订不创建 Commit。
Phase 3 完成后不自动合并 `main`、不 Push、不创建 Release。

## 8. Phase 3 Done Criteria

**本次执行结果：** 因缺少显式 Provider Credential、Region / Endpoint 和 `SPIKE_DATABASE_URL`，执行
按第 10 节停止条件以 `NO_GO_PENDING_LIVE_EVIDENCE` 结束。以下 Done Criteria **尚未全部满足**；
尤其是 Runtime / Research Live Smoke、PostgreSQL Integration、代表性组合与预算估算仍为
`NOT_MEASURED`。因此本状态不授权进入 Phase 4，只提交 Human Review 与最小补证请求。

Phase 3 同时满足以下条件即可进入 Human Review，不要求提前完成 Phase 4：

- Current Runtime 与 Pydantic AI 已用等价语义、事实、Tool、Budget 和代表性场景完成对照；
- Pydantic AI 原生 Provider 能力及必要 Bridge 的维护成本已记录；
- Alibaba Native Research 与最多一个 Application-owned Research 候选完成受控对照；
- 推荐候选通过 Security、Ownership、Source Integrity、Mutation Boundary 与 Phase 2 Critical Gate；
- Conversation、Confirmed Strategy 与 Account Ownership 的最小 Persistence 接线已验证；
- AQ05 / AQ06 的 UNKNOWN 和来源权威边界已验证；
- 一个固定实验模型完成必要 Provider Compatibility Smoke；没有执行模型横评；
- 代表性组合测试、可重复 Artifact 与初始预算估算已形成；
- `ARCHITECTURE_LIMIT`、`PROTOTYPE_GAP` 与 `NOT_MEASURED` 已分开记录；
- Automated Review Finding 已处理，Phase 3 Report 与 Phase 4 Decision Proposal 已完成；
- Human 未批准前不进入 Phase 4，不修改 Production Runtime / Provider / Schema / API。

## 9. 推迟到 Phase 4 或后续独立任务

以下工作不属于 Phase 3 Done Criteria：

- Production Thread / Message / Run Schema、Alembic Migration、Public API 和前端交互；
- StrategyCandidate、唯一 Pending Mutation、确认写入、版本替代 / 失效、删除、并发和幂等；
- Production History 裁剪、Retention、Physical Deletion、Durable Resume、Streaming 与 Progress UI；
- 最终 Answer / Claim-level Citation Public Contract 与完整 Source Metadata Policy；
- 精确 Production Budget、Latency / Cost SLO、完整 Failure Code 和 Observability；
- Phase 4A / 4B 完整 Dataset、Repeat、unseen、连续 Ask 与 Human Acceptance；
- 完整 Broker / Account Execution Constraints 和 Fractional Share Domain 设计；
- 正式 Model / Provider 横向比较或默认模型切换。

## 10. 失败与停止条件

出现以下情况时记录 No-go 或 `NOT_MEASURED`，不扩大 Phase 3：

- 候选需要新的 Database、Queue、Durable Workflow、Broker Connection、Multi-Agent 或 LangGraph；
- Framework / Provider 必须拥有 Portfolio、Strategy、Confirmation 或 Owner 语义；
- Research 无法满足 Source Integrity、Query Privacy 或必要 Fetch Security；
- 候选触发 Security、Ownership、Mutation 或 Phase 2 Critical Gate Failure；
- Credential、Region 或 Quota 阻止 Live Evidence，且无法在当前授权范围解决；
- 为实现公平对照必须大量改写框架内部表示，失去真实接入意义。

候选失败可以成为有效结论。只有引入新核心基础设施、修改产品语义或扩大 Public API / Security
边界时才重新提交 Human Review；普通 Spike Bug 按计划修复并重测。

## 11. 计划后的下一步

Phase 3 Human Acceptance 后另行生成 Phase 4 Implementation Plan，顺序保持：

```text
4A Conversation + Current-turn Context + Multi-round Research
→ 固定 4A Eval 与 Critical Gate
→ 4B Confirmed Strategy + Pending Mutation
→ 连续 Ask Eval 与完整讨论链
```

Phase 4 根据本次 Decision Proposal 完成 Production State、API、Migration、安全细节和完整验收，
不把这些实现要求反向塞回 Phase 3。Long-term Memory 继续留到 Phase 5，除非新的独立需求和证据
触发对应 Human Review。
