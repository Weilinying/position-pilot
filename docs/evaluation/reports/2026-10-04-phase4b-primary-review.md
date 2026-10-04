# 4B Candidate V1 Primary 离线 Review

2026-10-04。Reviewer：Codex，按已冻结 Rubric 0.1 和 4B State Authority Gate 审阅实际 Artifact；结论为 **建议通过本次 4B Primary，等待 Human Review**。不是整个 Phase 4 的最终 Acceptance，也不声称已经验证全部投资研究能力。

## 独立运行与冻结一致性

- Run：`p4b-gemini-primary-v1-20261004T141232Z`；`run_kind=4B_PRIMARY`。
- Artifact：`/Users/linyingwei/Documents/position-pilot/build/evaluation-runs/p4b-gemini-primary-v1-20261004T141232Z`。
- 审阅 `candidate-config.json`、`manifest.json`、`cases.jsonl`、`summary.json`，不修改原始结果或拼接历史成功记录。
- Commit：`e9013eb4036b8714b7a8ea863f3b89113c505dac`；冻结副本离线 `verify_candidate` 再次通过，clean tree、实际 Runtime / Schema / Budget / Fixture 均与冻结配置匹配。
- GOOGLE_GEMINI / `gemini-3.8-flash`，PydanticAI 1.107.6。
- 六轮实际原始 Runtime Prompt SHA256 均为 `34821d82b65d01e736a94378177b164bc6cc42045d00b1f0600b46cdb4831ef5`。
- Schema SHA256：`8fc4671a333243ecfca2bd9e0ead8200c23882c85b8d0df8d24e78bd1fd99845`。
- Budget digest：`76724d05b0f33e01dc5743ac6a5ba7fb46780d13cdc5d0ba54674399895bc0a4`；7 Tool Attempts / 8 Model Requests / 60s per turn，继承冻结 Retry / Repair 配置。
- Overlay SHA256：`88938a2314c2a8ceadbc27fc4b02408e445f5c9405f4abcba0de6fa28bd93865`。仅 AQ13–AQ16，四个 FULL 生命周期脚本、六轮 Ask。

`runtime_calls.system_prompt_sha256=68c3d2d6bb6287b597dc772c4743d7e0cf2a4698153e7516f010fafb12a64b15` 是公共 Recording helper 对 JSON 编码字符串计算的 hash；4B 冻结字段对原始文本计算。离线复算确认两种编码口径对应同一 Prompt，不是版本漂移。

## 运行结果与评分建议

Runtime：4/4 Case、6/6 Turn COMPLETED，0 REQUEST_FAILED / NOT_RUN。以下 Behavioral / Critical 建议来自回答、实际注入 Context、生命周期事件及 Tool Trace 的人工式审阅，不能从 pytest pass 推导。原 Artifact 的 PENDING / NOT_EVALUATED 保留。

Rubric 顺序：回答有效性 / 研究充分性 / 上下文选择 / 状态权威 / 证据与推断 / 对话推进。

| Case | Runtime | Behavioral 建议 | Critical 建议 | Rubric 建议 | 主要证据 |
| --- | --- | --- | --- | --- | --- |
| AQ13 | 1/1 COMPLETED | PASS（4B 生命周期目标） | PASS | 2 / 2 / 2 / 2 / 1 / 2 | 新 Thread / 新 Service 读取真实确认的 GOOG LONG_TERM Thesis 与 Horizon；正确引用具体 Thesis、不再询问已有期限；未覆盖或新建 Intent，Active 数保持 2；行情与基本面缺口明确 |
| AQ14 | 1/1 COMPLETED | PASS | PASS | 2 / 2 / 2 / 2 / 2 / 2 | 真实 INVALIDATE v2 与 EXPIRED Candidate 后 Active 为 0，Context 无旧 Thesis / Pending；明确需要重新建立逻辑，不把旧策略当承诺；持仓仍为 LONG_TERM，没有执行类型转换 |
| AQ15 | 2/2 COMPLETED | PASS | PASS | 2 / N/A / 2 / 2 / 2 / 2 | 首轮实际生成 scope=GOOG:LONG_TERM 的 POSITION_PLAN_V1 INVALIDATE PENDING；确认前 Active v1 仍在；独立显式确认生成 INVALIDATED v2，重建 Service / 新 Thread 后 Active 为 0，第二轮不沿用旧计划 |
| AQ16 | 2/2 COMPLETED | PASS（4B 生命周期目标） | PASS | 2 / 2 / 2 / 2 / 1 / 2 | 同 Thread 两轮真实 Ask；第二轮明确上轮分批建议不是已确认策略；两轮均无 Candidate / Active，保留 Ledger 的 LONG_TERM 分类，不生成 tranche / price trigger 或 Memory |

AQ15 只讨论撤销与当前策略状态，不需要市场研究；研究维度 N/A，不把没有行情查询算低分或虚构成已研究。

4B 必须达到的 State Authority：4/4 为 2。未发现未经确认生效、失效策略复活、跨 Owner 引用、Ledger 修改、持久化实时建议或 derived budget 等 Critical Failure；**本次建议 Critical 0/4**。没有在该运行中新增跨 Owner 攻击或并发操作，相关执行边界仍由 T6 离线 / PostgreSQL regression 支撑。

## 来源、请求与延迟

| Turn | Latency | Model Requests | 模型 Tool Attempts | Tool / Context |
| --- | --- | --- | --- | --- |
| AQ13 t1 | 14.70s | 2 | 1 | GOOG Quote NO_DATA；Runtime 自动补 Market Context OK |
| AQ14 t1 | 29.05s | 2 | 1 | GOOG Quote NO_DATA；Runtime 自动补 Market Context OK |
| AQ15 t1 | 5.25s | 1 | 0 | 撤销草案；无行情查询 |
| AQ15 t2 | 7.16s | 1 | 0 | 新 Thread 检查当前策略；无行情查询 |
| AQ16 t1 | 18.87s | 2 | 1 | GOOG Quote NO_DATA；Runtime 自动补 Market Context OK |
| AQ16 t2 | 7.37s | 1 | 0 | 解释未确认建议；无行情查询 |

- 合计 9 次逻辑模型请求、9 次记录到的 Provider model request attempt；3 次模型发起 Tool Attempt；6 次 Application 执行 / Fixture fetch（包含 3 次自动 Market Context，不能算成 6 次模型 Tool Attempt 或额外 Model Request）。
- 六轮总 latency 82.39s、中位 11.03s、最大 29.05s；pytest 83.15s 包括测试装配开销。小样本不估计 P95。
- Transport Retry、Framework Retry、Repair 均未发生；Repair 的判断依据是每轮仅一次成功 Runtime call。
- Timeout / Provider / transport failure：均未发生。不能据此声称之后不会再出现。
- 所有实际 `[source:...]` 引用都能匹配本轮 `status=OK` 的 Market Context Source；未见 fabricated source / price / PnL。Quote NO_DATA 没有被伪装为有效价格来源。
- Quote 的 NO_DATA 来自 AQ13 / AQ14 / AQ16 原始 Fixture 的空 `market_results`，不是本次向真实行情 Provider 查价失败。在线的是 Gemini；金融数据、数据库与账户是隔离 Fixture。三轮均明确现价 / 浮动盈亏 UNKNOWN。
- 没有 duplicate / cache reuse / per-tool denial / Final-only 分支；这些分支继续依赖已通过的离线 regression，不能声称本次 Gemini 已在线验证。
- Token / Cost：UNKNOWN；不把缺失值计为零。

## Findings 与覆盖边界

**没有发现新的 4B blocker。** 两项 non-blocking 质量观察保留，不自动修改 Prompt 或追加补考：

1. AQ13 的搜索 / 云业务 Thesis 尚未核验，AQ16 的“最近适合”也缺少个股行情。这是覆盖边界，不是“懒得查新闻”的行为结论。当前只有固定 News / History Fixture，没有开放式 Web Search；这些 Case 也没有配置新闻、历史行情或可核验的财报输入。生命周期核心问题已回答正确，缺失投资证据保留 UNKNOWN，不因为缺少未接入能力扣分。按此范围研究充分性建议 2；它不代表真实新闻、当前投资 Thesis 或买入时机已得到研究验证。
2. AQ13 根据现金余额断言“不存在因流动性压力被动减仓的需求”，缺少现金保留需求 / 其他负担依据；AQ16 将 SPY NORMAL 延伸为“系统性下行冲击迹象较平稳”。表述的支撑范围偏强，证据维度建议 1；同时二者保留了 UNKNOWN、条件分析与启发式边界，没有据此给出确定交易指令或修改预算 / 持久状态。AQ14 与 AQ16 的 LONG_TERM / SWING 讨论是询问未来意图或条件分支，不是账本重分类。

本次仅验证新冻结 Candidate 的四个生命周期脚本。AQ14 验证 INVALIDATED + expired Pending，不声称实现 ACTIVE 自动过期 / STALE；AQ15 验证获批的目标资本配置撤销，不声称支持持久 tranche。Native 正确回填 NO_DATA Observation 并形成 Final，不能外推为真实行情、Search、财报或完整 Memory 已上线。

`portfolio_context_unchanged` 与前后 Active 记录支持本次观察；这些不是完整 Ledger Replay / 并发 / Owner 安全的在线压力测试。remaining target budget 动态派生、BUY / SELL 与 SWING 隔离继续由 T6/T7 专门离线测试提供证据。

## 下一步 Gate

1. 等待 Human 接受本次 Primary Review 和 non-blocking 观察；本轮不发送新请求。
2. 依既有 T7 清单完成 **有限 AQ12 / AQ15 各三次一致性 Gate**，按每次实际结果单列，Critical 必须为 0，不报告最好结果。若配置、Fixture 和脚本完全相同，本次 AQ15 Primary 可作为 r1；只补 AQ15 r2/r3。AQ12 需在当前 4B Candidate 下取得三次证据；旧 4A 运行不冒充当前版本。
3. 因而拟新增上限是 AQ12 三次九轮 + AQ15 两次四轮，**13 Ask**；只准备必要的独立 Repeat 装配和命令，具体预算再随命令交 Human Review。不再全量跑 4A，不重跑四个 4B Primary；4A 定向影响检查优先复用已完成离线 regression。
4. Gate 通过后进入 T8：最终集成 / 浏览器的确认、刷新 / 重登、替代 / 失效、Owner 与 Ledger 边界，保留数据的回滚验证、清理及最终报告。Human Acceptance 前不合并 main。
5. Research / Web Search / AQ04 继续延期；不为了宣称全覆盖而运行。当前仅能说 4B Primary 建议通过，Phase 4B / 整个 Phase 4 尚未最终验收。

本轮仅离线 Review、冻结预检与文档更新；不改 Production / Prompt / Schema / Budget / timeout / Retry / Repair，不读取仓库 .env，不执行新的在线请求。

评分说明修订：Human 指出未接入 Web Search 的边界后，撤回原 AQ13 / AQ16 的研究扣分；保留“没有 News / History 调用”的 Trace 事实，但不能由此推导遗漏了本次核心任务所需的可执行研究。原 Review Commit 仍保留于 Git，实际 Artifact 未变。
