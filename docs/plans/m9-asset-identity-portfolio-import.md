# M9 Asset Identity & Portfolio Import 执行计划

## 1. Milestone 目标

M9 通过 Provider 验证的 Asset Identity 与可人工确认的 Text / Screenshot Import，降低用户
录入 Portfolio Opening State 的成本，目标 Release 为 `v1.1.0`。

唯一允许的产品闭环是：

```text
Text / Screenshot
        ↓ Recognition（只产生建议）
Provider-neutral Structured Import Draft
        ↓ Asset Metadata Search / Exact Validation
canonical symbol + Missing / Invalid / Confidence Review Signal
        ↓ Human Review / Edit / Confirmation
确定的 canonical symbol + shares + average_cost + optional position_type
        ↓ Asset Revalidation + deterministic Domain Validation
M8 one-time Opening State Command
        ↓ atomic write
Portfolio Opening State
```

M9 不建设本地完整 Asset Master，不把 Recognition Confidence 当作 Domain Truth，也不实现
已初始化 Portfolio 与外部账户之间的增量 Import、Sync 或 Reconciliation。

## 2. 已批准的产品与真实性边界

### D1 — Canonical Symbol 是 M9 Asset Identity

- Asset Identity 以 Asset Metadata Provider 验证后的 `canonical_symbol` 表示。
- Portfolio Domain 现有 `ticker` 字段承载 canonical symbol；M9 不仅通过 uppercase / regex
  把任意用户输入声明为真实 Asset。
- M9 只规范化前端 Asset Selector 与写入校验实际需要的 `canonical_symbol`、`display_name` 与
  `exchange`。Provider exact validation 成功只表示能够识别并规范化 symbol，不推断未明确
  提供的 active / inactive 状态；不为 `tradable`、`fractionable`、alias、class shares、source
  timestamp 等未来字段建设通用 Metadata Model。
- 不创建完整本地 Asset Master、Security Master 同步任务或 Symbol Mapping Database。
- Provider-specific JSON、枚举和错误只存在于 Integration Adapter。

### D2 — Import 只初始化 Opening State

- 最终写入复用 M8 `InitializeOpeningPositionsCommand` 与同一 User Row Lock。
- 只有 Opening Position、Transaction 与 Cash Event 全部为空时允许提交 Import。
- Portfolio 创建后但仍满足上述 Gate 时，可以继续完成尚未写入的 Opening State；一旦 Gate
  封闭，Import 必须明确失败，不能尝试 merge、overwrite、diff 或 reconcile。
- Import 不创建 Transaction，不影响 Cash，不产生经济 sequence，也不伪造历史 BUY。

### D3 — Confidence 只服务 Human Review

- Recognition Provider 可以返回数值或枚举 Confidence，但 Application 只把它规范化为
  Provider-neutral Review Signal。
- Confidence 不进入 `OpeningPosition`、Transaction、Ledger 或 Portfolio Replay。
- 高 Confidence 不能绕过 Human Confirmation、Asset Validation、必填字段检查或 Domain
  Validation；低 Confidence 也不能单独否决一个已被用户修正、确认且验证通过的确定字段。
- `MISSING` / `INVALID` 是确定性字段状态，与 Confidence Review Signal 分开表达；缺失或
  非法字段必须修正后才能提交。

### D4 — Provider / Capability Evaluation 先于实现

- Asset Metadata Provider 与 Vision / OCR Capability 分别评估，不预设由同一 Provider 提供。
- Phase 0 是短 Spike，只回答 M9 能否开始实现所需的最小问题，不建设长期 Provider 研究矩阵。
- Provider / Vision 选型与图片隐私边界属于实现前 Human Review Gate；批准后即进入实现。
- Public API、Upload Limit 与 Error Schema 按既有 API 风格实现并测试，只要不改变既有 Domain、
  Database 或 M9 Scope，不再单独暂停等待批准。

## 3. 当前 Repository 基线与实现差距

### 可复用能力

- `domain/portfolio.py` 已提供 immutable `OpeningPosition`、`PositionType.UNSPECIFIED`、Decimal
  Validation 与 deterministic Replay。
- `PortfolioService.initialize_opening_positions()` 已在 User Lock 下实现 one-time Gate、批量
  duplicate 检查、全量重放与原子写入。
- Session-derived `/v1/portfolio` 和 `/v1/portfolio/opening-positions` 已确保 Ownership；
  Browser 不能选择 User ID。
- M8 Frontend 已有手工 Opening Position Draft、逐字段错误、安全 DOM 与 Network Ambiguity
  边界。
- Market / News / LLM Integration 已示范 Provider-neutral Domain/Application Contract、Adapter
  Mapping、明确 Failure Status 与 Fake Provider Unit Tests。

### 主要差距

- 当前 `normalize_ticker()` 只做字符串格式规范化，不证明 Asset 真实存在，也不支持公司名称搜索
  或非唯一输入的候选选择。
- 尚无 Asset Metadata Domain Result、Application Service、Provider Protocol、Adapter、Config、
  API 或 UI Search / Exact Validation。
- 尚无 Text / Screenshot Recognition Contract、Upload Boundary、Draft Schema、Provider Adapter
  或图片隐私边界。
- 当前 Opening Position 写入不执行 Provider-backed Asset Validation。
- 当前 Browser Draft 没有 raw input、field status、review signal、candidate selection 与 explicit
  confirmation state。

## 4. Phase 0 — Short Capability Spike

Phase 0 必须先完成，但它只使用少量固定 Fixture 快速验证候选方案。选型和图片隐私边界获批后
立即开始实现；其余能力等出现真实需求再评估。

### E1 — Asset Metadata 最小问题

使用固定的美股 / 美国 ETF Fixture，只回答：

- 能否按 symbol / company name 搜索并返回可选择候选；
- 能否对提交的 symbol 做 exact validation 并返回 canonical symbol；
- 美股与美国 ETF 覆盖是否足以支持 M9；
- API 是否足够稳定，成本是否可接受。

不为 alias、class shares、delisted 语义、分页、source timestamp、完整许可矩阵或未来 Asset
字段做专项研究；如果固定 Fixture 暴露真实阻塞，再针对该问题补充验证。

### E2 — Vision / OCR 最小问题

使用无真实敏感信息的固定 Text / Screenshot Fixture，只回答：

- 能否识别 ticker、shares 与 average cost；
- 能否稳定返回 M9 所需的 Structured Draft；
- 图片是否不会被 Provider 默认长期保存；
- 成本是否可接受。

Evaluation 不比较“能否直接写入”，因为任何 Provider 都只能生成 Draft；不研究与当前 M9
Fixture 无关的 Region、Training、Confidence 统计模型或全格式覆盖。

### E3 — Spike 输出与一次性选型 Gate

- 一份简短 Spike 结果：逐项回答 E1 / E2 的八个问题；
- 推荐的 Asset Metadata Provider、Vision / OCR Capability 与可接受成本；
- 图片默认不长期保存的隐私边界；
- 简短 ADR：记录最终选型、理由和重新考虑条件。

Human Review 批准后立即进入 Phase 1。若 Vision 不能满足最小识别、Structured Output 或图片
保存边界，M9 缩减为 `Asset Identity + Text Import`，不把 Spike 延长成 Provider 研究项目。

## 5. 目标 Provider-neutral Contracts

以下只约束最小语义。具体 Pydantic 字段与 URL 在实现时按现有 API 风格确定，无需单独 Review。

### Asset Metadata

```text
AssetSearchQuery(query, limit)
        ↓ AssetMetadataService
AssetMetadataProvider.search()
        ↓
AssetSearchResult(status, candidates[])

AssetValidationQuery(symbol)
        ↓ AssetMetadataService
AssetMetadataProvider.get_exact()
        ↓
AssetValidationResult(status, asset?)

AssetIdentity
├── canonical_symbol
├── display_name
└── exchange
```

这不是通用证券主数据模型。Provider-specific Metadata 与诊断信息留在 Adapter；Search Candidate
只用于选择，最终写入必须执行 exact validation，不能把 Browser Candidate 直接视为有效 Asset。

### Recognition Draft

```text
RecognitionInput(TEXT | SCREENSHOT)
        ↓ RecognitionService
RecognitionProvider.recognize()
        ↓ provider-specific mapping
ImportDraft
├── draft rows[]
│   ├── raw / suggested symbol
│   ├── shares
│   ├── average_cost
│   ├── optional position_type
│   ├── field status: PRESENT | MISSING | INVALID | AMBIGUOUS
│   └── optional confidence review signal
├── warnings[]
└── no persistent write capability
```

Draft 只存在于当前 Browser / Request 生命周期，除非后续 Human Review 明确批准持久 Draft；
默认不持久化原始图片、OCR 文本、Confidence 或 Provider Payload。

### Confirmation / Write

确认请求只包含用户最终确认的确定字段与 canonical symbol，不包含能够影响 Domain 决策的
Confidence。Application 使用两阶段 Use Case；外部 Provider 调用不得发生在持有 User 数据库
行锁期间：

```text
require Session Ownership
→ optional fast Opening State eligibility read
→ exact Asset Validation for every canonical symbol（数据库事务外）
→ normalize Position Type / Decimal
→ reject duplicate (canonical_symbol, position_type)
→ InitializeOpeningPositionsCommand acquires User Row Lock
→ recheck Opening State Gate under lock
→ deterministic replay
→ atomic commit
```

Asset Provider Failure 时不得跳过验证后写入，也不得把 Browser Cache 当作后端真实性证明。
Validation 与取得行锁之间若出现并发 Ledger Write，锁内 Gate 必须拒绝本次 Import；系统不尝试
merge 或自动重试。

## 6. Public API 与 UI 实现方向

Codex 按现有 Session-derived API、Schema 和错误处理风格实现以下最小 Surface，无需为 URL、
Upload Limit 或 Error Schema 单独暂停 Review：

- Asset Search：Session-authenticated read endpoint，接收 bounded query / limit，返回
  Provider-neutral candidates 与 status。
- Opening Import Recognition：Session-authenticated、无写入能力的 Text / Screenshot endpoint，
  返回 Import Draft；Screenshot 使用明确 MIME / size limits，不接受 URL 抓取。
- Opening State Commit：优先复用现有 `POST /v1/portfolio` 与
  `POST /v1/portfolio/opening-positions`，在 Application Boundary 增加 exact Asset Validation；
  不新增 Import-specific Write Endpoint，除非 Human Review 发现现有原子 Contract 无法表达。

Browser Flow：

```text
Portfolio Setup / still-open Opening State
→ choose Manual | Paste Text | Upload Screenshot
→ recognize to editable Draft
→ resolve ambiguous asset candidates
→ show missing / invalid fields and confidence review cues
→ user explicitly confirms
→ backend revalidates assets and writes once
→ refresh deterministic Snapshot + read-only Opening Records
```

- 用户可以忽略 Confidence 并直接修正字段；UI 不显示“Confidence 通过所以可安全写入”。
- Recognition / Search Failure 保留 Draft 与用户编辑能力时，仍不得在缺少后端 Asset Validation
  的情况下写入。
- Upload、Recognition 与 Asset Search 是可重试 Read-like Processing；Opening State POST 仍沿用
  M8 Network Ambiguity 规则，不自动 Retry。
- 动态文本继续使用安全 DOM API。Recognition 输出只作为 Structured Draft 数据处理，不进入
  PositionPilot Agent 的 System / User Instruction，也不为此新增独立安全框架。

## 7. 实现 Task Decomposition

### T0 — Evaluation Fixture 与 Decision Proposal

- 建立少量无敏感信息的 Asset / Text / Screenshot 固定 Fixture。
- 运行短 Spike，只回答 E1 / E2 的八个最小问题并给出推荐选型。
- 提交 Provider / Vision 选型与图片隐私边界；Human Review 后形成简短 ADR 并开始实现。

### T1 — Asset Metadata Domain / Application Boundary

- 新增只包含 Selector 所需字段的 Provider-neutral Asset Identity、Search / Validation Result、
  Status 与 Provider Protocol。
- 实现 bounded query、canonical symbol、candidate sorting、exact-match 与 Failure Validation。
- Unit Tests 使用 Fake Provider，不访问真实网络。

### T2 — Selected Asset Metadata Adapter / Bootstrap

- 隔离 Provider Request / Response、Credential、Timeout 与 Failure Mapping。
- Config 只使用 Environment Variables，更新 `.env.example`，不得读取仓库 `.env*`。
- 增加 opt-in Online Smoke，不进入默认 Regression Gate。

### T3 — Recognition Domain / Application Boundary

- 新增 Text / Screenshot Input、Import Draft、Field Status、Review Signal、Warning 与 Failure
  Contract。
- 实现必要的 MIME、size、text length、row count 与 structured response Validation。
- Confidence 保持 Presentation / Review Metadata，不进入 Opening Position Command。

### T4 — Selected Vision / OCR Adapter

- 只请求 M9 所需的 Structured Draft 字段，Provider Payload 不越过 Adapter。
- 明确处理 malformed structured output、missing fields、timeout、rate limit、provider unavailable
  与 privacy-safe logging。图片和识别文本始终作为数据，不进入 PositionPilot Agent 指令链路。
- 增加 opt-in Online Smoke；默认 Tests 使用 Fake Provider 与固定 Fixture。

### T5 — Asset Search / Recognition API

- 按现有 API 风格增加 Session-authenticated read / processing endpoints。
- Response 使用 Provider-neutral Schema；不返回 Secret、原始 Provider Payload 或内部 User ID。
- 覆盖 query / upload bounds、status mapping、ownership 与无 Portfolio / sealed Opening State 场景。

### T6 — Confirmed Opening State Validation

- 在 Portfolio 创建与后续 Opening State 初始化路径执行 exact Asset Validation。
- 将 verified canonical symbol 传入现有 `OpeningPositionInput`；不新增 Asset Master Foreign Key。
- Provider Validation 在数据库事务外完成；现有 User Row Lock 内重新检查 one-time Gate，避免
  外部 I/O 持锁并阻止并发状态变化绕过 Gate。
- Provider Failure、invalid Asset、canonical duplicate 或 sealed Gate 全部原子失败。
- 保持 Opening Position 无现金影响、无 sequence、无历史 BUY 和 immutable 语义。

### T7 — Frontend Import Review Flow

- 在现有 Setup / Opening State UI 增加 Manual、Text、Screenshot 三种输入入口。
- 展示 editable Draft、`canonical_symbol / display_name / exchange` 候选、missing / invalid
  状态、Confidence Review Signal 与明确 Human Confirmation。
- 处理 stale response、身份切换、重复 Processing、Upload Cancellation 与 Write Ambiguity。
- 不引入 Frontend Framework、Node Build Pipeline 或前端金融计算。

### T8 — Tests 与 Browser Smoke

- Domain / Application / Adapter / API / Product Interface Tests；外部 Provider 全部 Mock。XSS、
  Recognition 文本不进入 Agent 指令、malformed Provider response、timeout、rate limit、invalid
  MIME 与 duplicate 等边界放在对应 Unit / API / Integration Test。
- PostgreSQL Integration 证明复用 one-time Gate、写入原子性和没有新增 Asset Master Persistence。
- Browser Smoke 只覆盖真实用户主流程：Manual Asset Search、Text Import、Screenshot Import、
  ambiguous symbol 后用户选择、修改 Draft 后 Confirm 并成功创建 Portfolio，以及 sealed Opening
  State 拒绝 Import。
- 运行默认 pytest、Ruff format / lint、mypy、uv lock、Alembic heads / history 与 diff check。

### T9 — Automated Review、Docs 与 Human Acceptance

- Automated Review 聚焦 Asset Truth、Confidence、Opening Gate、Provider Failure、图片隐私、
  Recognition 数据边界、Session Ownership 与 API 一致性。
- Review 修改后重跑受影响 Tests / Quality Checks。
- 同步 README、CHANGELOG、ARCHITECTURE、Roadmap、Provider ADR 与必要 Engineering Note。
- 使用正式 Provider 与真实 `position_pilot.main:app` 完成 Human Acceptance；Fake / Fixture 页面
  不构成 Provider Capability 或真实 Import Acceptance Evidence。

## 8. 测试与 Acceptance Matrix

| Boundary | 必须证明 |
|---|---|
| Asset Identity | 非唯一输入不能自动写入；exact validation 产生 canonical symbol |
| No Asset Master | Portfolio Persistence 不复制完整 Provider Asset Dataset |
| Provider Isolation | Provider-specific Payload / Error 不进入 Application / Domain |
| Recognition | Text / Screenshot 只产生 Draft，没有直接 Write Capability |
| Confidence | low confidence + corrected valid fields 可写；high confidence + invalid fields 不可写 |
| Human Confirmation | 未确认 Draft 不能写入；确认 Payload 不携带 Domain-authoritative Confidence |
| Opening Gate | 仅无 Opening / Transaction / Cash Event 时原子写入 |
| No Reconciliation | sealed Portfolio 不 merge / overwrite / diff external state |
| Validation | commit 前重新 Asset Validation，再执行 Decimal / duplicate / Domain replay |
| Failures | no match 与 Provider / invalid response / unsupported input Failure 可区分 |
| Privacy | 原图默认不持久化、不写普通日志、不进入未授权 Provider |
| Data Boundary | 图片 / OCR 文本只成为 Structured Draft 数据，不进入 Agent 指令链路 |
| Identity | Session 决定 Account / Portfolio，Request Body 不选择 User |
| Regression | M8 manual Setup、Ledger、Ask Composer 与 Agent Context 不退化 |

## 9. Non-Goals

- 本地完整 Asset Master、全市场 Security Master、Symbol History 或 Corporate Action Mapping；
- 已初始化 Portfolio 的增量 Import、merge、overwrite、sync、diff 或 Reconciliation；
- Broker Connection、Account Linking、自动定期同步或外部 Position Source of Truth；
- Recognition 自动写入、Confidence Threshold 自动批准 / 否决或把 Confidence 持久化为 Domain Fact；
- Transaction Text / Screenshot Import、Fee / Execution Cost 识别或历史交易重建；
- 从图片推测缺失 symbol、shares、average cost、position type 或交易历史；
- 默认持久化原始图片、OCR 全文、Provider Payload 或敏感 Metadata；
- 为 Draft 引入 Database、Queue、Object Storage、Vector Database 或后台 Job；
- 为 Recognition 数据额外建设通用 Prompt Injection / Upload Security Framework；
- 用 General Web Search、LLM 常识或 Browser Suggestion 替代 Asset Metadata Provider Validation；
- Frontend Framework Migration、Multi-Agent、Conversation Memory 或 Technical Analysis。

## 10. Dependency、并行与 Git Strategy

严格依赖顺序：

```text
T0 Evaluation + Human Review
→ T1 Asset Contract / T3 Recognition Contract
→ T2 Asset Adapter / T4 Recognition Adapter
→ T5 API
→ T6 Confirmed Write Validation
→ T7 Frontend
→ T8 Verification
→ T9 Review / Human Acceptance
```

- T1 与 T3 在 Human Review 后可并行；T2 与 T4 只在 Contract 稳定后可并行。
- T5、T6、T7 共享 Public Schema 与 Opening State 核心路径，默认串行整合。
- Subagent 不执行 git add / commit；主线程负责 Contract 决策、整合、Automated Review 与 Atomic
  Commits。
- 开始实现 M9 时创建 `codex/m9-asset-identity-import` Milestone Branch；每个通过验证的 Logical
  Change 创建 Atomic Commit。Human Acceptance 前不合并 `main`，未经授权不 Push、打 Tag 或
  创建 GitHub Release。

## 11. Human Review Gates

以下节点必须暂停并等待批准：

1. Provider / Vision 选型与图片隐私边界；
2. 实现过程中若需要改变既有 Domain、Database 或 M9 Scope；
3. M9 完成后的 Human Acceptance。

当前计划状态：真实性与 Scope Boundary，以及 Finnhub + Alibaba Model Studio `qwen3-vl-flash`
选型与图片隐私边界均已获 Human 批准。Massive 的 5 requests/min 免费额度经 Review 被确认不适合
交互式搜索与多持仓 exact validation，因此 2026-09-02 改用 Finnhub，并从最小 Asset Identity
删除 active / inactive status。M9 的 Domain / Application Boundary、Provider Adapter、
API、Confirmed Write Validation、Frontend Import Flow、默认 Regression、Automated Review 与
Engineering Browser Smoke 已完成；Review 发现的 FileReader Session Race、malformed Draft 提示、
Provider malformed response mapping 与 detached pending row 已修复并重新验证。

当前等待第三个 Human Review Gate：正式 Finnhub / `qwen3-vl-flash` Online Smoke、可清理
PostgreSQL Integration 与用户在正式 `position_pilot.main:app` 上的 Human Acceptance。缺少显式
导出的 Provider Credential 与 `TEST_DATABASE_URL` 时，这三项不会由默认 Test Suite 假装通过。
Human Acceptance 前保持 `IN PROGRESS`，不 merge `main`、不 Push、不 Tag，也不创建 Release。
