# Phase 4B 执行清单

2026-10-04。4A 已获 Human Acceptance；本清单整理既有 Phase 4 Implementation Plan 的 T6～T8 执行顺序，不重新设计架构。4B/T6 已于本日获 Human Approval，并完成下述补充 Contract 的离线实现；T7 离线连续 Ask / Memory Fixture 已验证，四个 Case 的在线 Primary 已完成，Review 建议待 Human 接受。

补充 Contract：同 `account + scope + kind` 最多各一个 ACTIVE 和 PENDING，允许二者同时存在；确认新版本时在同一事务 Supersede。三种 Intent 的 scope 均为规范化 `ticker + LONG_TERM/SWING`，详见 [T6 交付记录](../evaluation/reports/2026-10-04-phase4b-t6.md)。

## 目标与固定边界

让用户明确确认的持续投资意图跨 Thread / 登录生效，同时根据当前账本与市场重新分析。Conversation 中的模型建议不自动变成策略。

- 复用 Single Agent、PydanticAI、4A 已验收的工具与错误语义；不更换 Provider，不接新 Search。
- Gemini 官方仍用于 Eval；本清单不隐含授权 Production GoogleProvider 接线。
- 三种 Intent：`POSITION_PLAN_V1`、`INVESTMENT_THESIS_V1`、`HOLDING_HORIZON_V1`。
- 目标预算与本轮 Budget / Cash 分离；`remaining_target_budget = max(target_budget - open_cost_basis, 0)`，每轮从当前 Ledger 重算。
- 不保存当前建议、具体本轮买入金额、价格 trigger、tranche、已投入 / 剩余预算或其他派生事实。
- Memory 复用已有只读 `MemoryReader` / `NoOpMemoryReader`，只用 Fixture 验证背景过滤；不建设完整 Memory、Vector DB 或自动记忆。
- AQ04 / Research 继续延期。完整 Phase 4 最终验收及本地 main 合并安排在 T8；4A 通过不视为 4B 或整个 Phase 4 完成。

## 按依赖执行

| 顺序 | 工作 | 完成标准 |
| --- | --- | --- |
| 0 | 从干净 V8 新建 4B 分支，保留根工作树；记录继承配置与已接受边界；处理本次发现的有限离线测试问题 | 不改变 4A 历史 Artifact / Prompt / Budget；离线质量检查可解释，不增加模型测试 |
| 1：T6 | Strategy typed payload、Candidate / Confirmed Version、Service / Repository、additive 0011 Migration | Candidate 默认 24h；同 `account + scope + kind` 只有一个 Pending / Active；不同 scope / kind 可并存；并发、版本、幂等、Owner 正确；没有 Ledger 写入 |
| 2：T6 | Ask 生成可审查 Candidate Draft，绑定真实 User Message；现有 AnswerV2 Candidate 接缝与确认 / 取消 API；前端 Candidate Card | 仅用户明确长期意图 / 持久计划请求可生成；普通建议不生成。必须经显式 UI / API 确认，不把自然语言“好”当授权；不增加 Mutation Tool |
| 3：T6 | 每轮读取 Active Confirmed Intent，接入资金快照；替代 / 失效与 Thread 删除关联 | Pending / Expired / Stale / Superseded / Invalidated 不注入。删除 Thread 取消其 Pending，已确认 Intent 保留；BUY / SELL 后派生值更新；Horizon 不改变仓位类型 |
| 4：T7 | 连续 Ask 与 Memory 过滤离线验证，AQ13～AQ16 从 DIAGNOSTIC 转为 FULL | 使用真实 Service / UoW 生命周期步骤，而非把“已保存 / 已删除”写进 Prompt；Memory 不能覆盖 Ledger / Confirmed Intent |
| 5：T7 | 冻结 4B Candidate，执行一次 AQ13～AQ16 Primary，按实际影响定向回归 4A；按既有 Gate 验证 AQ12 / AQ15 各三次 | Runtime / Behavioral / Critical 分开 Review；只修有证据的通用问题。4A 已接受证据保留，不自动反复全量重跑；在线命令与 Run 预算先交 Human Review |
| 6：T8 | 最终集成 / 浏览器、回滚演练、Legacy 清理、报告与 Human Acceptance | 一次最终已启用 Scope 验证；延期 Case 不伪装 FULL。回滚保留 Conversation / Strategy / Ledger；确认后合并本地 main，不自动 push |

具体实现仍以 [既有计划 §7、T6～T8 与 Gate](ask-quality-phase-4-implementation.md) 为准。候选输出 / API 接缝若实际缺少原计划已冻结的 Contract，先离线核对后实现该 Contract；超出已批准 Contract 的变化需单独 Review。

## 主要代码范围

- 新增 Strategy 的 Domain / Application Service、Infrastructure models / UoW、API schema / router、0011 Migration 与对应测试；复用 Phase 3 Spike 作为证据，不从 Production 导入 Spike。
- 连接 `conversation_service.py` / `conversation_agent.py`、`investment_context_builder.py`、Native Runtime Context 与 `bootstrap.py`，按必要范围接入。
- 复用已有 `position_funding.py` / `memory.py` 及测试，不另建计算 / Memory 框架。
- 更新 `frontend/app.js` / `styles.css` 的 Candidate 展示、确认和冲突状态。
- 扩展现有 Eval Manifest / harness 和 PostgreSQL / Browser 检查；不扩展 Provider compatibility harness。

## 离线、工程与行为验收

1. 未确认、过期、旧版本及跨 Owner 的候选不能生效；重复确认不写第二个版本；并发同 scope 冲突、不同 scope 不误阻塞。
2. target_budget 300、open cost basis 200 → remaining 100；买入后重算、卖出后释放成本空间。市值、卖出收益、Cash 与本轮预算不进入该公式。
3. Assistant Recommendation 不提升为 User-confirmed Strategy；新事实可以改变建议，不能机械复用旧价格 trigger / tranche。
4. AQ13：正确读取已确认 Thesis / Horizon；AQ14：失效 Intent 不复用；AQ15：显式确认失效后旧版本不复活；AQ16：未确认建议不成为既定策略。
5. 浏览器完成“起草 → 确认 → 刷新 / 重登 → 读取 → 替代 / 失效”，B 不读取 A 的 Candidate / Strategy，账本不因聊天或确认改变。
6. State Authority 目标维度必须为 2；未经确认生效、跨 Owner、Ledger Mutation、旧策略复活或持久化实时建议，任一即 Critical Failure。COMPLETED / pytest pass 不等于行为通过。

## 离线质量检查待处理记录

为核对验收后 Git 收口，本轮在干净 V8 副本运行了全离线检查，没有模型请求：

- pytest：983 passed、1 failed、92 deselected。失败是 `test_portfolio_valuation.py` 的固定 2026-09-10 Quote 配合真实当前时钟，被正确判为 STALE；该文件及估值实现未在 4A 改动，应在测试注入固定时钟，不放宽行情 freshness。
- Ruff lint 通过；format check 有 6 文件差异，其中 4 个与 main 相同，2 个为 Phase 4 Eval。只处理相应格式，不重写逻辑。
- mypy：24 errors；23 个来自与 main 相同的三个旧测试文件，1 个是 Conversation integration test 缺少 `last_turn is not None` 的收窄。补真实类型 / 非空断言，不降低检查配置。
- 前端 Node syntax / Conversation Contract 检查通过。

这些是有限的离线检查维护，不作为新 Agent Behavioral failure、不撤销 Human 4A Acceptance、不触发在线补考。完整合并前需解决并重新检查。

## T7 当前状态（2026-10-04）

- 已完成四个真实生命周期脚本与只读 Memory Fixture 接线；History / Strategy / Ledger 不由 Prompt 伪造。
- 离线 FunctionModel 验证 4B Native Schema + ordinary Quote Tool、确认跨 Thread 读取、替代 / 失效、
  BUY / SELL 动态预算、SWING 隔离，以及 Memory 非权威过滤。
- 4B Primary 仅 AQ13–AQ16 / 6 Ask，命令与配置单独 Freeze；独立 Run
  `p4b-gemini-primary-v1-20261004T141232Z` 已 4/4 Case、6/6 Turn COMPLETED。
  [实际 Artifact Review](../evaluation/reports/2026-10-04-phase4b-primary-review.md)建议生命周期 Behavioral / Critical PASS、State Authority 2；研究与推断瑕疵另列，等待 Human Review，不从运行完成自动推导 PASS。
- Primary Human Review 后才决定有限影响回归与 AQ12 / AQ15 三次 Gate；不自动重跑完整 4A。
