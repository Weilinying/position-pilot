# M7 — Minimal Product Interface 执行计划

## 1. 状态与目标

**Status:** IMPLEMENTED — Awaiting Human Acceptance

M7 为已完成核心 V1 能力的 PositionPilot 增加一个可直接使用和演示的最小 Web Interface。界面必须忠实展示后端 Structured State、Agent Answer、Source Tracking 与 Failure State，不在浏览器中复制 Portfolio Calculation、Market Regime 或其他金融业务规则。

本计划优先完成一个本地、单用户上下文、同源运行的 Demo Vertical Slice：

```text
选择 / 输入 Portfolio User ID
        ↓
读取只读 Portfolio Snapshot
        ↓
输入 Investment Question
        ↓
POST /v1/investment/questions
        ↓
Answer + OK / DEGRADED + Context Sources
```

M7 不把当前开发接口升级为可公开部署的多用户产品；Authentication / Authorization 仍是明确限制。

## 2. 当前基线与缺口

- M6 已于 2026-08-29 Human Accepted 并合并到本地 `main`；M7 开始时应先修正 `ROADMAP.md` 顶部仍显示 M6 `IN PROGRESS` 的文档状态。
- FastAPI 已提供 `POST /v1/investment/questions`，返回 `status`、自由文本 `answer` 和经过后端验证的 `sources`。
- `sources` 已包含 Context 类型、获取状态、ticker、provider、feed、market timestamp 与 fetched timestamp，足以展示当前回答声明使用的成功来源和失败的 Tool Attempt；它不等价于逐 Claim Citation。
- `PortfolioService.get_portfolio()` 已能从 Ledger 确定性恢复 Portfolio State，但当前没有只读 Portfolio REST Endpoint。
- 当前只有 Cash Event 写入 API；User / Transaction 创建没有公共 API。M7 Demo Data 需要独立准备入口，但不应借此扩展成账户管理或交易录入产品。
- Repository 当前没有前端目录、JavaScript Toolchain、Authentication、CORS 配置或部署配置。
- 根目录存在用户未跟踪的 PyCharm 示例 `main.py`；M7 不依赖、不修改、不删除，也不将其纳入 Commit。

## 3. Human Decision Proposal

以下两项已于 2026-08-29 获得 Human Review 批准，构成 M7 的实现边界。

### D1 — Frontend Delivery

**建议：FastAPI 同源托管无构建步骤的 HTML / CSS / ES Modules。**

- 页面入口使用 `/app/`，静态资源使用 `/static/`；现有 API 路由保持不变。
- 不引入 React、Vue、Vite、Node package manager、前端状态管理或 UI Component Framework。
- 浏览器只负责输入、调用 API、展示状态和安全渲染；所有 Decimal 继续按 API 字符串显示，不在 JavaScript 中重新计算。
- 所有来自 API、LLM、Provider 或用户输入的动态文本均视为不可信数据，使用 `textContent`、DOM Property 或等价安全机制渲染；M7 不使用动态字符串拼接生成 HTML，也不引入 Markdown-to-HTML Renderer。
- 同源调用不需要 CORS，也不新增独立 Frontend Service 或 Reverse Proxy。

**Trade-off：** 该方案最符合轻量 Demo 范围，降低供应链和构建复杂度；代价是缺少成熟组件生态与自动化 JavaScript Unit Test Toolchain。若 Human Review 要求后续持续扩展为正式产品前端，应改为单独评估 React / Vue 等方案，而不是在 M7 实现中途切换。

### D2 — Read-only Portfolio API Contract

**建议：新增 `GET /v1/portfolios/{user_id}`。**

成功响应只暴露当前界面需要的确定性 Snapshot：

```json
{
  "user_id": "00000000-0000-0000-0000-000000000001",
  "available_cash": "1000.00000000",
  "positions_are_complete": true,
  "positions": [
    {
      "ticker": "GOOG",
      "position_type": "LONG_TERM",
      "shares": "2.00000000",
      "average_cost": "180.00000000",
      "cost_basis": "360.00000000"
    }
  ]
}
```

- Response 由 `PortfolioService.get_portfolio()` 的 `PortfolioState` 映射，不增加新计算路径或持久化 Projection。
- Positions 使用稳定的 `(ticker, position_type)` 顺序；同一 ticker 的 `LONG_TERM` / `SWING` 保持独立。
- Decimal 保持 JSON string，避免浏览器浮点数改变金融事实。
- 未知 User 返回现有稳定错误：`404 / USER_NOT_FOUND`。
- 不在本 Endpoint 返回 Transaction / Cash Event Ledger、历史 BUY Facts、当前市值、收益、实时价格或风险结论。

这是新增 Public API Contract，按 Repository Human Review Gate，批准本计划不自动代表可以任意扩展响应字段；实现只按上述最小 Contract 进行。

## 4. Acceptance Criteria

- 访问 `/app/` 可以看到无需构建步骤的 PositionPilot 页面。
- 用户可以输入有效 UUID 或使用 Demo Seed 输出的 UUID 加载 Portfolio Snapshot。
- Portfolio 展示 Available Cash，并按独立行正确展示 ticker、`LONG_TERM` / `SWING`、shares、average cost 与 cost basis。
- Question 只能在 Portfolio 加载成功后提交；重复提交受控，Loading 状态清晰且不会误显示上一轮来源。
- 修改 User ID 输入后，已加载 Portfolio Context 立即失效并禁用 Question，直到新 User 的 Snapshot 成功加载；异步 Portfolio / Question Response 只能在仍属于当前 User 与当前 Request Generation 时更新 UI，不得将旧 User 的 Answer 或 Sources 显示在新 Portfolio 下。
- `POST /v1/investment/questions` 成功后展示完整 Answer、Response `OK` / `DEGRADED` 和本轮 `sources`。
- Source 展示 type、原始 status、ticker、provider / feed 及可用 timestamp；不得把 Source Tracking 描述为逐 Claim Citation。
- `DEGRADED` 是带事实缺口的成功 Answer，不被错误显示成 Request Failure。
- `NO_DATA`、`NO_NEWS_FOUND`、Provider Failure 等非 `OK` Source 状态保留原始 Code，并以清晰的“缺失 / 不可用”视觉状态呈现。
- 404、422、502、503、网络错误与非预期错误有不同或至少不误导的用户提示；错误详情不暴露 Secret 或内部堆栈。
- 所有来自 API、LLM、Provider 或用户输入的动态文本均通过 `textContent`、DOM Property 或等价安全机制渲染；除静态 UI Template 外，不使用字符串拼接生成 HTML，也不通过不受控 Markdown 执行 HTML / Script。
- 前端不计算 Portfolio、Average Cost、Market Regime、购买数量、仓位权重或其他金融事实。
- Demo Data 通过显式本地命令准备，使用 Application Service 写入，不绕过 Domain Validation 或直接修改数据库。
- README 的推荐启动命令默认只绑定 `127.0.0.1` loopback interface；在没有 Authentication / Authorization 时，不得将 Demo Server 描述为可安全暴露到公网或不受控局域网。
- 核心 Demo Flow 按固定 Checklist 在真实浏览器完成至少一次 Human Browser Smoke；该证据不计入默认 Automated Regression Gate。默认自动测试与已配置质量检查仍须通过。
- README、Architecture、Roadmap 与实际启动 / Demo 流程一致。
- Automated Review 的 Critical / High Findings 已解决，修复后重新运行受影响检查。
- Human Acceptance 通过后才合并到本地 `main`。

## 5. UX 与状态边界

### 5.1 页面结构

单页只保留四个区域：

1. Portfolio Selector：User ID 输入、Load 按钮和 Demo 使用提示。
2. Portfolio Snapshot：Available Cash、按 Position Type 区分的持仓表及 Empty Portfolio 状态。
3. Investment Question：问题输入、Submit 按钮和请求中状态。
4. Decision Result：Answer、整体状态及 Source Cards。

不增加侧边导航、账户菜单、聊天历史、多会话、Watchlist、交易表单或复杂 Dashboard。

### 5.2 Client State Identity Invariants

Vanilla JavaScript 显式维护以下最小身份状态，不依赖输入框当前值隐式代表已加载 Portfolio：

```text
userIdInput  = 当前 User ID 输入框的规范化值
loadedUserId = 当前成功加载并展示 Snapshot 的 User ID；未加载或已失效时为 null
```

- Question Request 的 `user_id` 只能来自 `loadedUserId`，不得提交 `userIdInput` 或提交时重新读取输入框。
- `userIdInput` 一旦与 `loadedUserId` 不一致，立即把 Portfolio Context 标记为 stale、禁用 Question，并清除或明确失效当前 Result；只有对应输入值的最新 Portfolio Request 成功后才能更新 `loadedUserId`。
- Portfolio Load 与 Question Submit 分别维护单调递增的 Request Generation，或使用等价的 `AbortController` + Identity Check。Response 只有同时匹配发起时的 User ID 和当前 Generation 才允许更新 DOM。
- 新的 Portfolio Load 会使未完成的旧 Question Request 失效；旧 Response 即使成功返回，也必须丢弃，不能覆盖新 User 的 UI。
- 这些规则是 M7 的 UI Correctness Contract；不需要引入通用 Store 或复杂状态管理 Framework。

### 5.3 状态映射

| Backend / Browser State | UI 语义 |
|---|---|
| Portfolio 200 | 展示完整当前 Snapshot，启用 Question |
| Portfolio 404 | User 不存在，清空 Snapshot 并禁用 Question |
| Answer `OK` | 正常展示 Answer 与 Sources |
| Answer `DEGRADED` | 展示可用 Answer，同时明确部分当前事实缺失 |
| Source `OK` | 标记为本回答已验证绑定的可用 Context Source |
| Source `NO_DATA` / `NO_NEWS_FOUND` | 标记为本次查询无数据 / 无结果，不外推为世界状态 |
| Source Provider Failure | 标记外部数据源不可用，并保留原始 status |
| HTTP 422 | 输入不合法；使用后端稳定 message 或安全通用提示 |
| HTTP 502 | Agent / LLM Contract 无法形成回答，不展示伪 Answer |
| HTTP 503 | LLM Provider 当前不可用，可提示稍后重试 |
| Network / Unexpected Error | 标记请求失败，不复用上一轮 Answer / Sources 冒充结果 |

### 5.4 Source Grounding 文案边界

- UI 使用“本回答上下文来源”或等价文案，不使用“每句话都已证明”。
- 成功 Source 只能说明 LLM 声明使用且后端绑定到本轮成功 Context；不声称 Answer 每个自然语言 Claim 都经过自动验证。
- Failed Tool Attempt 可以展示状态，但不得显示为成功引用来源。
- 当前 API 未提供 Tool Result 的完整事实 Payload 或 claim-to-evidence mapping；M7 不通过解析 Answer 来伪造二者。

## 6. 实现任务与依赖

```text
T0 Milestone Start / Baseline
  ↓
T1 Read-only Portfolio API
  ↓
T2 Static UI Shell + Portfolio Flow
  ↓
T3 Question / Answer / Source Flow
  ↓
T4 Demo Data + End-to-end Browser Verification
  ↓
T5 Documentation + Full Checks
  ↓
T6 Automated Review → Fix → Re-check → Human Acceptance
```

### T0 — Milestone Start 与基线

- Human Review 批准 D1 / D2 后检查 Git 状态；保留并避开用户未跟踪的根目录 `main.py`。
- 从 `main` 创建 `codex/m7-minimal-product-interface` Branch。
- 将 `ROADMAP.md` Current Milestone 更新为 M7 `IN PROGRESS`，并确认 M6 为完成状态。
- 运行默认 pytest、Ruff、mypy、lock check、Alembic history / heads 与 `git diff --check`，记录 M7 启动基线。
- 不因前端开发擅自读取 `.env` 或输出 Credential。

### T1 — Read-only Portfolio API Slice

- 在 FastAPI 层增加最小 Portfolio Response Schema 和 `GET /v1/portfolios/{user_id}`。
- 直接调用现有 `PortfolioService.get_portfolio()`；API Handler 只做 Schema Mapping 与 Error Mapping。
- 明确排序、Decimal Serialization、Empty Positions 和 `USER_NOT_FOUND` Contract。
- 增加 API Contract Tests，覆盖双 Position Type、空组合、Decimal 精度和 404。
- 不新增 Repository 方法、Database Table、Migration 或 Projection。

### T2 — Static UI 与 Portfolio Flow

- 增加小型 `frontend/` 目录，预计包含 `index.html`、`styles.css`、`app.js`；具体拆分以职责清晰为准。
- 使用 FastAPI / Starlette 已有静态文件能力托管 `/app/` 与 `/static/`，不增加前端运行服务。
- 实现 User ID 校验、URL Query Parameter 可选预填、Portfolio Loading / Empty / Error State。
- 显式区分 `userIdInput` 与 `loadedUserId`；输入变化立即使已加载 Context 失效并禁用 Question。
- 为 Portfolio Load 建立 Request Generation / Identity Check，丢弃已过期 User 或已被新请求取代的异步 Response。
- 展示 Cash 与 Positions；Position Type 使用文本与视觉标签双重表达，不只依赖颜色。
- Question 区域在 Portfolio 未成功加载时禁用。
- 增加静态入口与资源可访问的 FastAPI Tests。

### T3 — Question、Answer 与 Sources Flow

- 通过同源 `fetch` 调用现有问答 API，不修改 Agent、Prompt、Tool Routing 或 Source Validation。
- Question Request 只读取 `loadedUserId`；提交时清理上一轮 Result State，禁用重复提交并显示 Loading。
- 为 Question Request 建立 User Identity + Request Generation Check；新 User Load 或新 Question 使旧 Response 失效，过期 Answer / Sources 不得渲染。
- 安全展示 Answer 文本和整体 `OK` / `DEGRADED` 状态。
- 按 Source 类型和状态展示 Context Cards，保留 provider / feed / timestamp 与原始 status。
- 实现稳定 API Error Parser：优先读取现有 `detail.code` / `detail.message`，无法识别时回退到安全通用提示。
- 所有 Portfolio、Answer、Source、Error 和 User Input 衍生的动态文本统一使用安全 DOM Text API；禁止用动态字符串拼接设置 `innerHTML`。
- 不解析 Answer 内的 ticker、数字、`FACT / INFERENCE / UNKNOWN` 或 Citation。

### T4 — Demo Data 与实际行为验证

- 增加显式本地 Demo Seed 入口，创建一个新的 Demo User，并通过 `PortfolioService.create_user()` 与 `record_transaction()` 写入少量 `LONG_TERM` / `SWING` 持仓。
- Seed 输出生成的 User ID 和 `/app/?user_id=...` 访问方式；重复执行创建新的隔离 Demo User，不覆盖既有 User 或 Ledger。
- Demo 数据只用于本地开发，不在应用启动时自动写数据库，不进入 Migration，不增加隐藏的 Demo Mode。
- 为 Seed 的固定组合与失败行为增加不依赖真实数据库的测试；必要的 PostgreSQL 验证保持 opt-in Integration Test。
- 使用固定 Human Browser Smoke Checklist 验证页面、状态与安全边界，并在 M7 Completion Evidence 中记录日期、Browser 和每项结果。
- 外部 LLM / Alpaca 不可用时，用已测试的后端替身完成确定性 UI Flow；真实 Provider Smoke 作为额外 Evidence，不伪称默认检查通过。

### T5 — 文档与完整检查

- 更新 README：M7 状态、默认绑定 `127.0.0.1` 的启动命令、页面 URL、Demo Seed、Credential 前置条件和“仅本地 / 开发环境”警告；不得推荐无 Authentication 的 `0.0.0.0` 启动方式。
- 更新 ARCHITECTURE：Static UI、只读 Snapshot API、同源边界和仍无 Authentication 的限制。
- 检查是否产生新的 ADR / Engineering Note；预期 D1 / D2 属于 M7 已批准范围，可在 Plan 或 Architecture 记录，不为简单静态界面机械新增 ADR。
- 运行默认 pytest、相关 Integration Tests、Ruff format / lint、mypy strict、`uv lock --check`、Alembic history / heads 与 `git diff --check`。
- 对 HTML / CSS / JavaScript 执行实际浏览器验证；M7 不仅凭文件存在宣称 UI 可用。

### T6 — Review 与收口

- 在基础检查通过后执行 Automated Review，重点检查 Public API Contract、XSS / HTML Injection、异步状态竞争、旧 Answer / Source 泄漏、错误映射和 Domain Logic Duplication。
- 修复 Critical / High Findings；根据影响重新运行 API Tests、默认检查与浏览器 Demo Flow。
- 将 `ROADMAP.md`、本 Plan 与 Architecture 的最终状态同步为实际结果，并记录已知限制。
- 提交 Human Acceptance Evidence；获得 Human Acceptance 后合并到本地 `main`，不自动 Push 或删除 Branch。

## 7. Verification Matrix

| 层级 | 必须验证的行为 | 主要方式 |
|---|---|---|
| Domain / Application | Portfolio Snapshot 仍来自 Ledger replay | 复用现有 Unit Tests，不新增前端计算 |
| API Contract | 双 Position Type、Decimal string、空持仓、404 | FastAPI TestClient |
| Static Delivery | `/app/` 与资源可访问，不遮蔽 `/health` / `/v1/*` | FastAPI TestClient |
| UI Identity | Input change invalidation、A → B、stale Portfolio / Question Response | Human Browser Smoke + 可控延迟 Response |
| UI Portfolio | Loading、Loaded、Empty、Invalid UUID、404 | Human Browser Smoke Checklist |
| UI Agent | OK、DEGRADED、422、502、503、Network Failure | Human Browser Smoke + 可控 API Stub / Dependency Override |
| UI Security | 所有动态文本不能执行 HTML / Script | Human Browser Injection Case + Code Review |
| Source Display | 成功来源、无数据、Provider Failure、timestamp | Human Browser Smoke + API Fixtures |
| Demo | Seed → User ID → Portfolio → Question → Result | 本地 PostgreSQL + Human Browser Smoke |
| Regression | Backend 默认行为与质量门禁不退化 | pytest、Ruff、mypy、lock / Alembic checks |

M7 Browser Smoke 是可重复、带固定 Checklist 和结果记录的 **Human Verification Evidence**，不属于默认 Automated Regression Gate，也不得在文档中描述为自动化 E2E。固定 Checklist 至少包含：

- [x] Portfolio loaded。
- [x] `LONG_TERM` / `SWING` 分别展示。
- [x] 修改 User ID 后 Context 立即失效，Question 禁用。
- [x] A 的延迟 Portfolio / Answer Response 不会更新 B 的 UI。
- [x] `OK` Answer。
- [x] `DEGRADED` Answer。
- [x] Source `NO_DATA`。
- [x] Provider Failure Source。
- [x] HTTP 422。
- [x] HTTP 503 / controlled Provider Failure。
- [x] Answer、Source、Error 与 User Input 中的 XSS Payload 均作为文本展示。
- [x] Source Metadata 使用字段标签区分 Ticker、Provider、Feed、Market Time 与 Fetched At。
- [x] 空仓 Snapshot 失效后恢复为未加载提示，不保留旧 Portfolio 的空仓语义。
- [x] 中文 / 英文可一键切换，且切换不改变已加载身份、请求状态、Answer 或 Provider 原始值。

不为满足矩阵擅自引入新的前端测试框架。若实际实现显示 Vanilla JS 状态逻辑已复杂到 Human Browser Smoke 无法稳定覆盖，应暂停并提交新增 Playwright / Node Toolchain 的 Decision Proposal。

## 8. Atomic Commit 建议

实现阶段预计按以下 Logical Changes 提交；以实际边界为准，不为数量机械拆分：

1. `docs: start M7 minimal product interface`
2. `feat: expose read-only portfolio snapshot api`
3. `feat: add minimal PositionPilot web interface`
4. `chore: add local demo portfolio seed flow`
5. `docs: complete M7 interface documentation`

每个 Commit 前先通过该 Slice 的相关测试；Review 引起修改后重新验证。Plan 审阅阶段不创建实现 Commit。

## 9. Non-Goals

- Authentication、Authorization、用户注册、账户切换或公开部署安全加固。
- User / Transaction 的通用 CRUD UI 或交易执行。
- 券商连接、自动下单、自动调仓或 Portfolio Import。
- Conversation History、Semantic Memory、Streaming Answer 或 WebSocket。
- React / Vue / Vite、Design System、组件库、Node Build Pipeline 或独立 Frontend Service。
- Candlestick、Technical Indicator、收益曲线或其他复杂图表。
- 在前端计算 Average Cost、Current Market Value、Position Weight、Market Regime、购买数量或买卖信号。
- 修改 LLM Provider、Prompt、Tool Contract、Market / News Provider 或 Evaluation Dataset。
- 将 Source Tracking 扩展为逐 Claim Citation 或返回完整 Tool Payload。
- 移动端专项适配、通用国际化 Framework、语言偏好持久化、Accessibility Certification 或 Production Analytics；已批准的中英静态界面切换、基础键盘操作、语义标签和可读对比度仍属于正常实现质量。
- Deployment / Hosting；若 Human Review 要求发布，再单独制定 Hosting / Security 计划。

## 10. 已知限制与重新考虑条件

- 由于没有 Authentication，URL 中的 User ID 不是访问控制；M7 只允许本地 / 受控开发演示，README 默认命令只绑定 `127.0.0.1`。文档约束不在代码中强制禁止 `0.0.0.0`，但不得将无 Authentication 的实例宣称为可安全暴露到公网或不受控局域网。
- Vanilla JS 不带独立 Unit Test Toolchain。若 UI 状态、组件数量或交互复杂度明显超过本计划，应重新评估 Frontend Framework 和 Browser Automation，而不是继续堆叠脚本。
- Browser Smoke 是固定 Checklist 驱动的 Human Verification Evidence，不是自动化 E2E，也不替代默认 Backend Regression Gate。
- Source Cards 展示来源身份和状态，不展示完整 Tool Result，也不证明 Answer 每个 Claim 正确。
- `DEGRADED` / `UNKNOWN` 的精度受现有 API Contract 限制；M7 不解析自然语言补造结构化未知项。
- Demo Seed 生成本地 Ledger Data，不提供清理命令；Database Cleanup 继续使用现有本地开发流程，M7 不增加破坏性删除接口。
- 若 M7 需要对外部署、真实多用户访问、持久化 UI 设置或大规模前端演进，必须先进入新的 Security / Architecture Human Review Gate。

## 11. Human Review Checklist

Human Review 于 2026-08-29 全部批准：

- [x] 批准 D1：FastAPI 同源静态 HTML / CSS / ES Modules，不引入前端 Framework / Build Toolchain。
- [x] 批准 D2：新增计划中定义的只读 `GET /v1/portfolios/{user_id}` Public API Contract。
- [x] 接受 M7 仅用于本地 / 受控 Demo，不处理 Authentication / Authorization 或 Hosting；推荐命令默认只绑定 `127.0.0.1`。
- [x] 接受 Source Tracking 只展示来源身份与状态，不扩展为逐 Claim Citation。
- [x] 接受 Demo Seed 创建新的隔离 User，不提供 UI 内 User / Transaction 管理或删除能力。

若实现需要突破以上边界，重新进入 Human Review Gate。

## 12. 当前执行证据

- 已在 `codex/m7-minimal-product-interface` Branch 完成只读 Portfolio Snapshot API、同源静态 Web Interface、隔离 Demo Seed、文档与 ADR。
- `GET /v1/portfolios/{user_id}` 直接复用 `PortfolioService.get_portfolio()`，按 `(ticker, position_type)` 稳定排序并保持 Decimal string；没有新增 Database、Migration、Projection 或金融计算路径。
- Browser 显式维护 `userIdInput`、`loadedUserId`、Portfolio Generation 与 Question Generation。User ID 输入变化会立即使 Context 失效，旧 User / 旧 Generation Response 被丢弃。
- 所有动态 Portfolio、Answer、Source、Error 与 User Input 文本均使用安全 DOM Text API；Static Contract Test 禁止 `innerHTML`，Browser Injection Cases 未创建 Image / Script DOM，也未执行 Payload。
- 2026-08-29 使用 Codex In-app Browser 完成固定 Human Browser Smoke：Portfolio Load、双 Position Type、Input Invalidation、延迟 Portfolio / Answer A → B、`OK`、`DEGRADED`、`NO_DATA`、Provider Failure、404、422、503、Network Failure 与 XSS Cases 均通过；Browser Console 无 Error / Warning。
- Human Acceptance Review 追加修复 Source Metadata 标签与 Empty Portfolio stale copy，并增加不持久化的中英一键切换。复验确认五类 Source Metadata 标签及双语时间格式清晰展示；空仓 User 改变后恢复未加载提示并禁用 Question；切换语言不改变已加载身份、Answer 或 Provider 原始值；Browser Console 仍无 Error / Warning。
- Browser Smoke 期间发现两项按钮状态恢复问题：中止 Portfolio Load 后 Load Button 可能保持禁用，以及中止 Question 后 Ask Button 可能保留 `Analyzing…` 文案。Root Cause 均为旧 Generation 的 `finally` 正确拒绝更新后，显式 Invalidation 未恢复控件状态；已在 Invalidation Path 修复并重验 A → B 场景。
- Automated Review 继续补充了 Portfolio / Answer Payload Shape Validation 与 Portfolio Response User ID 一致性拒绝；修复后无未解决 Critical / High / Medium Finding。
- 最终默认 Gate：367 passed、38 skipped；Skip 仍为需要显式真实模型、Alpaca 或 `TEST_DATABASE_URL` 的既有 Online / Integration Tests。
- Ruff format / lint、mypy strict、`uv lock --check`、Alembic heads / history 与 `git diff main...HEAD --check` 通过；Alembic Head 仍为 `20260825_0004`。
- 未新增或修改 `.env`、Secret、Provider、Agent Prompt、Tool Contract、Database Schema 或 Hosting 配置。
- 新增 ADR 0008 记录无构建同源界面、只读 API、Client Identity Invariants、loopback 与 Human Browser Smoke 边界；未新增 Engineering Note 或 Migration。
- 当前等待 Human Acceptance；通过后按 Repository Workflow 合并到本地 `main`，不自动 Push 或删除 Branch。
