# Gemini Production 有限回归：8 Cases / 12 Turns

2026-10-06。Human 已批准本次有限补跑；尚未批准 Merge / Push。

## 已取得的 Smoke 证据

用户在自己的终端执行了被冻结的 Production Smoke。
本地 Artifact：`artifacts/gemini-production-final-2026-10-05-attempt-1/smoke.json`。
核对结果为技术 **PASS**：官方 GOOGLE_GEMINI / gemini-3.8-flash / NativeOutput、
2 次模型请求、1 次成功 Quote Tool、有效 Source ID / inline citation、当前 4B Typed Thesis Draft。
没有数据库访问或 Search 暴露，behavioral_status 仍为 NOT_EVALUATED。

两个 Google SDK 警告未阻断本次实际 FunctionCall / FunctionResponse / Native Final 完成，
不能仅因警告将该次执行判为 FAIL，也不因此更换 SDK、开启 AFC / Search 或添加文本解析兜底。
这是固定 Portfolio / Quote 的模型接线证据，不是实际金融数据访问或全面 Production Acceptance。

既有 Production Candidate 与 Runtime / Prompt / Schema / Budget 未修改；
回归单独冻结 [Regression Candidate](2026-10-06-gemini-production-regression-candidate.json)，
关联原 [Smoke Candidate](2026-10-05-gemini-production-smoke-candidate.json)，不重写旧验收记录。

## 本次授权边界

| Case | Ask Turns | 验证重点 |
| --- | ---: | --- |
| AQ06 | 1 | 金额、Quote 与 Ledger Cash 的权威边界 |
| AQ12 | 3 | GOOG → MSFT → GOOG 的历史与 Source 隔离 |
| AQ13 | 1 | 跨 Thread / Service 读取已确认 Thesis / Horizon |
| AQ14 | 1 | 已失效版本与过期 Pending 不再作为已确认意图 |
| AQ15 | 2 | 提出失效草案、独立显式确认、后续新 Thread 不使用旧 Plan |
| AQ16 | 2 | 未确认建议不能升级为用户既定 Strategy |
| AQ17a / AQ17b | 2 | 新闻空结果与 Provider Failure 必须区分 |

固定 8 Cases / 12 Ask Turns，各一次。失败时保留证据，不自动重跑 Case；
依赖失败的后续确认 / Turn 按既有 Harness 标记 NOT_RUN，不伪造完成 12 Turns。
其余独立 Case 可以继续。调用完成不等于行为 PASS，Rubric / Acceptance 仍需 Review。

- 使用本次真实 Production Factory，不使用历史 Eval 专用 Provider 装配。
- Core 复用现有 Native Case / History Fixture；4B 复用真实 Strategy / Conversation Service 与
  隔离的临时内存 SQLite，不连接用户的 PostgreSQL 或修改实际 Ledger。
- Quote / History / News / Market Context 使用固定 Fixture，仅 Gemini 模型请求是真实在线调用。
- 生产初始 Native Run 仍为 7 Tool Attempts / 8 Model Requests / 60s；保留已有最多一次无 Tool
  Source / Citation Repair，使用剩余 60s 预算。不新增 Framework / SDK Retry。
- 12 Ask Turns 不等于 12 API 请求；含既有 Repair 的保守最大模型请求数为 108，实际数写入 Artifact。
- `OPEN_WEB_RESEARCH = DEFERRED`，AQ04 Earnings 不测，不执行 Repeat 或 Browser Acceptance。

## 执行命令

Agent 的执行进程没有继承用户终端中的 GEMINI_API_KEY；本轮只完成离线准备，未代为发出模型请求。
不读取 / source `.env`，不在聊天中索取 Key。用户可在刚才已成功执行 Smoke 的终端直接运行：

```bash
cd /Users/linyingwei/Documents/position-pilot
RUN_GEMINI_PRODUCTION_REGRESSION=1 PYTHONPATH=backend:tests uv run --frozen python tests/evaluation/gemini_production_regression.py --online --artifact-dir artifacts/gemini-production-regression-2026-10-06-attempt-1
```

无需激活虚拟环境或配置测试数据库。运行前核对两份冻结 Candidate；必须使用全新 Artifact 目录，
不覆盖原 Smoke，也不自动复用 / 续跑已有回归目录。没有 Key 时不创建目录、不构造 Provider Client。

完成后读取该目录 `summary.json` 与 `cases/*.json`，再做行为 / 金融事实 / 生命周期 Review。
线上结果出来前，状态为 **PREPARED_OFFLINE / ONLINE NOT_RUN**，不记录回归 PASS，不合并 main。

## 离线验证

- Regression Runner / Smoke / Core Harness / Strategy Harness / Strategy Continuity：59 passed（Review 修复后重跑）。
- `ruff check backend tests`：通过；`ruff format --check backend tests`：216 files already formatted。
- `mypy backend tests`：严格配置通过，215 source files；没有豁免导入错误或放宽类型检查。
- 原 Smoke Candidate 的 `--preflight`：通过；原 Production 源码与冻结记录没有修改。
- FunctionModel 组合测试完成 8 Cases / 12 Turns 和隔离 SQLite 生命周期，仅作为离线机械执行证据。
- 本轮不重复全量离线 Regression；没有修改 Production / 公共 Contract，原整合轮的全量记录保留。
- Automated Review 发现 AQ12 前轮失败后旧 Harness 仍继续后续请求：只在新 Runner 的进度回调中断链，
  不改共享 Harness；第 1 / 2 轮失败测试验证真实 Core Harness 的后续调用未发出且 NOT_RUN 已持久化。
- 只读复审确认上述 P2 已关闭，当前范围无剩余 P1 / P2。

## 最终冻结

- Source commit：`d48c0f6461202e09a228703715bf106192dd8b92`。
- Candidate：`gemini-production-regression-2026-10-06-v1`，父 Smoke 仍绑定 `3638eff7abc8d870c0e7ec525661863bb41badfe`。
- Regression 与原 Smoke 的离线 `--preflight` 均通过；没有代发在线请求。
- `main = 0d36e786b9f09b2e39c4a53630960b4bce4aaae4` 与封存 stash `911862ad5b8663579103e40b0262221126a51915` 未改变。
- 当前分支 `codex/gemini-final-phase4b-integration`；未 Merge / Push，用户原 Smoke Artifact 保留且未提交。
