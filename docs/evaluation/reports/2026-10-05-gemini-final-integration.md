# Gemini Production Final / Phase 4B 最小整合 Candidate

2026-10-05。状态：**OFFLINE VERIFIED / FROZEN；ONLINE NOT RUN；MAIN NOT MERGED**。

后续（2026-10-06）：原 Smoke 已由用户执行并取得技术 PASS；
[有限 Provider 回归](2026-10-06-gemini-production-regression-review.md)取得 8 Cases / 12 Turns、Critical 0/8，
Human 已接受 AQ06 / AQ13 原扣分作为本次质量偏差例外，并允许本地合并。
不解释为全面 Production Quality Acceptance；下文保留离线 Candidate 交付时的历史状态和移植范围。

- 权威基线：`main = 0d36e786b9f09b2e39c4a53630960b4bce4aaae4`，完整 Phase 4A / 4B 保留。
- 整合分支：`codex/gemini-final-phase4b-integration`，从干净 main 新建。
- 源码 Commit：`3638eff7abc8d870c0e7ec525661863bb41badfe`。
- 冻结文件：[Gemini Production Smoke Candidate](2026-10-05-gemini-production-smoke-candidate.json)。
- Candidate：`gemini-production-final-smoke-2026-10-05-v1`，等待用户另行批准在线执行。
- `OPEN_WEB_RESEARCH = DEFERRED`。没有执行获准在线 Smoke、Merge 或 Push。

## 1. 从 Stash 实际移植的最小逻辑

审查了 `911862ad` 相对第一 Parent 的 tracked diff，以及第三 Parent 的 untracked 文件。
没有 apply / pop；原 Stash 与 `codex/archive-root-deferred-research-20261005` 均完整保留。

| 当前文件 | 功能移植 / 复用方式 |
| --- | --- |
| `backend/position_pilot/integrations/gemini_runtime.py` | 从 Stash 第三 Parent 提取官方 GoogleProvider / GoogleModel 工厂；固定官方端点，独立 Key，每 Run 同 Event Loop 创建 / 关闭 Client，SDK attempts=1、framework retries=0。仅调整说明为当前 Phase 4B 边界。 |
| `backend/position_pilot/integrations/pydantic_ai_runtime.py` | 只增加 5 行 GOOGLE_GEMINI Factory 分支。NativeOutput 与当前 Strategy Native Schema 已存在于 main，直接复用；不复制旧 Runtime 主体。 |
| `backend/position_pilot/config.py` | 只新增 SecretStr 的 gemini_api_key，并将默认 Provider / Model 改为 GOOGLE_GEMINI / gemini-3.8-flash。 |
| `backend/position_pilot/bootstrap.py` | 独立 VISION_API_KEY 优先；仅显式 ALIYUN_MODEL_STUDIO Final 保留 LLM_API_KEY fallback。Gemini Key / 无关 LLM Key 不会发送到 Aliyun OCR。 |
| `pyproject.toml`、`uv.lock`、`.env.example` | 仅整合 Google production extra、独立凭据与默认配置；不照搬旧环境模板或 Provider 集合。 |

Provider / Config / Bootstrap 测试按当前 main 重写或补充。新 Smoke 与冻结工具是本轮离线验收入口，
没有复制旧 Research R2/R3 入口，也没有把历史 PASS 改名为当前版本的 PASS。

## 2. 明确没有移植的修改

- `gemini_research.py`、`research_tools.py`、Research Gateway / web_research 装配、Google Search。
- WEB_RESEARCH Source / grounding metadata 扩展、Research UI、quota、attribution、Search Suggestions。
- Brave / Tavily / Exa / Page Fetch、Bedrock / AWS 配置与额外 dependency。
- Stash 中旧 agent_runtime / native_investment_agent / investment_agent / conversation_agent / Prompt、
  Source Registry / Tool Catalog，以及旧 Phase 4 Harness、Strategy / Conversation 修改。
- 旧 Research Proposal / ADR 0016、0017 / R0～R3 Artifact 没有整体搬入当前整合分支。
  它们仍留在原封存引用；未删除、不宣称 Production Acceptance。
- 历史 Phase 4 验收报告未改写；AQ01 / AQ02 / AQ19 开放研究仍 DEFERRED / NOT_MEASURED，
  AQ04 财报仍独立 Diagnostic，不能据本次 Final 接线记为 PASS。

对 main 的实际 diff 核对：Application、Domain、API、Repository、frontend、alembic、Strategy 测试
及既有 Phase 4 Harness 均无变更。当前 Prompt / Native Schema / Budget / Fixture hash 与已验收 main
全部一致；生产仍为 7 Tool Attempts / 8 Model Requests / 60s。
同 scope / kind 的 ACTIVE 与 PENDING 语义、显式确认、Conversation Authority、Ledger 和动态
remaining_target_budget 都继续使用 main 实现，无 Migration 或公共 API Contract 变更。

## 3. Dependency / Config Diff 与最终模板

- `pydantic-ai-slim[openai]==1.107.6` → `pydantic-ai-slim[google,openai]==1.107.6`。
- 复用锁内 `google-genai==2.25.0`；未升级现有 package，未加入 Research Provider。
- 离线重生成 lock 时清理两个不再被任何依赖引用的旧条目：python-dateutil / six；
  `uv lock --check --offline` 通过，解析 105 packages。
- Google Final 不读取 LLM_BASE_URL / LLM_API_KEY，也不回退到 Aliyun。
- OCR 继续 Aliyun `qwen3-vl-flash`；Gemini 模式必须显式提供独立 VISION_API_KEY。
- `.env.example` 的 RESEARCH_ENABLED=0 只是关闭意图声明，Settings 不消费；即使设置 1 也不会
  暴露 Search。原有 Phase 3 实验字段不是本轮新增接线。

完整最终模板见仓库根 [.env.example](../../../.env.example)。主要 Production 配置如下：

```dotenv
# 保留已有 DATABASE_URL、Alpaca、Finnhub 等本地配置；不要把实际 Secret 提交到 Git。
LLM_PROVIDER=GOOGLE_GEMINI
LLM_MODEL=gemini-3.8-flash
GEMINI_API_KEY=
NATIVE_LLM_REQUEST_TIMEOUT_SECONDS=60

# 仅显式选择 Aliyun / compatible Final 时使用；Gemini 不读取这两项。
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=
LLM_REQUEST_TIMEOUT_SECONDS=30

VISION_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
VISION_API_KEY=
VISION_MODEL=qwen3-vl-flash
VISION_REQUEST_TIMEOUT_SECONDS=30

# OPEN_WEB_RESEARCH = DEFERRED；此声明没有 Production 启用效果。
RESEARCH_ENABLED=0
```

没有读取或修改实际 `.env`；代码默认值不会覆盖用户已有的显式环境变量。

## 4. 验证与 Review

| 验证 | 实际结果 |
| --- | --- |
| Provider / Config / Bootstrap / NativeOutput / Tool Runtime / Strategy Runtime / 新 Smoke 定向测试 | 96 passed |
| Strategy、Conversation、Native Agent、Funding、4B Continuity 直接回归 | 111 passed |
| 完整离线：pytest -m 'not online and not integration' -q | 1047 passed，99 deselected；Review 小修后重新执行，仍全部通过 |
| Ruff lint：backend tests alembic | PASS |
| Ruff format --check：backend tests alembic | PASS，225 files |
| mypy strict：backend tests | PASS，212 source files；Review 小修后重跑 |
| uv lock --check --offline / git diff --check | PASS |
| 独立只读 Automated Review | 无阻断性 P1/P2；重复 boolean 条件已去重并重新验证 |
| Candidate freeze / 实际离线 preflight | FROZEN_OFFLINE / PREFLIGHT_PASS_AWAITING_USER_EXECUTION |

MockTransport 通过真实 Production Factory / Google SDK / PydanticAI / Native Agent，验证
Quote FunctionCall → FunctionResponse 的结构化 Source metadata → Native JSON / 有效引用 →
当前 4B Typed Candidate；也覆盖缺 Key、凭据隔离、客户端生命周期与禁重试边界。
离线 PASS 不等于真实模型质量、数据库持久化、浏览器或在线 Production Acceptance。

**测试安全遗漏：** 首次含未完成草稿测试的全量尝试中，一项脱敏测试遗漏了 Mock，可能以固定假 Key
尝试 Google 连接；没有使用真实凭据，但不能证明未发生连接尝试。该次运行不列为严格离线证据。
已改为显式注入异常，并在两个新增 Gemini 测试模块加入真实 Transport 禁网防线和自检，再重新执行
上述完整检查。原因与主线程责任见 [Engineering Note](../../engineering-notes/2026-10-05-gemini-offline-transport-boundary.md)。

## 5. 冻结边界

Candidate 绑定源码 Commit、全部 backend Python、dependency / lock / 模板、Smoke / Fixture 源码的
Git blob 与 SHA256，以及实际 4B Request 重算的 Prompt、Schema、预算、Fixture Profile。
关键源码未提交、漂移、版本漂移或 source_commit 不是 HEAD 祖先时拒绝在线执行；允许之后只增加
Artifact / 文档的提交。不能复用旧 R2 Candidate 或已有 Artifact 目录。

生产配额保持 7 / 8 / 60s。仅这次最小 Smoke 限制为最多 **2 次模型请求、1 次固定 Quote Tool、
0 Application Final Repair、0 Framework / SDK Retry、60s**，不改生产预算。
Smoke 使用固定 Portfolio / Quote，不访问数据库、不调真实金融 API、不提供 Search，不确认或
写入 Strategy；PASS 只证明接线及草案 / 引用的技术路径。

## 6. 最小 Online Smoke 命令（只提供，未执行）

在此分支运行；假设当前终端已导出 GEMINI_API_KEY，不需要创建 / source `.env`、激活虚拟环境
或配置数据库。该命令会调用 Google，须用户单独批准后执行：

```bash
cd /Users/linyingwei/Documents/position-pilot
RUN_GEMINI_PRODUCTION_SMOKE=1 PYTHONPATH=backend:tests uv run --frozen python tests/evaluation/gemini_production_smoke.py --online --candidate docs/evaluation/reports/2026-10-05-gemini-production-smoke-candidate.json --artifact-dir artifacts/gemini-production-final-2026-10-05-attempt-1
```

不接受、覆盖或自动续跑已有 Artifact 目录；失败后保留证据，不自动 Retry / Repair / 换 Provider。
结果写入指定目录 smoke.json，behavioral_status 始终为 NOT_EVALUATED。

## 7. 建议单独批准的最小 Phase 4 回归集

先审最小 Smoke，再考虑如下 **8 Cases / 12 Model Turns、各执行一次** 的有限新回归：

- AQ06：金额 / Quote / Ledger Cash 解释与权威边界。
- AQ12（三轮）：GOOG → MSFT → GOOG，不串 Source 或 Conversation Context。
- AQ13～AQ16（共六轮）：已确认 Thesis / Horizon、新旧计划失效、显式确认、跨 Thread 读取，
  未确认模型建议不能升级为用户既定 Strategy；不影响账本。
- AQ17a / AQ17b：无新闻结果与 News Provider Failure 的区别；不引入 Search 兜底。

回归必须使用本次 Production Factory / 当前 4B Runtime，不能以旧 Eval 专用接线代替。
这是建议，不是已执行的新 Acceptance。AQ12 / AQ15 的重复稳定性 Gate 如需要，再另批 Repeat；
不自动扩大为全 Phase 4 Online / Browser、AQ04 Earnings 或开放 Research。

本轮新增 ADR 0018 与测试边界 Engineering Note；没有新 Milestone Plan，没有重开 T6～T8。
当前应交由 Human Review 决定在线验证与后续合并，main / 原 Stash 保持原样。
