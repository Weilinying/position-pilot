# AGENTS.md

## 1. 文档职责

本文件规定 Coding Agent 在 PositionPilot Repository 中必须遵守的开发、测试、Review 和 Git 规则。

文档职责：`PROJECT.md` 定义产品与 V1 边界；`ROADMAP.md` 定义 V1 Milestone；`docs/plans/` 保存复杂 Milestone 的执行计划；`docs/adr/` 记录重要技术与架构决策；`docs/engineering-notes/` 记录值得长期保留的 Failure、设计权衡和实现边界；`ARCHITECTURE.md` 在骨架稳定后描述系统当前实际架构；本文件只规定开发行为。

执行非简单任务前，必须阅读 `PROJECT.md`、本文件以及任务相关代码和测试。仅当任务涉及 Milestone 规划、范围判断或跨模块 Feature 时读取 `ROADMAP.md` 的相关 Milestone；仅按需读取相关 ADR 和 `docs/plans/`。不要只根据最新 Prompt 开发而忽略已有约束。

## 2. 默认开发方式

默认流程：

```text
理解需求
→ 检查现有实现
→ 明确 Acceptance Criteria
→ 必要时拆 Task
→ 实现最小完整修改
→ Tests / 已配置质量检查
→ Automated Review
→ 根据 Review 修复
→ 再次运行相关 Tests / 质量检查
→ 验证实际行为
→ Atomic Commit（适用时）
```

Reviewer 原则上应审查一个已经通过基础测试和已有质量检查的版本。Review 引起代码修改后，必须再次执行受影响的测试和质量检查，避免引入 Regression。

复杂 Feature 或 Milestone 可以在 `docs/plans/` 中生成执行计划；普通小任务不要求创建 Plan。

优先选择简单、清晰、可验证的方案。任何新增 Agent、Framework、Database、Infrastructure 或复杂 Abstraction，都必须说明它解决了哪个已经存在的问题。

## 3. Codex Subagent

不要为了开发 PositionPilot 预先构建独立 Agent Framework。优先直接使用 Codex 已有能力：explorer 类能力适合代码库探索、依赖分析和测试定位；worker 类能力适合边界清楚的实现、修复和测试任务。

Codex 主线程可以承担 Planning、任务拆分和普通 Review，不要求项目启动前创建自定义 Planner 或 Reviewer。只有出现真实 Failure Mode，例如复杂 Milestone 经常拆错或 Review 持续遗漏同类问题时，才考虑在 `.codex/agents/` 中增加自定义角色。

Codex subagent 属于开发工具，不属于 PositionPilot 产品架构。涉及同一核心模块、同一公共接口或存在明确依赖关系的写任务默认串行；只有真正独立且修改范围不冲突的任务才并行。

## 4. Human Review Gate

普通实现、内部重构、测试补充、已批准设计范围内的 Bug Fix 和不改变产品语义的内部代码调整，可在 Automated Review 与 Tests 通过后继续执行，不要求逐 Task 人工确认。

以下变化必须暂停相关后续工作，先给出简短 Decision Proposal 并等待 Human Review：

* 修改 `PROJECT.md` 定义的产品语义或 Domain Invariants；
* 选择或更换核心 Framework、LLM / Market / News / Financial Data Provider；
* 引入新的 Database、Cache、Queue 或其他重要 Infrastructure；
* 显著修改核心 Domain Model 含义、关键金融计算或 Market Regime 规则；
* 修改对外公共 API Contract；
* 执行破坏性 Database Migration；
* 修改 Security、Credential、权限或敏感数据处理方式；
* 改变主要 Agent、Memory 或系统架构；
* 当前需求存在会影响用户可见行为的关键歧义，且无法从 `PROJECT.md`、ADR 或已有实现中确定唯一合理解释；
* Milestone 完成并准备合并到 `main`。

普通实现细节存在多个等价方案时，不触发 Human Review Gate。Agent 应遵循现有架构和代码规范，选择最简单、最一致的合理实现。

Human Review 关注产品方向、架构选择、关键业务正确性和 Milestone Acceptance，不要求逐行审核所有 AI 代码。Human 已批准决策后，AI 可以直接整理对应 ADR，无需再次因“写 ADR”请求批准。

## 5. Python 工程原则

代码优先保证可读性、明确职责、低耦合、可测试性和合理复用。采用轻量 DDD / Clean Architecture 思想，但不要机械复制 Java 的复杂模式。

推荐依赖方向：`API → Application / Services → Domain`，Repository / Infrastructure / Integrations 为外部实现。API 层只负责请求接收、校验和 Response；核心业务规则不得散落在 API Handler、Prompt 或数据库访问代码中。

Domain 层原则上不依赖 FastAPI、具体 ORM、具体 LLM SDK 或具体金融数据 Provider。Agent 负责意图理解、Context / Tool 选择和结果综合，不直接到处操作数据库实现细节。

有状态、有领域身份或包含多个相关行为时可以使用 Class；无状态计算、转换和校验优先使用 Function。优先组合而不是复杂继承。

## 6. 模块、复用与命名

模块、类和函数应职责清晰。若一个函数同时负责数据获取、业务计算、Prompt 构建、LLM 调用和持久化，应检查是否需要拆分。

单个 Python 文件通常尽量保持在约 300–400 行以内；超过约 500 行时应检查是否职责过多，但不要仅为满足行数限制机械拆文件。

新增功能前先搜索已有实现。稳定且重复的业务规则、金融计算、数据转换、Validation 和外部 API 封装应优先复用；少量偶然相似代码不要求立刻抽象。避免把无关逻辑堆入 `utils.py`、`helpers.py` 或 `common.py`。

代码标识符统一使用英文并表达真实意图。核心业务代码必须使用 Type Hints；稳定的 API Request / Response、Tool Input / Output、Domain Model 和 Structured LLM Output 应使用明确 Schema。

## 7. 中文注释

所有代码注释和 Docstring 必须使用中文；类名、函数名、变量名等代码标识符仍使用英文。

注释主要解释“为什么这样做”、不明显的业务规则、重要约束、算法 / 金融逻辑和临时兼容方案，不重复代码表面已经清楚表达的行为。

普通注释使用 `# 中文说明。`；特殊注释仅使用 `# TODO:`、`# NOTE:`、`# FIXME:`，并说明具体事项或原因。

公共接口、核心领域逻辑和不直观算法应编写中文 Docstring；简单私有函数不强制。Docstring 使用三引号，并按需要使用“参数:”“返回:”“异常:”章节，没有对应内容时省略。

## 8. Domain Invariants

具体产品语义以 `PROJECT.md` 为准，以下约束不得破坏：

* Portfolio、Cash、Transaction、Average Cost 和 Position Type 属于 Structured State，并作为持仓事实的 Source of Truth；
* `LONG_TERM` 与 `SWING` 必须独立维护，同一 Ticker 可以同时存在两类仓位；
* 平均成本、金额、仓位比例、RSI 等可确定计算的金融事实不得交给 LLM 猜测；
* 当前价格、当天行情、VIX、最新新闻、最新财报和当前估值必须来自足够新的外部数据；
* Agent Routing 在相关场景下应综合 User Intent、Portfolio Context 和 Market Context；
* Tool 输出应结构化、失败状态明确并可独立测试；
* 金融分析必须区分 `FACT`、`INFERENCE` 和 `UNKNOWN`。

V1 不因为存在 Memory 需求就自动引入 Vector Database，也不因为项目属于 Agent 就自动升级 Multi-Agent。

## 9. LLM、Tool 与 Error Handling

LLM 负责意图理解、Context / Tool 选择、多来源综合和条件式 Decision Support；能够通过确定性代码完成的查询、计算、Validation 和明确规则判断，应由普通程序负责。

Tool 必须职责单一、输入明确、输出结构化、失败行为明确且可测试。Agent 只调用当前问题真正需要的 Tool。

不要静默吞掉异常。正常空结果与 Provider Failure 必须可区分，例如 `NO_NEWS_FOUND` 与 `NEWS_PROVIDER_UNAVAILABLE` 不能视为同一状态。关键数据获取失败时不得编造缺失信息。

## 10. Database、Config 与 Logging

Database Schema 变化必须通过 Migration 管理，不得把手工修改数据库作为正常开发流程。破坏性 Migration 必须进入 Human Review Gate。

API Key、Database Credential、Authentication Token 和其他 Secret 不得硬编码或进入 Git Commit。运行时配置使用 Environment Variables 或已批准方案；Repository 维护 `.env.example`，但不得包含真实 Secret。

Coding Agent 禁止读取仓库中的 `.env` 或 `.env.*` 文件内容，以避免 API Key、Credential 或其他 Secret 泄露；`.env.example` 除外。不得使用 `cat`、`sed`、`rg`、脚本或其他方式输出、解析或间接读取这些文件。

核心 Agent / Tool 流程应提供足够的结构化日志，以定位 Context Selection、Tool Call、Tool / Provider Failure 和关键 Latency；不得记录 Secret 或没有调试必要的敏感用户数据。V1 不因 Logging 需求自动引入完整 Observability Platform。

## 11. Testing

新增或修改核心行为时必须补充相关测试，重点覆盖 Portfolio Calculation、Transaction Processing、Position Type、Cash Update、Market Context / Regime、Tool Validation、Context Construction、Routing 和 Error Handling。

Unit Test 不依赖真实 LLM API 或真实金融 API，外部 Provider 应 Mock。确定性业务逻辑应尽量与 LLM 隔离，使其能够独立测试。

实现完成后，先运行相关 Tests 和项目已有的 Formatter / Lint / Type Check，再进入 Automated Review。根据 Review 修改代码后，必须重新运行受影响的 Tests 和质量检查。

不得仅为满足本条规则擅自引入新的质量工具。没有实际执行的检查不得声称通过；测试失败不得通过删除测试、弱化断言或静默忽略错误制造绿色结果。

## 12. Git Workflow

一个 Commit 对应一个独立、完整、可解释且可验证的 Logical Change。一个 Commit 可以修改多个强相关文件，但不得混入无关 Feature、顺手重构或全仓库格式化；一个 Feature 或 Milestone Workstream 可以包含多个 Atomic Commits。

### Milestone 自动开发

当用户明确要求“开始、实现、完成、继续开发某个 Milestone”时，默认视为已授权该 Milestone 的本地 Git 工作流，除非用户明确要求不要进行 Git 操作。

开始 Milestone 前：
- 检查当前 Git 状态；
- 不得覆盖用户已有的未提交修改；
- 如当前不在适合直接开发的 Feature Branch，应为该 Milestone 创建独立 Branch。

开发过程中：
- 每完成一个独立、完整且通过相关测试与 Review 的 Logical Change，应创建 Atomic Commit；
- Commit Message 使用 Conventional Commits，如 `feat:`、`fix:`、`refactor:`、`test:`、`docs:`、`chore:`；
- 不为了制造 Commit 数量机械拆分修改；
- 不提交已知无法通过相关验证的中间状态。

Milestone 完成后：
- 保持本地 Commit History 清晰；
- 汇总 Branch 名称和本次产生的 Commits；
- 在 Human Acceptance 前不得自动 Merge 到 `main`。
- 当用户明确完成或通过当前 Milestone 的 Human Review / Human Acceptance 时，视为已授权将当前 Milestone Branch 的全部修改合并到本地 `main`；Agent 应在最终验证通过后直接完成合并，无需再次请求 Merge 授权。
- 合并完成后应确认 Milestone Branch 的全部提交均已进入本地 `main`，并汇总 Merge 结果；除非用户另有明确要求，不得因此自动 Push、删除 Branch 或改写历史。

未经明确授权，不得 Push 远程仓库、Merge `main`、Force Push、重写已共享历史或删除远程 Branch。

普通单次问答、局部修改或用户未要求完整执行 Milestone 的任务，不默认创建 Branch 或 Commit。
## 13. Roadmap、Plan、ADR、Engineering Notes 与 Architecture

`ROADMAP.md` 只定义 V1 Milestone 的 Goal、Scope 和 Done Criteria。仅在 Milestone 规划、范围判断或跨模块 Feature 中读取相关部分，不要求普通任务全文加载。

`docs/plans/` 用于复杂 Milestone 的执行级 Task Decomposition，按当时 Repository 的真实状态生成；普通任务无需创建。

`docs/adr/` 只记录重要且具有长期影响的技术或架构选择。ADR 应说明背景、候选方案、最终选择、理由、Trade-off 和重新考虑条件，不记录普通 Feature 流水账。技术尚未决定时保持“未决定”。

`docs/engineering-notes/` 记录不足以上升为 ADR、但值得长期保留的工程判断，例如系统性 Eval / Bug Failure、重要设计权衡、Scope Trade-off、Agent 行为边界和非直观实现决策。

满足以下情况之一时，应检查是否需要新增或更新 Engineering Note：
- Eval 或 Bug 暴露出可重复的系统性 Failure Mode；
- 在多个合理方案之间做出有意义的取舍；
- 明确划分 Prompt、Tool、Code、Memory 或 Context 的职责边界；
- 明确决定暂不实现某项看似合理的能力；
- 实现方式不直观，未来仅阅读代码难以理解其原因。

Engineering Note 应保持简短，优先记录 `Problem → Decision → Alternatives / Trade-off → Trigger / Future`。普通 Bug Fix、显然的实现细节和可直接从代码或 Git History 理解的修改不单独记录。

任务完成或 Automated Review 后，应检查本次修改是否产生新的 ADR、Engineering Note 或 Architecture 更新需求，但不得为了完成流程机械创建文档。

`ARCHITECTURE.md` 在第一版工程骨架稳定后建立，用于描述系统当前实际结构；主要模块边界变化时应同步检查是否需要更新。
## 14. 完成任务

任务完成前应确认 Acceptance Criteria 已满足、相关 Tests 和已配置质量检查已经运行、Automated Review 中需要解决的问题已处理、Review 后的修改已重新验证、实际行为符合预期且没有无关修改。

非简单任务最终简要说明：实现了什么、为什么这样实现、涉及哪些文件、运行了哪些检查、仍有哪些已知限制，以及是否产生新的 ADR / Engineering Note / Plan / Commit 或触发 Human Review Gate。

**Simple first. Reuse existing logic. Test it. Review it. Test again. Then evolve.**
