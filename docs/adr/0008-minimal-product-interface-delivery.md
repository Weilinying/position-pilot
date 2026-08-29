# ADR 0008 — Minimal Product Interface Delivery

## Status

Accepted — 2026-08-29

## Context

M7 需要为已经稳定的 FastAPI V1 Vertical Slice 增加一个可直接使用和演示的最小 Web Interface。当前 Repository 没有 JavaScript Toolchain、Frontend Framework、Authentication、CORS 或 Hosting 配置；页面只需加载一个 Portfolio、提交问题并展示 Answer、Source 与 Failure State。

选择或引入核心 Frontend Framework、修改 Public API Contract，以及无 Authentication 时的运行边界属于 Human Review Gate。2026-08-29 Human Review 批准本 ADR 的最小方案。

## Decision

- 使用 FastAPI / Starlette 同源托管静态 HTML、CSS 与 ES Modules，页面入口为 `/app/`，静态资源位于 `/static/`。
- 不引入 React、Vue、Vite、Node Package Manager、Frontend State Framework、独立 Frontend Service 或 CORS。
- 新增只读 `GET /v1/portfolios/{user_id}`，直接映射现有 `PortfolioService.get_portfolio()` 的确定性 Ledger Replay Result。
- Browser 只保存 `userIdInput`、`loadedUserId` 与 Portfolio / Question Request Generation。Question 只能使用 `loadedUserId`，过期 User 或 Generation 的 Response 必须丢弃。
- 所有动态文本使用安全 DOM Text API；LLM Answer、Source Metadata、API Error 与 User Input 不生成动态 HTML。
- 默认本地启动命令只绑定 `127.0.0.1`。M7 不在代码中禁止其他 Host，但无 Authentication 的实例不得被描述为可安全公开部署。
- Browser Smoke 是固定 Checklist 驱动的 Human Verification Evidence，不是默认自动化 E2E Gate。

## Alternatives

### React / Vue + Vite

优点是组件生态、状态测试和长期前端扩展能力更强；缺点是为一个单页 Demo 引入新的 Runtime、Build、Dependency 与测试边界。当前交互规模尚不足以证明该复杂度。

### Server-rendered Template

可以减少 JavaScript，但 Question、Loading、Source Cards 和异步身份一致性仍需要 Client State。模板引擎不会消除核心 Browser State，反而增加新的渲染依赖。

### 独立 Frontend Service

可以建立清晰部署边界，但当前会额外引入 CORS、两套启动流程与部署协调，不符合 M7 Local-only Vertical Slice。

## Trade-offs

- 无构建静态界面保持了最小依赖和同源安全边界，但没有独立 JavaScript Unit Test Toolchain。
- Human Browser Smoke 可以验证当前有限交互，但不提供自动化 E2E Regression Guarantee。
- 新 Snapshot API 增加了稳定 Public Contract；未来扩展字段仍需保持 Domain Source of Truth 和 Human Review Gate。
- Local-only 约束避免在 M7 引入 Authentication，但 User ID 本身不是访问控制。

## Reconsider When

- 页面出现多个独立 Route、共享组件或复杂 Client State；
- Human Browser Smoke 无法稳定覆盖已出现的 UI Failure Mode；
- 需要自动化 Browser Regression、正式 Hosting 或多用户 Authentication；
- Frontend 需要独立发布周期、持久化设置或第三方 Connector；
- Read-only Snapshot 出现真实性能问题，需要 Projection、Cache 或新的 API Boundary。
