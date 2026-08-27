# M6 — Evaluation & V1 Hardening 执行计划

## 1. 状态与目标

**Status:** IN PROGRESS — Offline Evaluation Slice complete；Real-model Eval blocked

M6 将 M3～M5 已积累的 Behavioral Eval Cases 整理为可重复运行的 V1 Evaluation Dataset，并用 Evaluation 证据驱动必要的可靠性修复。

M6 遵循 **Eval First / Failure-driven Hardening**：Production Code、Prompt、Logging 或架构修改必须由 Evaluation Failure、已知 Failure Mode 或 Automated Review Finding 驱动，不预先实现“可能有用”的加固。

## 2. 当前基线与缺口

- pytest 已同时承载默认自动测试与 Opt-in Real-model Behavioral Eval，继续作为 M6 的 Evaluation Execution Engine。
- M6 启动时继承 22 个固定 Behavioral Cases，已覆盖 Portfolio Facts、Quote、History、News、Market Context、部分对照场景和 Failure Handling。
- Tool Trace、Source Validation、Structured Answer Repair 与基础指标已存在，但 Dataset Definition、Fixtures、Execution / Reporting 职责仍较集中。
- M6 启动基线为 337 passed、36 skipped；22 个真实模型 Cases 因未配置 `LLM_API_KEY` 跳过，尚不能作为真实模型行为通过证据。
- History / News / Market Context 的 empty、failure 与 stale Contract 已有 Unit / Agent Test Evidence；仅在模型行为或实际 Failure 证明必要时补充 Real-model Case。
- M6 启动时的输出缺少 Dataset Version、运行元数据、聚合结果和正式 Human Review 记录。

## 3. Acceptance Criteria

- V1 Evaluation Dataset 有明确版本，并可通过 pytest 重复运行。
- Coverage Matrix 将 V1 Requirement 映射到具体 Eval Case，主要 V1 场景不存在未解释的覆盖缺口。
- Controlled Contrast Cases 尽量只改变一个变量，其余 Question、Portfolio 和 Fixtures 保持一致。
- Automated Grounding Contract 与 Human Factual Grounding 的验收边界明确。
- Hard Contract Failure 与 Quality Signal 分开记录和汇总。
- 全量 Real-model Eval 至少运行 1 次；少量代表性 Contrast Case、历史不稳定 Case 或 Repair Case 重复运行 3 次。
- Offline Contract Tests、已配置质量检查和必要 Integration Tests 通过。
- Online Smoke 作为 Human Acceptance Evidence 完成记录，不作为受第三方服务状态影响的常规 CI Gate。
- Critical / High Automated Review Findings 已解决，Review 后重新验证受影响行为。
- 已知限制明确记录，`PROJECT.md` 的 V1 Success Criteria 有对应 Evaluation Evidence。
- Human Acceptance 通过后才可合并到 `main`。

## 4. Evaluation Boundary

### Automated Grounding Contract

确定性检查负责验证：

- Tool 名称、参数、调用预算与去重；
- Provider Result、Failure Status 和 `OK` / `DEGRADED` 映射；
- `source_refs` 只能引用本轮成功取得的同类型、同 ticker Context；
- Portfolio、Cash、Position Type 和代码派生金融事实保持结构化；
- Structured Answer 最多 Repair 一次，失败后返回明确 Request Failure。

### Human Factual Grounding

Human Review 负责验证：

- Answer 是否准确使用 Portfolio 与 Tool Facts；
- 是否正确区分 `LONG_TERM` / `SWING`；
- 是否自然区分 `FACT`、`INFERENCE` 和 `UNKNOWN`；
- News 是否保持来源归因，Market Regime 是否保持 SPY Proxy 与 V1 Heuristic 边界；
- 是否虚构当前事实、最新财报、技术指标、交易能力或确定性因果。

`source_refs` 合法只证明来源声明满足 Application Contract，不代表 Answer 中每个 Claim 都正确，也不等价于逐 Claim Citation。

## 5. Coverage Matrix

Coverage Matrix 是 M6 判断是否需要新增 Case 的依据。新增 Case 数量由 Requirement、已知 Failure 或实际 Evaluation Failure 决定，预计约 8～10 个，但数量不作为 Done Criteria；不为矩阵对称性强行补齐 empty / failure / stale Cases。

| V1 Requirement | 当前 Case / Evidence | M6 处理 |
|---|---|---|
| Entry / Add Position | `market_context_normal`、Cash / Position Type 对照 | 增加直接对应 V1 Success Criteria 的 Controlled Contrast |
| Market Drop Explanation | `drop_reason_unknown` | 保留 News attribution、未知跌幅与条件式因果检查 |
| Post-Earnings Holding | `post_earnings_unknown` | 验证 Earnings 不可用时保持 `UNKNOWN` |
| Position Reduction | `position_reduction_rule_check` | 增加自由判断减仓，与既定规则核对形成 Contrast |
| Available Cash | `low_cash_personalization` / `high_cash_personalization` | 校验只改变 Cash，其余输入一致 |
| Position Type | `long_term_position_personalization` / `swing_position_personalization` | 校验只改变 Position Type，其余输入一致 |
| Market Regime | `market_context_normal` / `market_context_high_stress` | 校验只改变 Regime Fixture，其余输入一致 |
| Portfolio-only / No-tool | `cash_only_no_tool`、`positions_only_no_tool`、`missing_position_is_absence` | 保留最小充分 Context 检查 |
| Quote / Multi-ticker | `current_price_without_position`、`compare_two_quotes` | 保留参数、去重、预算与 Source 检查 |
| Price History | `recent_price_history`；Unit / Agent Tests 已覆盖 Failure Taxonomy | 仅在 Requirement 或实际 Failure 证明必要时增加 Behavioral Case |
| Recent News | `recent_news`；Unit / Agent Tests 已覆盖空结果与 Provider Failure | 仅在 Requirement 或实际 Failure 证明必要时增加 Behavioral Case |
| Market Context Failure | `market_context_provider_failure`；Unit Tests 已覆盖 `NO_DATA` / stale | 不为状态对称性重复增加 Behavioral Case |
| Missing / Provider Failure | `quote_no_data`、`quote_provider_failure` | 保持状态区分并覆盖其他稳定 Context |
| Source Grounding / Repair | Diagnostics Unit Tests 与全部 Behavioral Cases | 汇总 Retrieved / Declared Source、Repair 与 Human Grounding |
| V1 Success Criteria | M6 已增加直接入口 Case 与有界历史 BUY Facts | 保留真实模型 Factual Grounding 缺口，直到 Real-model Eval 与 Human Review 完成 |

## 6. Failure 与质量信号

### Hard Contract Failure

- 声明未在本轮成功取得、类型或 ticker 不匹配的 Source；
- Tool Call 突破预算或绕过参数校验；
- Response Status 错误；
- 混淆 Provider Failure、`NO_DATA`、`NO_NEWS_FOUND` 或正常空结果；
- 将缺失的当前事实、财报、Market Regime 或其他 `UNKNOWN` 补造成事实；
- Repair 后仍不满足 Structured Answer Contract，却返回成功结果。

Hard Failure 必须先完成 Root Cause Analysis，区分 Dataset、Fixture、Provider、Application Contract、Prompt 或模型行为，再决定修复位置；不预设通过新增 Guard 修复。未解决的 Hard Failure 阻断 M6 Acceptance。

### Quality Signal

- Structured Answer 使用 Repair；
- 同一 Controlled Contrast 的 Tool Selection 或回答重点发生路由波动；
- Context Over-call、Source 漏报、Latency 异常或回答差异不足；
- Human Review 发现表达不清、归因不足或条件式分析质量不稳定。

Quality Signal 必须记录和分析；只有形成稳定 Failure Mode、违反 Acceptance Criteria 或被 Reviewer 判定为 Critical / High 时，才驱动 Production 修改。

## 7. 执行顺序

```text
T0 M6 Plan + Baseline Freeze
  ↓
T1 Dataset Definition / Fixtures / Execution & Reporting Boundary
  ↓
T2 Coverage Matrix + Controlled Contrast Cases
  ↓
T3 Offline Evaluation Baseline + Real-model Evaluation
  ↓
T4 Failure Triage
  ↓ only evidence-backed changes
T5 Failure-driven Hardening + Targeted Regression Tests
  ↓
T6 Full Checks → Automated Review → Fix → Re-check
  ↓
Evaluation Evidence + Human Acceptance
```

### T0 — Plan 与基线冻结

- 开始实现前检查 Git 状态，并使用独立 M6 Branch。
- M6 Commits 不混入与本 Milestone 无关的工作区修改。
- 记录当前 Test、Behavioral Case、Provider Capability、Prompt / Tool Contract 与已知 Skip 基线。
- 在 Plan 获批后再更新 Milestone 状态，不在计划审阅阶段开始实现。

### T1 — Evaluation Dataset 边界

- 为 Dataset 增加稳定版本与 Case Metadata。
- 合理分离 Dataset Definition、Fixtures、Execution / Reporting 职责，不固定具体文件结构，也不为了拆文件而拆文件。
- pytest 继续负责参数化、选择、断言、Skip Gate 和失败报告。
- Runner / Reporter 只负责轻量运行编排、指标聚合和结果输出，不重新实现测试发现、断言或测试框架。

### T2 — Coverage 与 Controlled Contrast

- 建立可维护的 V1 Requirement → Eval Case 映射。
- 先识别未覆盖 Requirement，再补充最小 Case。
- Cash、Position Type、Market Regime 等 Contrast 尽量只改变一个变量。
- 每个新增 Case 明确 Automated Assertions 与 Human Checks；只有存在 Case-specific Known Limitation 时才记录，不要求所有 Case 填写。

### T3 — Evaluation Baseline

- 运行全部 Offline Tests，形成确定性 Contract Baseline。
- 全量 Real-model Eval 至少运行 1 次。
- 只对少量代表性 Contrast、历史不稳定或实际触发 Repair 的 Cases 重复运行 3 次。
- 报告只使用 Evaluation 层已有数据；缺少的字段保持未提供，不为补齐报告字段增加 Production Instrumentation。
- 优先记录 Dataset Version、Model / Provider、Git Revision、Tool Trace、Status、Retrieved / Declared Source、Repair、可取得的 Latency 与 Human Review 内容。
- 聚合指标分别记录 `repair_count`、`cases_with_repair` 和对应比例，避免用单 Case 0/1 值表示全局 Repair Rate。

### T4 — Failure Triage

- 将结果分类为 Hard Contract Failure、Quality Signal、Provider / Environment Blocker 或已知限制。
- 判断 Failure 属于 Dataset、Fixture、Production Contract、Prompt、Provider Adapter、Logging 还是自然语言质量。
- Hard Failure 先完成 Root Cause Analysis，再选择最小且与根因一致的修复。
- 不用 Production Guard 掩盖 Fixture 或 Evaluation 错误，也不把 Human Rubric 伪装成自动保证。

### T5 — Failure-driven Hardening

- 只实现 T4 已确认或 Automated Review 新发现的必要修改。
- 每项 Production Code、Prompt 或 Logging 修改都关联具体 Failure Evidence 与 Regression Test。
- `investment_agent.py` 不主动大拆分；只允许由 Evaluation、Testability 或 Review Finding 驱动的 Contract-preserving 局部重构。
- 若证据要求修改 Provider、Model、Market Regime、公共 API、核心 Domain 或重要 Infrastructure，先进入 Human Review Gate。

### T6 — Review 与收口

- 运行默认 pytest、相关 Integration Tests、Ruff format / lint、mypy strict、`uv lock --check`、Alembic head / history 与 `git diff --check`。
- 执行 Automated Review，修复 Critical / High Findings，并重新运行受影响检查。
- 在可用环境执行 PostgreSQL、Alpaca Market / News 与真实 Agent Online Smoke，作为 Human Acceptance Evidence；第三方不可用时记录外部 Blocker，不将其配置为常规 CI Gate。
- 更新 Evaluation README、M6 Completion Summary、已知限制及必要的 Architecture / Engineering Note。
- Human Acceptance 后按 Repository Git Workflow 合并到本地 `main`，不自动 Push 或删除 Branch。

## 8. Non-Goals

- 新增 Earnings、Fundamentals、Asset Metadata、Technical Analysis 或交易能力。
- 修改 SPY Market Regime 方法、阈值或代理范围。
- 更换或增加 LLM / Market / News Provider。
- 建设公开金融 Benchmark、历史收益 Backtest、完整 LLM-as-a-Judge 或独立 Evaluation Platform。
- 为 Token / API Cost 提前扩展 Provider Contract；只有实际 Model Selection 需要时再评估。
- 引入新的 Agent、Database、Cache、Queue、Observability Platform 或其他 Infrastructure。
- 未经 Failure Evidence 的 Prompt 调优、Logging 扩展或 Production 重构。

## 9. Human Review Gate

以下情况暂停对应实现并提交 Decision Proposal：

- Evaluation 证据要求改变产品语义、公共 API、核心金融计算或 Market Regime；
- 选择或更换 Model / Provider；
- 引入新 Infrastructure 或改变 Single Agent 架构；
- 修改 Security、Credential 或敏感数据处理方式；
- M6 完成并准备合并到 `main`。

## 10. 当前执行证据

- Dataset `1.0`、Coverage Matrix、24 个 Behavioral Cases、Controlled Contrast 与轻量 Reporter 已完成。
- Coverage Audit 发现历史买入位置未进入 Agent Context；RCA 后以同一 Ledger Read 的有界 BUY Facts 修复，不新增 Tool、Source Type、预算或公共 API。
- Offline Gate：348 passed、38 skipped；Ruff、mypy、lock、Alembic 与 diff 检查通过。
- Automated Review：无 Critical / High / Medium Finding。
- 全量 Real-model Eval 已尝试；当前进程未配置 `LLM_API_KEY`，24 个 Cases 跳过，不作为 Behavioral Pass。
- Online Smoke 已尝试；当前进程未配置 Alpaca / LLM Credential，4 项跳过；PostgreSQL Integration 同样因未配置 `TEST_DATABASE_URL` 跳过。
- 待完成：全量 Real-model 运行、代表性 Cases 三次重复、Human Factual Grounding 与 Online Smoke Evidence。
