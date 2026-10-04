# Phase 4 4A 本机持久化组合验收

2026-10-04。承接 Human 已批准的有限剩余验收。冻结 V8 的真实 FastAPI、PostgreSQL 与网页已运行；本轮没有新的模型、行情、News 或 Search 请求。

后续 Human 已明确确认 4A 验收通过，接受本文记录的证据边界；这不改写 NOT_EVALUATED 项，也不等于完整 Phase 4 验收。

## 环境与方法

- 代码：`67c9442696127a3a015535ffd8fbaa05288feb3a`，`/private/tmp/position-pilot-gemini-candidate-v8`，检查前后均 CLEAN。
- API / 网页：`http://127.0.0.1:8000/app/`；数据库为既有 `position-pilot-postgres-1`，迁移版本 `20260922_0010`。
- Docker 原容器恢复运行，没有重建、重置或读取容器凭证。真实配置与迁移由用户自行装载执行；Agent 没有读取仓库 `.env`。
- 通过真实注册、初始化 Portfolio、Thread API 创建两个隔离的 `example.test` 测试账户。初始 Cash 为 1000，空持仓；没有操作用户原有账户。
- 仅向刚创建的隔离 Thread 注入 SQL Fixture：500→200 预算历史、带来源的回答、NO_NEWS_FOUND、失败 Turn。所有 Assistant 内容明确标注“持久化验收 Fixture，非模型输出”。SQL 用账户 ID / email 保护目标范围。
- 通过真实 API 与网页读取这些记录，并通过已存在 Turn 的 `client_request_id` 幂等重放验证成功 / 失败返回。没有新执行 Agent；不是完整的真实模型 Ask E2E，不证明预算意图提取、Gemini Production 接线或实时信息能力。

Artifact：[目录](../../../build/evaluation-runs/p4-persistence-acceptance-20261004)、[结果](../../../build/evaluation-runs/p4-persistence-acceptance-20261004/api-checks.json)、[环境与测试对象](../../../build/evaluation-runs/p4-persistence-acceptance-20261004/manifest.json)。可复现 helper / SQL 已保存，实际密码没有进入 Artifact 或 Git。

验收后仅将这两个临时测试账户的 Session 设为到期，并移除私有临时密码文件；测试记录保留供 Review，未影响用户原有账户。扩展 confirm 导致关闭测试标签页也超时，如页面仍显示确认框，可取消并关闭测试标签页。

## 验收结果

| 项目 | 实际结果 | 边界 |
| --- | --- | --- |
| 预算历史恢复 | 网页刷新后 USER 500 / 200 及两条明示 Fixture 回答完整；API 返回 4 条消息 | 持久化 / UI PASS；语义沿用已接受 AQ10，不能从 Fixture 推导新 Behavioral PASS |
| Thread / Account 切换 | A→B 后列表为空，无 A 消息或 Source；B→A 后原 Thread 恢复；两 Thread 切换不串话 | 真实 UI PASS |
| Owner 隔离 | B 直接访问 A 的 Thread 与 Messages，均 404 / THREAD_NOT_FOUND | 真实 API PASS |
| Sources 恢复 | Source UUID、URL、时间、reference、PERSISTENCE_FIXTURE Provider、OK / NO_NEWS_FOUND 状态正确恢复 | API / UI PASS；外部 URL 未访问 |
| 失败历史 | FAILED / LLM_PROVIDER_UNAVAILABLE 展示正确；失败 Turn 只有 USER，没有 Assistant Answer | API / UI PASS；失败状态是 Fixture，不是本轮真实 Provider 故障 |
| 成功幂等重放 | 返回原 Turn ID，历史不变 | API PASS；未重新运行 Agent |
| 失败幂等重放 | 返回既有 503 / LLM_PROVIDER_UNAVAILABLE，历史不变 | API PASS；未重新运行 Agent |
| 账本保护 | 重放和删除前后 Portfolio / Transactions / Cash Events 响应完全相同，Cash 1000 | 真实 API PASS；初始测试 Portfolio 由初始化接口创建 |
| 删除 API | 刚创建的可丢弃空 Thread 软删除后，列表不含该 Thread；详情 / 消息均 404；另外两 Thread 保留 | API PASS |
| 删除网页确认 | 本次扩展的原生 confirm 控制超时，没有取得取消 / 确认后的可靠状态 | NOT_EVALUATED；不写成正式 UI PASS。此前同 V8 页面在工程替身下的原生 Chrome Cancel / Confirm / 刷新已通过，见有限验收报告 |

截图：[预算恢复](../../../build/evaluation-runs/p4-persistence-acceptance-20261004/budget-restored.jpg)、[B 隔离](../../../build/evaluation-runs/p4-persistence-acceptance-20261004/account-b-isolation.jpg)、[来源与失败](../../../build/evaluation-runs/p4-persistence-acceptance-20261004/sources-and-failure.jpg)。

脚本先后纠正了两个测试假设：公开注册响应不暴露 Account ID；既有失败 Turn 重放返回 503，而非 502。均依据现有 Contract 修正，没有改产品或弱化成功断言。最终 API 检查全部通过；三个 helper 的语法检查通过。

本轮只新增验收证据和更新文档，没有修改 Production、Provider factory、Schema、依赖、Budget、timeout、Retry 或 Repair。此前 46 项定向 pytest、前端 Node 检查及 PostgreSQL 集成 / Migration 往返证据继续适用于未变的相关代码，未重复执行。不把这些历史检查声称为本轮新跑。

## 收口建议

已接受的 Core checkpoint / Repeat，加上同 V8 的工程替身 UI 和本轮真实 API / PostgreSQL / UI 恢复证据，已具备提交 4A 有限验收 Human Review 的条件。删除 confirm 的正式环境操作限制单独保留，不再为了自动化工具问题重跑模型或扩展 Provider。

建议 Human 接受这一组合工程证据边界后收口 4A。它不等于完整同版本 V8 Primary，也不等于正式网页 Gemini / 真实市场认证。AQ04 明确 DEFERRED / NOT_RUN，等待 web_search；Research 仍 NOT_MEASURED；4B Strategy / Memory 尚未开始。完整 Phase 4 尚未完成，本轮不 merge main、不启动 4B。
