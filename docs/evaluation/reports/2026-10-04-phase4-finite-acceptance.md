# Phase 4 4A 有限剩余验收

2026-10-04。用户授权执行有限剩余验收，并明确将 AQ04 延期到 web_search 功能可用后再评审。本轮不运行 Core / Repeat / Research / Earnings，不开始 4B。

## 1. 环境与证据范围

- 冻结代码：V8 `67c9442696127a3a015535ffd8fbaa05288feb3a`，`/private/tmp/position-pilot-gemini-candidate-v8` 工作树 CLEAN。
- 初次检查时正式应用没有运行：`8000` 未监听。Docker Desktop 已打开，但 `docker ps` 没有运行容器，`5432` 未监听；后续恢复原容器并由用户启动 V8 应用，结果见本文第 3 节。
- 工程页面：`127.0.0.1:18081/app/?engineering_smoke=1`，复用既有 `tests/browser_smoke_app.py`。页面明确展示 Fake Agent / Fixture 标识。
- 临时入口在 `/private/tmp/position-pilot-finite-ui.py`，只预建两个内存假账户、增加失败与空新闻 Fixture；替换 `get_settings` 为拒绝函数，防止间接读取 `.env`。所有 Application / API / Frontend 代码保持 V8 原样。
- 真实浏览器：Codex 内置浏览器与 Chrome 扩展；删除确认框最终使用 Chrome 原生 UI 操作验收。没有通过执行页面脚本绕过确认框。
- 无真实 LLM / 行情 / News 请求，无正式数据库访问，无依赖或 Production 修改。

工程 Artifact：[目录](../../../build/evaluation-runs/p4-finite-acceptance-20261004)、[API 断言结果](../../../build/evaluation-runs/p4-finite-acceptance-20261004/api-boundaries.json)。临时入口副本也保存于该目录，假账户凭证仅为本机一次性 Fixture，不是真实凭证。

## 2. 逐项验收

| 项目 | 本轮操作与结果 | 判定 / 边界 |
| --- | --- | --- |
| 恢复与切换 | A 创建预算 Thread 与独立 Thread；刷新恢复用户消息及来源；切换不串消息；A→B→A 后 A 原历史恢复 | ENGINEERING PASS；内存 Store 跨刷新 / 登录，不证明进程重启或真实 DB 持久化 |
| 预算纠正 | 同一 Thread 保存“这次最多投入 500 美元”与“预算改为 200 美元”，刷新和重新登录后仍可见 | 消息恢复 PASS；Fake Agent 返回固定回答，不能据此判预算语义提取 / 推理 PASS，已有 AQ10 行为证据仍按原 Review 采用 |
| 账本保护 | 工程 API 读取 Portfolio / Transactions / Cash Events，追加聊天后再次读取；三份响应完全相同，Cash 仍为 1000 | ENGINEERING PASS；未创建真实交易，未改变真实账户 |
| 删除 UI | 原生 Chrome 点击可丢弃 Thread 删除，Cancel 后 Thread 仍存在；再次确认删除后列表与当前 Context 移除，刷新不恢复 | ENGINEERING PASS；内置浏览器 / 扩展的 CDP 弹窗操作曾超时，不把这些失败尝试写成成功；采用后续原生 UI 的明确结果 |
| 账户隔离 | A 登出后 B 列表为空、页面不包含 A 的消息或 Source；再登录 A 恢复；B 直接 GET A 的 Thread 与 Messages 都为 404 / THREAD_NOT_FOUND | ENGINEERING PASS；两个预建假账户，未操作真实隐私数据 |
| 来源恢复与定位 | 展开 Sources，看到 GOOG Fixture reference、BROWSER_SMOKE、CURRENT_QUOTE、时间与 OK 状态；重新读取历史仍包含对应来源 | ENGINEERING PASS；没有外部 URL 的来源展示 Metadata，不声称已经打开真实网站 |
| 空新闻 | 受控 NO_NEWS_FOUND 来源展示明确状态；回答明示检索窗口空结果不等于市场无新闻 | ENGINEERING PASS；只验证已有 UI 对状态的呈现，不证明模型会自主得出该边界 |
| 请求失败 | 受控 LLM_PROVIDER_UNAVAILABLE 展示 Answer unavailable / Sources 0；刷新后重新选择失败 Thread，失败仍可见；API 持久历史仅 USER，answers={} | ENGINEERING PASS；错误卡片是 UI 状态，未伪造或持久化成功 Assistant Answer |
| 正式应用组合链路 | 初次未运行；后续真实 API / PostgreSQL / 网页恢复已验证，见持久化验收报告 | 工程组合证据已补；真实模型 Ask / Production Gemini 未评估 |
| AQ04 | 用户明确延期，等待 web_search 功能可用后再 Review | DEFERRED / NOT_RUN；不计 Core 13，不标 PASS |

截图：[恢复](../../../build/evaluation-runs/p4-finite-acceptance-20261004/account-a-restored.jpg)、[B 隔离](../../../build/evaluation-runs/p4-finite-acceptance-20261004/account-b-isolation.jpg)、[空新闻来源](../../../build/evaluation-runs/p4-finite-acceptance-20261004/sources-no-news.jpg)。

本轮本机 API 断言通过。第一次校验脚本误按内部 Cash 对象读取公开响应，产生 KeyError；按既有 `PortfolioSnapshotResponse.available_cash` 字段更正后全部通过，没有修改产品 DTO 或弱化断言。
上一轮 46 项 Conversation / API 定向离线检查及前端 Node 检查继续作为对应代码证据；本轮不修改这些代码，因此未重复执行，也不声称是本轮新跑的测试。

## 3. 后续真实应用验收与收口状态

已接受的 Core checkpoint / Repeat 不再重跑。AQ04 已按 Human 指示延期；工程 UI 原先缺少的删除确认、账户切换和失败展示证据现已补齐。本轮没有发现需要修改 Production 的新问题。

随后恢复了既有 PostgreSQL 容器，用户自行执行迁移并启动冻结 V8 后端。真实 API / PostgreSQL / 网页的预算历史、来源 / 失败恢复、账户切换、Owner 隔离、幂等重放及删除 API 已通过。[持久化组合验收](2026-10-04-phase4-persistence-acceptance.md) 明示 SQL Fixture 与真实模型执行的区别。网页 confirm 在本次扩展控制下超时，正式环境取消 / 确认保持 NOT_EVALUATED；同 V8 工程替身的原生 UI 成功证据仍保留。

Gemini 当前只有 Eval 原生装配，Production factory 未增加 GoogleProvider 分支。不能直接把 `LLM_PROVIDER=GOOGLE_GEMINI` 当作正式网页已可用；本轮没有修改该 factory 或尝试让 Gemini Key 走旧 OpenAI-compatible 路径。正式模型链路应先确认既有 Production Provider 的实际接线，或独立批准 Google 最小接线，不能为了验收静默扩展本轮范围。

建议 Human Review 接受组合工程证据及明确边界后收口 4A，不再新增模型测试。真实模型网页接线不作为本轮隐式新增任务；4B 尚未开始，完整 Phase 4 不标完成，不自动 merge main。
