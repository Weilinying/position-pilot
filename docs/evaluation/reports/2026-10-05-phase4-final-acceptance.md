# Phase 4 Final Human Acceptance 与本地收口

2026-10-05。Human 已正式签发整个 Phase 4 最终验收，授权有限 Legacy 清理及本地 `main` 合并，暂不 Push。
已接受 4A 核心质量、4B 显式确认的跨会话持续意图、T8 浏览器 / SQL / 保留数据的应用回退结论。
AQ12 r1 历史概括偏强等已知非致命瑕疵继续保留；不改写原 Rubric 或将例外说成无瑕疵 PASS。

## Legacy 清理

- 删除 Production `InvestmentAgent` 手写 Loop 和 `ModelCompletionRuntime` 旧 Completion Port。
- 旧 Loop、冻结 Prompt 与 urllib HTTP LLM Adapter 迁至 `tests/legacy/`，历史 Characterization / Phase 3
  对照测试继续保留。Production 不导入测试目录，不提供默认回退到旧 Runtime 的路径。
- Native 仍需的 Quote / History / News / Market Context Observation 与 Source 序列化提取至
  `application/investment_tool_results.py`；单次 Tool 参数校验共用，额度继续由现有 Budget Policy 负责。
- Source Repair Payload 提取至 `investment_answer.py`，不改变既有 Repair 行为。
- pytest 增加 `tests` 搜索路径，仅为历史测试模块解析，不改变 Production Python path、依赖或锁文件。
- `/questions` 的 deprecated 公共兼容 API、Aliyun Vision / OCR、Provider Factory、Settings、Ledger、
  Strategy、Migration、Tool implementation 和 Native Prompt 均保持不变。

## 清理验证与 Review

最终离线检查：

- `pytest -m 'not online and not integration' -q`：**1030 passed，99 deselected**。
- Ruff lint 与全目录 format check 通过（208 Python 文件）。
- mypy strict 通过（207 source files）。
- 新增 Production 依赖边界测试：发布包不存在旧 Loop / Completion Port，也不导入测试 Legacy 或旧 Adapter。
- 新增 Candidate profile 回归：由真实离线 Native Request 重算并比较冻结 profile，全字段一致。
- AST Review 确认四个 Tool Observation 函数主体与迁移前相同；旧 HTTP Adapter 与迁移前逐字节相同。
- `git diff --check` 通过；主线程完成引用、Contract、修复 Payload 与最小 diff Review。

途中测试目录命名导致导入失败、旧日志测试模块名不匹配，以及新增 AST 检查的类型收窄问题均已修复；
未删测试、弱化断言或放宽质量配置。独立 subagent 因工具默认模型 `gpt-6.0-luna` 不可用而未启动，
不声称完成独立 Agent Review。本次未读取 `.env`，未发送模型请求，未重跑 Browser / Online Eval。

## 验收 Candidate 未漂移

| 项目 | 清理后值 |
| --- | --- |
| PydanticAI | 1.107.6 |
| Runtime system prompt SHA256 | `34821d82b65d01e736a94378177b164bc6cc42045d00b1f0600b46cdb4831ef5` |
| Native output schema SHA256 | `8fc4671a333243ecfca2bd9e0ead8200c23882c85b8d0df8d24e78bd1fd99845` |
| Budget policy SHA256 | `76724d05b0f33e01dc5743ac6a5ba7fb46780d13cdc5d0ba54674399895bc0a4` |
| Tool Attempts / Model Requests | 7 / 8 |
| per-turn wall-clock | 60s |
| Strategy fixture SHA256 | `88938a2314c2a8ceadbc27fc4b02408e445f5c9405f4abcba0de6fa28bd93865` |
| Base fixture SHA256 | `f907a653bd0dfb2c731b6084151fa68b8edb8c28f1f947da89c0aed62d11e149` |

Framework retries=0；继承 V8 的有限 transport retry 与 source/citation repair，不新增策略。
Gemini 官方 `gemini-3.8-flash` 仍仅用于已批准 Eval，不将本次收口描述为 Production Provider Certification。
旧 Artifact 冻结 commit 保持原值；清理后的 commit 不伪装为曾执行在线 Baseline 的 commit。

## Git 收口与保留范围

开发分支为 `codex/phase4b-t6`；Legacy 清理与最终文档分别形成 Atomic Commit，随该分支合入本地 `main`。
本地 main 使用独立 `/private/tmp/position-pilot-phase4-main` 工作树，避免覆盖原根目录的未提交修改；
主线程在合并后核验 feature tip 为 main ancestor、main 工作树干净以及原目录状态未变。
实际 Commit / Merge SHA 以 Git History 与本次交付消息为准，不 Push、不删除任何旧分支或冻结工作树。

当前 Phase 4 已启用范围验收完成。AQ04 Earnings、AQ01/AQ02/AQ19 Research / Web Search、完整自动 Memory、
Production Provider Certification 继续延期；它们没有被记为 PASS，也不阻塞本次已批准范围。
T8 原生删除 confirm 未完成等证据限制继续保留，详见[T8 最终报告](2026-10-05-phase4-t8-final.md)。
不新增 Release / Tag，不自动启动下一阶段。
