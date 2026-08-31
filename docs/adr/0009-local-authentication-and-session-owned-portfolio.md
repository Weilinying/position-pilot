# ADR 0009 — Local Authentication and Session-owned Portfolio

## Status

Accepted — 2026-08-31

## Context

M8 的 `v1.0.0` Acceptance 要求本地用户无需 Demo Seed、已知 UUID 或开发者操作，即可从首次访问完成注册、Portfolio 初始化、Ledger 写入和真实 Investment Agent 问答。M7 的 UUID Input 与 Browser Pointer 只能提供工程 Demo 身份，不能表达稳定 Account Ownership，也无法形成完整首次使用流程。

Human Review 批准 Authentication 进入 M8 的唯一原因，是服务 Local Self-Service MVP。该决定不把 M8 扩展为完整 Account Platform，也不改变现有单一 `User → Portfolio State` Domain Model。

## Decision

- 新增最小 Email / Password Account、登录、退出与 Session 恢复。Account 最多通过 nullable unique Link 拥有一个现有 Portfolio User；Account 可以先注册，稍后再原子创建 Portfolio。
- Password 使用标准库 `hashlib.scrypt`、每个 Password 独立随机 Salt 与版本化参数进行 Hash。Password 明文不持久化、不写日志、不进入 Response。
- Session Token 使用密码学随机 Opaque Secret。Browser 只通过七天有效的 `HttpOnly + SameSite=Lax + Path=/` Cookie 持有 Token；PostgreSQL 只保存 SHA-256 Digest、Account、创建时间和过期时间。
- Loopback HTTP 明确使用 `Secure=false`。Login 会撤销当前 Browser 的旧 Session 并签发新 Token；Logout 删除当前 Session；过期或无效 Token 返回稳定 `401`。
- 正常产品 API 使用 Session-derived singular Resource：`/v1/portfolio` 及其 Opening Position、Transaction、Cash Event 子资源。Investment Question Body 只接收 `question`，User Identity 由 Server Session 注入。
- 既有 UUID Routes 仅为工程兼容保留，也必须验证当前 Session 对目标 User 的 Ownership；知道 UUID 不能读取、修改或提问其他 Account 的 Portfolio。
- Browser 不在 URL、表单或 `localStorage` 中保存或恢复身份。Logout、Session Expiry 与 Account 变化必须清空 Portfolio、未提交草稿、Question Presentation History 和异步写入状态。
- Authentication 只适用于推荐绑定 `127.0.0.1` 的本地产品，不宣称具备公网 Account Security。

## Alternatives

### 继续使用 UUID / Local Pointer

实现最少，但用户必须理解内部标识，且 UUID 不是 Ownership 或 Credential，无法满足首次使用与账户恢复 Acceptance。

### JWT Stateless Session

减少 Session Lookup，但会把撤销、轮换和 Credential 生命周期编码进签名 Token。M8 已有 PostgreSQL，持久化 Opaque Session 更容易撤销与审计，也不需要引入 JWT Library。

### Authentication Framework 或完整 Account Platform

能够提供 Password Reset、Email Verification、OAuth、MFA、Rate Limit 和 Session Management，但显著扩大基础设施与产品 Scope。当前 localhost MVP 没有足够需求证明该复杂度。

### Client-generated UUID 或 Idempotency Infrastructure

可以缓解部分 Create Response Ambiguity，但不能替代 Account Ownership，并会提前引入 Mutation Reconciliation。M8 的注册结果未知时改为使用相同 Email Login；Portfolio Setup 通过 Session 恢复当前确定性状态。

## Trade-offs

- Persisted Session 每次认证需要 Database Read，但换来简单明确的撤销、轮换与 Ownership Boundary。
- scrypt 避免新增 Password Library；参数需要随硬件和威胁模型重新评估，M8 不实现在线升级、Breached Password 检查或 Password Lifecycle。
- Cookie 在 loopback HTTP 上不能设置 `Secure=true`；因此当前实现不得暴露到公网或不受控局域网。
- Account 与 Portfolio User 仍是两个一对一概念。这样复用现有 Ledger Domain，但 Multiple Portfolios 时必须重新评估 Resource 与 Ownership Model。
- M8 没有 Rate Limit、Email Verification、Password Reset、OAuth、MFA、Role / Permission、远程 Session 管理或通用 Idempotency。

## Reconsider When

- 服务需要离开 loopback、使用 TLS 或面向不受控网络；
- 需要 Password Recovery、Email Ownership、MFA、OAuth、Rate Limit 或远程 Session 管理；
- 一个 Account 需要多个 Portfolio、Organization 或共享权限；
- 安全评估要求成熟 Password Hash Library、Pepper、密钥轮换或集中 Identity Provider；
- Create / Ledger Network Ambiguity 产生真实 Failure，需要 Idempotency Key、Mutation Lookup 或 Reconciliation。
