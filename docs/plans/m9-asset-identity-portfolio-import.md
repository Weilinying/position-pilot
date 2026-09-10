# M9 Asset Identity & Portfolio Import 执行计划

> 2026-09-10：M9 已追加当前持仓层级、批次维护和录入交互工作，见
> [M9 后续执行计划](m9-current-holdings-and-batch-editing.md)。下文 T0–T9 保留原导入实现记录；
> 新增工作按后续计划 T10–T14 执行。产品方向已确认，新增实现尚未完成，不新建 M9.1。

## 1. Milestone 目标

M9 通过 Provider 验证的 Asset Identity 与可人工确认的 Text / Screenshot Import，降低用户
录入 Portfolio Opening State 并校准已有持仓的成本，目标 Release 为 `v1.1.0`。
2026-09-10 扩展包含紧凑持仓树、可调整类型的批次、交易更正与未实现估值。

原导入能力的产品闭环是：

```text
Text / Screenshot
        ↓ Recognition（只产生建议）
Provider-neutral Structured Import Draft
        ↓ Asset Metadata Search / Exact Validation
canonical symbol + Missing / Invalid / Confidence Review Signal
        ↓ Human Review / Edit / Confirmation
确定的 canonical symbol + shares + average_cost + optional position_type
        ↓ trusted local Asset Binding + deterministic Domain Validation
M8 one-time Opening State Command
        ↓ atomic write
Portfolio Opening State
```

已初始化 Portfolio 的 Screenshot 复用 Recognition / Asset Binding，但最终写入追加
`PositionReconciliation` 事件，不重新初始化 Opening State。

M9 不建设本地完整 Asset Master，不把 Recognition Confidence 当作 Domain Truth，也不实现
外部账户持续同步；已确认的截图行只通过不可变 Position Reconciliation 事件校准本地状态。

## 2. 已批准的产品与真实性边界

### D1 — Canonical Symbol 是 M9 Asset Identity

- Asset Identity 以 Asset Metadata Provider 验证后的 `canonical_symbol` 表示。
- Portfolio Domain 现有 `ticker` 字段承载 canonical symbol；M9 不仅通过 uppercase / regex
  把任意用户输入声明为真实 Asset。
- M9 只规范化前端 Asset Selector 与 Recognition 自动解析实际需要的 `canonical_symbol`、`display_name` 与
  `exchange`。Provider exact validation 成功只表示能够识别并规范化 symbol，不推断未明确
  提供的 active / inactive 状态；不为 `tradable`、`fractionable`、alias、class shares、source
  timestamp 等未来字段建设通用 Metadata Model。
- 不创建完整本地 Asset Master、Security Master 同步任务或 Symbol Mapping Database。
- Provider-specific JSON、枚举和错误只存在于 Integration Adapter。

### D2 — Opening Import 与已有持仓校准分开

- 最终写入复用 M8 `InitializeOpeningPositionsCommand` 与同一 User Row Lock。
- 只有 Opening Position、Transaction 与 Cash Event 全部为空时允许提交 Import。
- Portfolio 创建后但仍满足上述 Gate 时，可以继续完成尚未写入的 Opening State；一旦 Gate
  封闭，Opening Import 必须明确失败，不能尝试 merge、overwrite 或 diff。
- Import 不创建 Transaction，不影响 Cash，不产生经济 sequence，也不伪造历史 BUY。
- 已初始化 Portfolio 的 Screenshot 校准走独立 `PositionReconciliation` Command；每一行追加
  immutable event，保存 `(ticker, position_type)`、`target_shares`、`target_average_cost`、
  `source`、`confirmed_at` 与可选 `broker/source_info`。
- Replay 按 `confirmed_at` 与 Transaction `occurred_at` 合并排序；校准直接替换对应 Position
  的 Shares / Cost Basis，校准之后的 Transaction 继续生效。
- Screenshot 未出现的 Position Key 保持不变；Reconciliation 不生成 BUY / SELL、不修改 Cash，
  也不覆盖或删除历史 Opening / Transaction / Cash Facts。

### D3 — Confidence 只服务 Human Review

- Recognition Provider 可以返回数值或枚举 Confidence，但 Application 只把它规范化为
  Provider-neutral Review Signal。
- Confidence 不进入 `OpeningPosition`、Transaction、Ledger 或 Portfolio Replay。
- 高 Confidence 不能绕过 Human Confirmation、Asset Binding、必填字段检查或 Domain
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

### 当前实现状态

- Provider-neutral Asset Metadata / Recognition Contracts、Finnhub / Qwen Adapters、Config、API 与
  Browser Draft Review Flow 已完成。
- Opening Import 继续使用一次性 Gate；已有 Portfolio 使用独立 Position Reconciliation 账本，
  两条写入路径都只接受 Browser 已明确绑定的 canonical symbol。
- Screenshot 已统一为紧凑 Attachment Composer，支持 Choose、Drag & Drop、Paste、最多两张图片
  与本地缩略图 Preview；只有点击“开始识别”才逐张读取、上传并合并 Draft。
- Vision 只返回明确 ticker 而遗漏 `suggested_symbol` 时，后端以该 ticker 执行 exact validation；
  Browser 保存未绑定 Draft 时也会为 canonical symbol 完全一致的结果自动补充绑定，不再暴露
  无意义的候选选择错误。代码不同或结果有歧义时仍要求用户明确确认。
- Finnhub exact validation 对外明确为 `VALID / INVALID / PROVIDER_UNAVAILABLE`；AAOX 已在正式本地
  页面返回 canonical match，长期自动测试不扩展真实 ticker matrix。
- 原导入工作待最终 Acceptance；当前另需完成后续计划 T10–T14，不能将本次新增需求视为已实现。

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
用于本地 Browser 建立选择状态，Recognition suggestion 必须先 exact validate 才能自动绑定。
Confirm 信任该本地 Binding，不重复调用 Provider。

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

确认请求只包含用户最终确认的确定字段与 Browser 已绑定的 canonical symbol，不包含能够影响
Domain 决策的 Confidence。M9 接受 loopback 本地产品的受信任 Browser 边界，Confirm 不重复调用
Asset Provider：

```text
require Session Ownership
→ optional fast Opening State eligibility read
→ normalize Position Type / Decimal
→ reject duplicate (canonical_symbol, position_type)
→ InitializeOpeningPositionsCommand acquires User Row Lock
→ recheck Opening State Gate under lock
→ deterministic replay
→ atomic commit
```

Asset Provider Failure 会阻止 Browser 建立 Asset Binding；未绑定 Draft 不得 Confirm。取得行锁前
若出现并发 Ledger Write，锁内 Gate 必须拒绝本次 Import；系统不尝试 merge 或自动重试。若未来
客户端不再受 loopback 本地边界控制，必须恢复 Confirm revalidation 或引入后端签名的短期 Receipt。

## 6. Public API 与 UI 实现方向

Codex 按现有 Session-derived API、Schema 和错误处理风格实现以下最小 Surface，无需为 URL、
Upload Limit 或 Error Schema 单独暂停 Review：

- Asset Search：Session-authenticated read endpoint，接收 bounded query / limit，返回
  Provider-neutral candidates 与 status。
- Opening Import Recognition：Session-authenticated、无写入能力的 Text / Screenshot endpoint，
  返回 Import Draft；Screenshot 使用明确 MIME / size limits，不接受 URL 抓取。
- Opening State Commit：优先复用现有 `POST /v1/portfolio` 与
  `POST /v1/portfolio/opening-positions`，接收 Browser 已绑定的 canonical symbol 并执行确定性校验；
  不新增 Import-specific Write Endpoint，除非 Human Review 发现现有原子 Contract 无法表达。

Browser Flow：

```text
Portfolio Setup / still-open Opening State
→ choose Manual | Paste Text | Upload Screenshot
→ recognize to editable Draft
→ resolve ambiguous asset candidates
→ show missing / invalid fields and confidence review cues
→ user explicitly confirms
→ backend performs deterministic validation and writes once
→ refresh current holdings（主页面不并列展示 Opening / Reconciliation Records）
```

- 用户可以忽略 Confidence 并直接修正字段；UI 不显示“Confidence 通过所以可安全写入”。
- Recognition / Search Failure 保留 Draft 与用户编辑能力，但 Browser 未建立 Asset Binding 时不得
  提交写入。
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

- 将 Browser 已绑定的 canonical symbol 传入现有 `OpeningPositionInput`；Confirm 不重复调用
  Provider，也不新增 Asset Master Foreign Key。
- 现有 User Row Lock 内重新检查 one-time Gate，阻止并发状态变化绕过 Gate。
- invalid symbol format、duplicate 或 sealed Gate 全部原子失败。
- 保持 Opening Position 无现金影响、无 sequence、无历史 BUY 和 immutable 语义。

### T6b — Existing Portfolio Position Reconciliation

- Screenshot 行在已初始化 Portfolio 上追加 immutable `PositionReconciliation`，不修改 Opening、
  Transaction 或 Cash Event 历史。
- Replay 按确认时间与交易发生时间合并排序，直接校准对应 `(ticker, position_type)` 的目标 Shares /
  Average Cost；未出现的 Position Key 保持不变，校准后的后续交易继续生效。
- 校准事件不产生 BUY / SELL、Cash 变化或经济 sequence；保存来源、确认时间及可选 broker / source info。

### T7 — Frontend Import Review Flow

- 在现有 Setup / Opening State UI 增加 Manual、Text、Screenshot 三种输入入口。
- 展示 editable Draft、`canonical_symbol / display_name / exchange` 候选、missing / invalid
  状态、Confidence Review Signal 与明确 Human Confirmation。
- 每条 Draft 必须绑定 Provider 验证后的 Asset Identity；自由输入必须由用户从候选列表明确选择，
  Recognition `suggested_symbol` 经后端 exact validation 成功后可自动绑定，失败或歧义时才要求
  人工选择。编辑已绑定 ticker 后立即清除选择状态，未重新选择或验证时禁止 Confirm。
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
| Opening Gate | Opening Import 仅在无 Opening / Transaction / Cash Event / Reconciliation 时原子写入 |
| Position Reconciliation | 已有 Portfolio 只追加校准事件；目标 Position 确定性更新，未出现 Position 保持 |
| No External Sync | 不做 Broker Connection、持续同步、外部 diff 或自动删除 |
| Validation | Confirm 信任本地 Browser Asset Binding，并执行 ticker format / Decimal / duplicate / Domain replay |
| Failures | no match 与 Provider / invalid response / unsupported input Failure 可区分 |
| Privacy | 原图默认不持久化、不写普通日志、不进入未授权 Provider |
| Data Boundary | 图片 / OCR 文本只成为 Structured Draft 数据，不进入 Agent 指令链路 |
| Identity | Session 决定 Account / Portfolio，Request Body 不选择 User |
| Regression | M8 manual Setup、Ledger、Ask Composer 与 Agent Context 不退化 |

## 9. Non-Goals

- 本地完整 Asset Master、全市场 Security Master、Symbol History 或 Corporate Action Mapping；
- 已初始化 Portfolio 与外部账户的持续同步、merge、overwrite、diff、自动删除或 Broker Connection；
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
→ T6 Confirmed Deterministic Write
→ T6b Existing Portfolio Reconciliation
→ T7 Frontend
→ T8 Verification
→ T9 Review / Human Acceptance
```

- T1 与 T3 在 Human Review 后可并行；T2 与 T4 只在 Contract 稳定后可并行。
- T5、T6、T6b、T7 共享 Public Schema 与 Portfolio Replay 核心路径，默认串行整合。
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
API、Confirmed Deterministic Write、Frontend Import Flow、默认 Regression、Automated Review 与
Engineering Browser Smoke 已完成；Review 发现的 FileReader Session Race、malformed Draft 提示、
Provider malformed response mapping 与 detached pending row 已修复并重新验证。

2026-09-09 扩展已实现：新增 immutable Position Reconciliation、统一 Attachment Composer、
Finnhub `httpx2` transport、`VALID / INVALID / PROVIDER_UNAVAILABLE` exact-validation contract 与
全量重新验证交互，并修复 optional Position Type 的 Draft 提示。当前进入最终 Integration、
Automated Review 与正式应用 Human Acceptance；AAOX 等真实 ticker 只作为 Human Acceptance
验证，不进入长期 Provider smoke matrix。Human Acceptance 前保持 `IN PROGRESS`，不 merge
`main`、不 Push、不 Tag，也不创建 Release。

## 12. 当前执行入口

2026-09-10 用户确认保留交易历史，允许逐批修改策略类型；成交事实通过更正保留历史。
新增需求均归属 M9，按 [后续执行计划](m9-current-holdings-and-batch-editing.md) 实施。
不进行旧测试数据兼容或历史批次回填，尚未执行数据库重置。
