# Phase 4 T8 最终验收报告

2026-10-05（本机演练于 10-04 开始）。状态：**T8 操作验证完成，整个 Phase 4 已获 Final Human Acceptance（2026-10-05）。**
最终 Legacy 清理及本地 Git 收口见[收尾记录](2026-10-05-phase4-final-acceptance.md)；下文保留 T8 当次证据与限制。

## 验收决定与版本

Human 已接受 4A，以及 4B Primary / Repeat 的有限证据。本次明确给予 AQ12 r1 历史概括偏强的瑕疵例外通过：
仍保留 CS / EI 各 1、其余维度 2 的原始建议分，不改写成逐次达到原最低分；Critical PASS，作为已知 non-blocking finding。
不修改 Prompt，不重跑 Core / Repeat / pytest 或质量检查套件，不接新 Provider / Search。

- 实际演练应用：冻结干净副本 `e9013eb4036b8714b7a8ea863f3b89113c505dac`；收尾文档在 `codex/phase4b-t6`。
- PydanticAI 1.107.6；既有在线证据 GOOGLE_GEMINI / gemini-3.8-flash，仅 Eval 接线。
- Runtime Prompt SHA256：`34821d82b65d01e736a94378177b164bc6cc42045d00b1f0600b46cdb4831ef5`。
- Intent Native Schema SHA256：`8fc4671a333243ecfca2bd9e0ead8200c23882c85b8d0df8d24e78bd1fd99845`。
- Budget Policy SHA256：`76724d05b0f33e01dc5743ac6a5ba7fb46780d13cdc5d0ba54674399895bc0a4`。
- 7 Tool Attempts / 8 Model Requests / 60s per turn；框架 retries=0；既有 Eval ConnectError/ReadError 一次原请求重试；
  至多一次无 Tool Source/Citation Repair，均限剩余 wall-clock。本轮未调用这些模型分支。
- 文档变更不改变上述应用版本、Prompt、Schema、Budget 或 Fixture。4A 历史结果不拼成新同版本 Baseline。

## 本轮真实组件与外部边界

使用 Chrome 扩展、冻结副本原样前端与 FastAPI，真实 Session Auth、Portfolio / Conversation / Strategy Service、
SQLAlchemy UoW 和独立 PostgreSQL 17。隔离容器 `position-pilot-t8-drill`，数据库端口 15438，应用 18082；
回退副本 18083。未访问原 5432 数据库、未加载任何 `.env`，不读取/输出真实 Credential。

模型输出由临时 `FixtureAgent` 返回 typed Draft；Quote / Asset Metadata 复用已有浏览器 Fixture。
页面与回答明确标识 Fixture。这是实际 HTTP / 浏览器 / SQL 生命周期证据，**不证明真实 Provider 网页 Ask、
模型意图识别或市场数据联网成功**。这些行为沿用已 Review 的 Gemini Eval；没有把 Gemini 写入 Production factory。

[本轮完整证据目录](/Users/linyingwei/Documents/position-pilot/build/evaluation-runs/p4-t8-final-20261004/manifest.json)
保存操作装配、截图、快照、HTTP 结果与文件 digest；SQL 备份仅包含合成演练账户，不进入 Git。

## 浏览器 / 集成逐项结果

| 项目 | 实际证据 | 结论 |
| --- | --- | --- |
| 注册 / 初始化 | 浏览器真实 API 注册合成 A 账户，建立 Cash 1000、GOOG LONG_TERM 1 股、平均成本 200 | PASS；无真实账户 / 交易 |
| 起草 / 确认 | Ask 生成 300 USD PENDING Card；明确点击 Confirm intent，真实 SQL 保存 ACTIVE v1 | PASS；模型产草案为 Fixture，确认是实际产品流程 |
| 刷新 / 重登 | 刷新 CONFIRMED 不丢；退出清空界面，重登恢复历史与 Card | PASS；真实持久数据库，不是内存 Store |
| 新 Thread 读取 | 新 Thread 得到 target=300、open_cost=200、remaining=100 | PASS；动态调用现有确定性 PositionFundingSnapshot，未让模型心算 |
| ACTIVE + PENDING | 起草 500 时仍有 ACTIVE 300 与 PENDING 500；确认后旧 v1 SUPERSEDED、新 v2 ACTIVE | PASS；同 scope 只各一个；数据库快照保存 |
| 仓位 scope | 另确认 GOOG SWING 700；LONG_TERM remaining=300，SWING remaining=700 | PASS；SWING 不串 LONG_TERM 成本 |
| 显式失效 | INVALIDATE PENDING 经按钮确认后，LONG_TERM v3 INVALIDATED；后续只读取 SWING ACTIVE | PASS；不复活旧版本 |
| Owner 隔离 | 合成 B GET A Candidate / Thread、POST confirm / cancel 都为 404；B 的 ACTIVE 列表为空 | PASS；真实 HTTP Session-owned API |
| 删除来源 Thread | 浏览器 Delete 点击到原生 confirm；macOS 锁屏且扩展确认超时，未确认该 UI 成功；后用实际 HTTP DELETE 完成软删除 | HTTP PASS / 原生确认 NOT_COMPLETED；Candidate CANCELLED、GET 404，已确认 SWING 保留 |
| Ledger 保护 | 8 个账本相关表在起草、确认、替代、失效后 digest 不变 | PASS；不通过 Ask 写入 Ledger |
| 恢复新版 | 浏览器重新打开新版，原历史、Confirmed / Invalidated Card 全部恢复；删除的 900 Thread 不再列出 | PASS；没有恢复模型旧结论为 Active Intent |

截图：`01-pending.jpg`、`02-confirmed-refresh.jpg`、`03-relogin-new-thread-funding.jpg`、`04-scope-isolation.jpg`、
`05-invalidated.jpg`、`06-prephase4-rollback.jpg`、`07-restored-history.jpg`，均在证据目录。
`owner-check.json` / `delete-boundary.json` 记录 HTTP 边界；原生删除确认的工具限制不伪装为通过。

## 回滚与前向恢复演练

1. 通过显式演练 DSN 在空隔离库升至 `20261004_0011`，建立真实 Conversation / Strategy / Ledger。
2. `pg_dump --no-owner --no-privileges` 保存 `t8-retained.sql`；记录 `pre-rollback.json`。
3. 从 Phase 4 前提交 `97a72240776fad1ea72ed136c6c97270b76e0770` 导出应用 Artifact，替换为同隔离 SQL 装配；
   停新版，浏览器进入旧前端，成功读取同一账户 Cash 1000、GOOG 成本 200。旧 Thread / Strategy API 为 404，
   旧模型未调用。没有部署请求级双跑，也没有删除新增表。
4. 记录 `during-rollback.json`；恢复冻结新版，仅执行幂等 `upgrade head`，不 downgrade；记录 `restored.json`。
5. 三阶段 **15 个业务表 + alembic_version（共 16 张表） 的行数 / SHA256 完全相同**；新增 PENDING、历史版本和消息全部保留。
   数据摘要不含 Account password_hash 或 Session。`rollback-result.json` 四项保留检查为 true。
6. 浏览器恢复历史。随后独立 HTTP 删除演练按正常生命周期 CANCELLED 草案；该操作在三阶段比较完成之后，
   不混淆为回退丢数据。

演练 PASS 的范围是应用 Artifact 回退及保留 Schema 的前向恢复，不是 Production 故障演习、旧 Provider 认证、
备份还原灾难恢复或 RPO/RTO 承诺。原 PostgreSQL 容器仍运行；本轮临时服务和隔离容器已停止，数据副本保留。

正式操作次序：备份 → 部署单一新版 Artifact 与 additive 0011 → 验证；触发 Owner / Ledger / 未确认生效等
Hard Rollback 时切回上述旧 Artifact / Frontend，**不执行数据库 downgrade**，保留数据以便前向修复。
本轮没有对正式数据库执行 0011；生产启动仍需按正式环境受控执行 Migration。

## Cutover / Legacy / 文档

只读检查确认 `bootstrap.get_investment_agent()` 仅装配 NativeInvestmentAgent + PydanticAI Runtime；Conversation 与
兼容 `/questions` 共用该入口。Legacy 手写 Loop 不在 Production 装配路径；旧代码与 Characterization 仍存在，
不声称已经物理删除。依据 [原计划 §12.4](../../plans/ask-quality-phase-4-implementation.md)，物理清理安排在
Final Acceptance 后；本轮用户禁止改 Prompt / 重跑测试，因此没有进行会影响共享 DTO / 旧对照测试的源码重构。
该清理不应再打开模型 Eval 或增加新的 Provider；若需要源码变动，后续只跑直接受影响离线检查。

更新 Architecture / Roadmap / 执行清单及 ADR 状态，没有新增架构决策或改动 Production。
Release Mapping：仍是既有 V1 Answer Quality Discovery 的已启用范围，未创建新 Version / Tag / 发布或 Production Provider Certification。

## 已有检查与 Review

[T6 报告](2026-10-04-phase4b-t6.md)：全离线 1012 passed、78 受影响回归、独立 PostgreSQL 8 passed、Ruff / mypy / Node 通过。
[T7 报告](2026-10-04-phase4b-t7.md)：全离线 1023 passed、Review 后 120 相关回归、Ruff / mypy / Node 通过。
这些是此前实际执行的结果，本轮没有重新运行。Primary 4/4 Case、6/6 Turn 完成；Repeat 新增 13/13 Ask 完成，
AQ15 r1 引用 Primary；行为结论依照各自 Review 与 Human 例外接受，不从 pytest / COMPLETED 推导。

本轮主线程审查数据摘要、Owner HTTP、回退版本、冻结副本与文档 diff，检查秘密隔离和证据范围。
没有声称独立 subagent Review 完成；先前工具的继承模型不支持委派。没有产品代码 diff，因此不重新运行测试套件。

## 最终结论与剩余事项

- **本轮没有发现新的 State Authority / Ledger / Source Critical blocker。** 已启用 4A + 4B 范围建议最终验收；
  AQ12 r1 语言概括瑕疵保留为 Human-accepted non-blocking exception。
- 不自动重跑或继续加 Prompt。AQ04 Earnings、AQ01/AQ02/AQ19 Research / Web Search、完整 Memory / 自动记忆、
  正式 Provider Certification 仍是已批准延期范围，不能标 PASS，也不计成当前已启用范围未完成。
- 原生删除确认本轮 NOT_COMPLETED，实际删除 / 取消 / Owner 边界已由 HTTP + SQL 验证；4A 已有原生删除 UI
  成功证据，当前新增的 Strategy cancel-on-delete 边界由本轮 SQL 证据补齐，未把旧证据拼成新模型 Baseline。
- **Final Human Acceptance 已收到**；Human 明确接受上述限制与例外，并授权按 AGENTS.md §12
  完成 Legacy 有限清理与本地 main 收口。保留根工作树用户修改，不 Push / 删除分支。

依据：[4A 有限验收](2026-10-04-phase4-finite-acceptance.md)、[4A 持久化](2026-10-04-phase4-persistence-acceptance.md)、
[4B Primary Review](2026-10-04-phase4b-primary-review.md)、[4B Repeat Review](2026-10-04-phase4b-repeat-review.md)。
