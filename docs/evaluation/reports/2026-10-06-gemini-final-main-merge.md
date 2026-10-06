# Gemini Production Final — 本地 main 合并记录

日期：2026-10-06。状态：已完成本地合并；未 push、部署或执行新的在线请求。

## 合并身份

- Phase 4A / 4B 权威基线：`0d36e786b9f09b2e39c4a53630960b4bce4aaae4`。
- 整合分支：`codex/gemini-final-phase4b-integration`。
- 整合分支最终提交：`2bf3a7f09fb12195803911f089a5fca6168a8582`。
- 本地 main 合并提交：`a2397c26ba789f79864dc58b62e0061e098e7452`，采用 `--no-ff`；双亲分别为上述基线与整合分支最终提交。
- 已验证整合分支全部提交均为 main 的祖先，`main..codex/gemini-final-phase4b-integration` 无遗漏提交，合并后的文件树与整合分支一致。根工作树位于 main。

## Human Acceptance 边界

Human 接受 `gemini-production-regression-2026-10-06-v1` 为有限 Provider 在线回归证据：8 Cases / 12 Turns，Critical Gate 0/8。Production Factory、Native Structured Output、Tool Calling、Source 引用、Strategy Lifecycle 与 State Authority 关键链路通过本次验证。

AQ06 Answer Usefulness / Evidence & Inference、AQ13 Evidence & Inference 原评分均为 1，未达到冻结 Rubric 最低 2 分，作为本次有限回归的已知质量偏差接受。未修改全局 Rubric、未覆盖 Phase 4 / 4A / 4B 历史结论，也不代表全面 Production Quality Acceptance。不追加在线补考；问题保留在后续 Answer Quality / Research 能力优化范围，不因此开放 Research。

详细证据及原评分见[回归 Review](2026-10-06-gemini-production-regression-review.md)；移植边界见[整合记录](2026-10-05-gemini-final-integration.md)。

## 合并范围与保留项

Production Final 默认配置为 `GOOGLE_GEMINI` / `gemini-3.8-flash`，通过官方 GoogleProvider / GoogleModel 与 NativeOutput 接入；`GEMINI_API_KEY` 与 Aliyun OCR 凭据隔离。Vision / OCR 继续 Aliyun，保留原有允许的同 Provider fallback。环境变量仍可覆盖默认配置，本次未修改或读取本地 Secret 配置。

Application、Domain、API、Strategy、Conversation、Ledger、Migration 与旧 Runtime / Prompt 未被实验基线覆盖。`OPEN_WEB_RESEARCH = DEFERRED`；Production 不暴露 `web_research`，未移植 Google Search、Research Source / UI / quota / attribution、Brave 或 Page Fetch。AQ04 仍为独立 Diagnostic。

封存分支 `codex/archive-root-deferred-research-20261005` 及 stash `911862ad5b8663579103e40b0262221126a51915` 均保留，未 apply / pop 或删除。原始在线 artifacts 保留为未跟踪本地文件，未提交到 main。未删除其他分支、工作树或证据，未开启下一阶段。

## 验证

合并前在整合分支重新执行：

- 全量离线测试：`1059 passed, 99 deselected`。
- Ruff check：通过；Ruff format check：228 个文件无需格式化。
- 严格 mypy：215 个源文件通过。
- `uv --no-cache lock --check --offline`：通过。普通离线 lock 检查曾被 sandbox 默认缓存权限阻止，改用 no-cache 后成功；未联网或修改 lock。
- `git diff --check`：通过；独立 Automated Review：无阻断项。

合并后再次验证两份冻结 Candidate 的离线 preflight 均通过，`online=false`，冻结文件未修改；CLI 的 `PREFLIGHT_PASS_AWAITING_USER_EXECUTION` 是 preflight 模式状态，不替代已记录的在线证据或 Human Decision。合并未引入额外源代码变化，因此未重复在线调用。
