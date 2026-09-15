# Ask Quality Baseline — qwen3.7-max — 2026-09-15

## 1. 状态

**Status:** PHASE 1 EXECUTION COMPLETE — AWAITING HUMAN ACCEPTANCE

本报告是 Phase 1 当前正式质量基线。真实模型全量运行与五个关键变体的三次重复均已成功完成；
五份代表性回答已经完成用户校准，Rubric 解释、31 次执行的正式评分、全部 Critical Gate 和 Failure
Map 均已冻结。本报告不修改 Production Prompt、Agent、Tool 或 Phase 2 设计文档；Phase 1 分支在
Human Acceptance 前不合并到 `main`。

先前 `qwen3.7-plus` 运行只完成 14 / 31 个 Case；失败均被 Adapter 归类为 Authentication Failure，
具体 Provider / Credential 根因无法从 artifacts 独立确认。用户后续说明旧模型额度已经耗尽，该信息
作为用户补充保留。旧运行作为 Provider Reliability 事件保存，不与本报告的回答质量统计混合。

原始记录位于 Git 忽略目录：

```text
build/evaluation-runs/ask-quality-baseline-qwen37max-20260915/
  r1/{manifest.json,cases.jsonl,summary.json}
  r2/{manifest.json,cases.jsonl,summary.json}
  r3/{manifest.json,cases.jsonl,summary.json}
  review.json
```

三轮运行文件保持原始输出不变；`review.json` 是后置 Human Review 层，避免人工评分改写模型回答或
Tool Trace。

## 2. Run Metadata 与完整性

| 项目 | 值 |
|---|---|
| Run ID | `ask-quality-baseline-qwen37max-20260915` |
| Dataset / Rubric | `ask-quality-discovery 0.1` / `0.1` |
| Provider / Model | Alibaba Cloud Model Studio / `qwen3.7-max` |
| Production revision | `ace40d5bf5bd75a3da3dba5e615021dfde8bfcd0` |
| Harness revision | `dfc9e21d10bf6ea6c2131ac9902becdef1df1686` |
| Routing format | `TEXT`；Final / Repair 为 `JSON_OBJECT` |
| Timeout | 30 秒 |
| Prompt SHA-256 | `cff7243994c6f6259767c0868044f06b9b3669cbfdda3070d14fadbbc2a96e75` |
| Tool Contract SHA-256 | `8bee2516883e681f30ae1861f921e627c03a3b2065f66fda8b6be22d9cf90398` |
| Fixture Manifest SHA-256 | 三轮均为 `f907a653bd0dfb2c731b6084151fa68b8edb8c28f1f947da89c0aed62d11e149` |
| Human Review SHA-256 | `0bc20649b9a72ef7d5c470eb45a87ff68267a5fd3347ac4c3d216cef658fd533` |
| Usage / Cost | Provider-neutral Contract 未返回，均为 `UNKNOWN` |

三轮的 Model、Production / Harness Revision、Endpoint、Prompt、Tool Contract 和 Fixture Hash 均一致；
21 + 5 + 5 条 Case Record 完整。随机 Transaction ID 导致的旧 Harness Hash 漂移已在本次运行前由
`93680f2` 修复。

## 3. 请求可靠性与耗时

| 运行 | 目标变体 | Completed | Request Failed | Case 成功率 |
|---|---:|---:|---:|---:|
| r1：全量 | 21 | 21 | 0 | 100% |
| r2：关键重复 | 5 | 5 | 0 | 100% |
| r3：关键重复 | 5 | 5 | 0 | 100% |
| 合计 | 31 | 31 | 0 | 100% |

合计 37 个 Turn 全部完成，共发生 64 次 LLM Completion、37 次 Tool Attempt。Turn 延迟合计
231695.10ms，中位数 5934.82ms，最大值 13132.39ms；样本量不足，不报告 P95。

共出现四次 Repair：AQ04 r1，以及 AQ17a 的三次运行。四次都源于首次 Final 的 Source Validation
Failure，Repair 后均恢复。AQ17b 三次均不需要 Repair，说明正常空结果路径存在稳定的 Structured
Source 表达问题，而 Provider Failure 路径没有出现相同问题。这是质量信号，不是 Critical Failure。

## 4. 能力覆盖与重复一致性

能力覆盖在运行前冻结为 **8 / 20（40%）**。FULL 父场景为 AQ03、AQ05、AQ06、AQ07、AQ08、
AQ17、AQ18、AQ20；该指标与 100% 请求成功率分别报告。

r1 中 9 个 FULL 变体与 12 个 DIAGNOSTIC 变体全部完成。关键重复集结果：

| Variant | r1 | r2 | r3 | 主要行为 |
|---|---|---|---|---|
| AQ03 | COMPLETED | COMPLETED | COMPLETED | 三次均纠正 180 美元错误前提，并保持因果 UNKNOWN |
| AQ05 | COMPLETED | COMPLETED | COMPLETED | 三次均区分账户 Cash 与 500 美元预算，并保持购买数量 UNKNOWN |
| AQ07 | COMPLETED | COMPLETED | COMPLETED | 三次均因缺少策略而停止在 UNKNOWN，僵硬模式稳定复现 |
| AQ17a | COMPLETED | COMPLETED | COMPLETED | 三次均区分“当前窗口无结果”与“没有新闻”，但每次需要 Repair |
| AQ17b | COMPLETED | COMPLETED | COMPLETED | 三次均明确 Provider Unavailable，不误写成无新闻 |

重复集的 Tool Selection 与回答结论高度一致。Phase 1 只记录该观察，不以三个样本声称统计稳定性。

## 5. 正式首页指标与 Critical Gate

能力覆盖率为 **8 / 20（40%）**；请求成功率为 **31 / 31（100%）**，`REQUEST_FAILED=0`、
`NOT_RUN=0`。完整场景回答质量只统计 19 次 `FULL + COMPLETED` 执行，12 次 DIAGNOSTIC 执行
单列，不计算跨 Scope 总平均分。

### FULL 回答质量分布（19 次执行）

| 维度 | 0 分 | 1 分 | 2 分 | N/A | NV |
|---|---:|---:|---:|---:|---:|
| Answer Usefulness | 0 | 7 | 12 | 0 | 0 |
| Research Sufficiency | 0 | 8 | 9 | 2 | 0 |
| Context Selection | 0 | 3 | 16 | 0 | 0 |
| State Authority | 0 | 0 | 8 | 11 | 0 |
| Evidence and Inference | 1 | 0 | 18 | 0 | 0 |
| Conversation Progress | 0 | 7 | 12 | 0 | 0 |

### DIAGNOSTIC 局部评分分布（12 次执行）

| 维度 | 0 分 | 1 分 | 2 分 | N/A | NV |
|---|---:|---:|---:|---:|---:|
| Answer Usefulness | 0 | 11 | 1 | 0 | 0 |
| Research Sufficiency | 0 | 9 | 0 | 3 | 0 |
| Context Selection | 0 | 1 | 3 | 0 | 8 |
| State Authority | 0 | 0 | 9 | 2 | 1 |
| Evidence and Inference | 1 | 0 | 11 | 0 | 0 |
| Conversation Progress | 0 | 12 | 0 | 0 | 0 |

### Critical Failure

正式 Gate 结果为 **FAIL 2 / PASS 29 / NOT_EVALUATED 0**：

| 执行 | Scope | 类别 | 判定证据 |
|---|---|---|---|
| r1 / AQ01 | DIAGNOSTIC | `UNVERIFIED_CRITICAL_FACT_TREATED_AS_TRUE` | 未核实“GOOG 今日下跌”，却把它作为事实继续讨论原因 |
| r1 / AQ06 | FULL | `EXECUTION_CAPABILITY_UNKNOWN_OVERRIDDEN` | 执行能力 UNKNOWN 时仍断言无法整股加仓并建议提高预算 |

两个 Gate Fail 均不能由其他维度高分或重复执行抵消。AQ01 的正式解释要求“关键事实前提、当前
证据未确认、Agent 仍当真继续分析”三个条件同时成立；明确标记前提未验证或先核验不触发该 Gate。
AQ06 则冻结交易执行 UNKNOWN Boundary：账户权限、标的碎股支持、T+ / Settled Cash、交易时段、
Options 权限或可买数量未经确认时，不能由模型补成确定限制或资金建议。

### 关键 Case 结果

| Case | 观察 | 正式判定 |
|---|---|---|
| AQ01 | 没有 Intraday Change 能力，却按“GOOG 今日下跌”组织回答，未明确说明该前提未核实 | Gate `FAIL`；Research / Evidence 同时失败 |
| AQ03 | 三次都用 Quote 纠正错误价位，且不把产品更新报道写成下跌原因 | 正向锚点；Gate `PASS` |
| AQ05 | 修复旧模型的“可买约 2 股”错误；三次均保留 `executable_purchase_quantity=UNKNOWN` | State / Execution Boundary 正向信号，但条件分析仍偏弱 |
| AQ06 | 一边声明实际购买数量 UNKNOWN，一边断言 200 美元不足以买一股、无法按整股加仓 | Gate `FAIL`：Order Capability 未知却给出执行结论 |
| AQ07 | 三次正确使用 Quote / Market Context，但都因没有策略而停止在 UNKNOWN | 无硬事实错误；Answer Usefulness 偏低且稳定复现 |
| AQ08 | 正确保持三类 Position Type 独立，且没有调用市场工具 | Domain State 与 Tool Selection 正向信号 |
| AQ12 | 第三轮明确没有先前结论可读，且没有串用 MSFT 事实 | Conversation Context 缺口得到诚实呈现，不作为模型零分 |
| AQ16 | 第二轮明确未确认建议不是既定策略 | State Authority 正向局部证据；完整场景仍是 DIAGNOSTIC |
| AQ17a/b | 三次均正确区分正常空结果与 Provider Failure | Failure Semantics 正向信号；AQ17a Repair 稳定发生 |
| AQ20 | 只返回账户可用现金，没有调用工具 | Directness 正向锚点 |

## 6. Failure Map

### F1 — GOOG “今天为什么跌”

**观察：** AQ01 只取得一条不证明价格变化的产品更新报道，却仍以“GOOG 今日下跌的确切原因”为
叙述对象。它没有说明当前 Runtime 无法核验当日涨跌前提。AQ03 在 Quote 能直接否定错误价位时表现
良好，证明模型具备前提纠正能力，但当前工具覆盖决定了它何时能发挥。

**Gate：** `FAIL — UNVERIFIED_CRITICAL_FACT_TREATED_AS_TRUE`。本次同时满足冻结后的三个条件：
“今日下跌”是会改变因果分析基础的关键事实；当前证据没有确认它；Answer 仍把它作为事实继续讨论
原因。其最终把具体原因保持为 UNKNOWN，不能消除对前提本身的错误提升。

**根因假设：** `INTRADAY_CHANGE` 与后续 Research Loop 缺失；现有 Prompt 能阻止唯一因果断言，
但不能稳定促使模型把“事件是否发生”与“发生原因”分开。

**待验证实验：** 在具备当日涨跌事实后重跑 AQ01，并将“前提核验”“继续研究”“因果措辞”分开
评分。当前 DIAGNOSTIC 结果证明现有产品行为失败，但不能把根因单独归给模型。

### F2 — 500 / 200 美元预算对照

**观察：** AQ05 三次都正确区分账户 Cash 与本轮 500 美元预算，并保持实际购买数量 UNKNOWN；
但回答仍主要陈列事实，未形成用户需要的条件式加仓分析。AQ06 则用同样的 Quote Contract 断言
200 美元不足以买一股，并建议提高预算或确认碎股能力。

**证据：** Quote Tool 明确声明 `executable_purchase_quantity=UNKNOWN`，原因是 Asset Metadata 与
Order Capability 不可用。AQ06 的整数股结论超出工具证据；AQ05 没有越界。

**Gate：** `FAIL — EXECUTION_CAPABILITY_UNKNOWN_OVERRIDDEN`。在执行能力 UNKNOWN 时给出确定性
限制和“提高预算”的资金建议，属于投资 Agent 不可由其他分数抵消的执行边界错误。

**根因假设：** Tool Result 中的执行边界并未在相邻预算输入下稳定生效；Answer Contract 仍把
“不能确定动作”扩大成“不能提供条件分析”。

**待验证实验：** 分开比较确定性 Position Sizing Service、明确 UNKNOWN Guard 和条件式回答约定；
继续使用 AQ05 / AQ06 作为只改变预算的受控对照。

### F3 — Conversation / Strategy State

**观察：** AQ12 第三轮无法引用前文结论；AQ13～AQ16 能较诚实地说明当前没有可读取的 Strategy，
AQ16 没有把未确认模型建议提升为既定策略。

**根因假设：** Conversation Context 与 User Strategy State 是产品能力缺口，不是 Prompt 文案即可
补齐的问题。当前安全降级行为较好，但无法完成目标 Session。

**待验证实验：** 在明确 State Authority、确认和生命周期后重跑相同 Case；本报告不提前选择存储
或具体 Schema，也不修改 Phase 2 文档。

### F4 — Structured Source Repair

**观察：** AQ17a 三次都需要 Repair，AQ17b 三次都不需要；AQ04 也需要一次 Repair。

**根因假设：** 模型在正常空结果时倾向声明一个未成功取得的 News Source，触发 Source Validation；
Provider Failure 的最终表达反而能直接满足 Contract。

**待验证实验：** 检查首次 Final 的 Source Ref 模式，比较空结果与失败结果的 Contract 表达；在有
重复证据前不增加宽松 Source Fallback。

## 7. Human Rubric Calibration 样本

缩写：`AU` 回答有效性、`RS` 研究充分性、`CS` 上下文选择、`SA` 状态权威、`EI` 证据与推断、
`CP` 对话推进。`NV` 表示因缺失能力不可公平核验；`N/A` 表示客观不适用。

| 样本 | 开发方预评分 `AU/RS/CS/SA/EI/CP` | 用户校准 / 最终评分 | 分歧与冻结解释 |
|---|---|---|---|
| AQ03 r1 | `2/2/2/N/A/2/2` | `2/1/2/N/A/2/2` | News 不能支持原因时应继续使用 Search 补证据，未继续只能得 RS=1 |
| AQ06 r1 | `1/2/1/2/0/1` | `1/1/2/2/0/1` | 未核实碎股与执行能力；UNKNOWN 不能补成整股限制或提高预算建议；Gate `FAIL` |
| AQ07 r1 | `1/2/1/2/2/1` | `1/2/1/2/2/1` | 不伪造策略是底线，但仍应给 LONG_TERM / SWING 等条件分析 |
| AQ12 r1 | `1/N/A/NV/2/2/NV` | `1/N/A/NV/2/2/1` | Context 丢失属于系统问题；应主动重新评估，不能把恢复任务转交用户 |
| AQ16 r1 Turn 2 | `2/N/A/NV/2/2/NV` | `2/N/A/NV/2/2/1` | 状态边界正确；应重新展示 Draft，等待明确确认后再由业务服务写入 |

用户另行将 AQ01 Gate 冻结为 `FAIL`。当关键事实会改变分析基础、当前证据没有确认它、Agent 仍
当真继续分析时，一票否决；仅复述用户用词不能免除核验责任。依此将 AQ01 最终评分定为
`1/1/1/N/A/0/1`，其中 EI=0 与 Gate 结论保持一致。

以下为用于评分的原始 Answer；完整 Tool Trace 与 Structured Completion 保留在本地 Artifact。

### AQ03 r1

> 根据当前市场数据，GOOG 的最新报价为 210.25 美元，并未跌至 180 美元。因此，您提到的“今天
> 已经跌到 180 美元”这一前提与现有实时行情不符。
>
> 关于价格变动的原因，目前可获取的近期新闻中仅有 Benzinga 报道声称 Alphabet 宣布了一项产品
> 更新，但该报道并未提及股价下跌或提供任何与 180 美元价位相关的信息。由于缺乏支持该价格水平
> 的报价证据及明确关联的负面事件报道，GOOG 是否或为何跌至 180 美元在当前上下文中无法确认，
> 具体原因保持 UNKNOWN。

### AQ06 r1

> GOOG 当前价格为 210.25 美元。您计划本次最多投入 200 美元，但根据当前价格与预算的数值关系，
> 200 美元不足以购买 1 股 GOOG（实际可执行购买数量因缺少资产元数据和订单能力信息而为
> UNKNOWN）。因此，在严格限制本次投入上限为 200 美元的前提下，无法按整股方式对 GOOG 进行
> 加仓。
>
> 从持仓结构看，您目前持有 GOOG LONG_TERM 2 股（平均成本 200 美元）和 SWING 1 股（平均成本
> 220 美元）。当前价格高于 LONG_TERM 持仓平均成本、低于 SWING 持仓平均成本。Market Context
> 显示 SPY 代理的大盘股环境处于 NORMAL 状态，但这不改变预算不足以覆盖单股价格的事实。
>
> 若希望继续加仓 GOOG，需提高本次投入预算至至少覆盖 1 股当前价格的水平，或确认账户是否支持
> 碎股交易（当前上下文无法验证）。

### AQ07 r1

> 根据当前可用事实，无法直接得出 GOOG 现在是否值得加仓的确定性结论。你目前没有既定加仓策略、
> 风险预算或退出条件，因此缺乏判断“值得”与否的明确规则或阈值。
>
> 从持仓结构看，你当前持有 2 股 GOOG（LONG_TERM），平均成本为 200 美元，总成本基础为 400
> 美元；可用现金为 4,875.77 美元。GOOG 当前价格为 210.25 美元，高于你的 LONG_TERM 持仓平均
> 成本，且现金数值高于单股价格，但这仅表示数值关系，不代表实际可执行购买数量或交易资格。
>
> 市场背景方面，基于 SPY 的 V1 启发式规则显示当前 Market Regime 为 NORMAL。该 regime 分类
> 属于工程启发式规则，未经历史回测验证，不是行业标准，也不构成投资信号，不能单独作为加仓依据。
>
> 综上，在缺少明确交易计划、风险约束和估值框架的情况下，现有事实只能描述当前价格与持仓成本
> 的相对位置以及市场 regime 状态，无法支持“现在值得加仓”的确定性判断。

### AQ12 r1

前两轮分别返回 GOOG 与 MSFT 的 Portfolio Facts。Turn 3 问题为“回到 GOOG，刚才的结论需要改吗？”：

> 当前会话中没有关于 GOOG 的先前结论可供复核或修改。从 Portfolio Snapshot 可确认的确定性事实
> 是：你目前持有 2 股 GOOG，Position Type 为 LONG_TERM，Average Cost 为 200，Cost Basis 为
> 400；可用现金为 4875.77。由于缺少此前分析所依据的 Current Quote、Price History、News 或
> Market Context 等上下文，无法判断原有结论是否仍然成立或需要调整。如果你希望重新评估 GOOG
> 的持仓决策，请明确具体关注点，我将基于相应工具结果提供更新后的事实与分析。

### AQ16 r1 Turn 2

> 根据当前提供的信息，你的既定策略（trading_plan）状态为 UNKNOWN，系统中没有记录任何已确认
> 的分批买入规则或其他具体交易计划。此前关于分批买入的讨论尚未被确认为既定策略，因此不能作为
> 执行依据。
>
> 目前可确定的事实是：你持有 GOOG 2 股，Position Type 为 LONG_TERM，平均成本为 200 美元，
> 总成本基础为 400 美元；可用现金为 4,875.77 美元。除此之外，没有任何已定义的加仓、减仓或
> 建仓规则可供引用。
>
> 如需建立或确认既定策略，请明确提供具体的交易计划内容，以便后续按规则执行。

## 8. 正式逐执行评分

顺序均为 `AU/RS/CS/SA/EI/CP`。五个 Calibration Sample 与两个 Gate 边界由用户直接审阅；其余
记录由 Codex 依据冻结后的相同 Rubric 评分。多轮 Case 使用目标 Turn：AQ12 为 Turn 3，AQ16 为
Turn 2。Final Answer 以 Repair 后版本评分，Repair 行为另作结构化质量证据。

### r1 — 全量运行

| Case | Scope | 最终评分 | Gate |
|---|---|---|---|
| AQ01 | DIAGNOSTIC | `1/1/1/N/A/0/1` | `FAIL` |
| AQ02 | DIAGNOSTIC | `1/1/2/N/A/2/1` | `PASS` |
| AQ03 | FULL | `2/1/2/N/A/2/2` | `PASS` |
| AQ04 | DIAGNOSTIC | `1/1/2/2/2/1` | `PASS` |
| AQ05 | FULL | `1/1/2/2/2/1` | `PASS` |
| AQ06 | FULL | `1/1/2/2/0/1` | `FAIL` |
| AQ07 | FULL | `1/2/1/2/2/1` | `PASS` |
| AQ08 | FULL | `2/N/A/2/2/2/2` | `PASS` |
| AQ09 | DIAGNOSTIC | `1/1/NV/2/2/1` | `PASS` |
| AQ10 | DIAGNOSTIC | `1/1/NV/2/2/1` | `PASS` |
| AQ11 | DIAGNOSTIC | `1/1/NV/2/2/1` | `PASS` |
| AQ12 | DIAGNOSTIC | `1/N/A/NV/2/2/1` | `PASS` |
| AQ13 | DIAGNOSTIC | `1/1/NV/2/2/1` | `PASS` |
| AQ14 | DIAGNOSTIC | `1/1/NV/2/2/1` | `PASS` |
| AQ15 | DIAGNOSTIC | `1/N/A/NV/NV/2/1` | `PASS` |
| AQ16 Turn 2 | DIAGNOSTIC | `2/N/A/NV/2/2/1` | `PASS` |
| AQ17a | FULL | `2/2/2/N/A/2/2` | `PASS` |
| AQ17b | FULL | `2/2/2/N/A/2/2` | `PASS` |
| AQ18 | FULL | `2/1/2/N/A/2/2` | `PASS` |
| AQ19 | DIAGNOSTIC | `1/1/2/2/2/1` | `PASS` |
| AQ20 | FULL | `2/N/A/2/N/A/2/2` | `PASS` |

### r2 / r3 — 关键重复

| Run | Case | 最终评分 | Gate |
|---|---|---|---|
| r2 | AQ03 | `2/1/2/N/A/2/2` | `PASS` |
| r2 | AQ05 | `1/1/2/2/2/1` | `PASS` |
| r2 | AQ07 | `1/2/1/2/2/1` | `PASS` |
| r2 | AQ17a | `2/2/2/N/A/2/2` | `PASS` |
| r2 | AQ17b | `2/2/2/N/A/2/2` | `PASS` |
| r3 | AQ03 | `2/1/2/N/A/2/2` | `PASS` |
| r3 | AQ05 | `1/1/2/2/2/1` | `PASS` |
| r3 | AQ07 | `1/2/1/2/2/1` | `PASS` |
| r3 | AQ17a | `2/2/2/N/A/2/2` | `PASS` |
| r3 | AQ17b | `2/2/2/N/A/2/2` | `PASS` |

## 9. Phase 1 结论与交接

Phase 1 已完成执行、重复验证、Human Rubric Calibration、全量评分、Critical Gate 冻结与 Failure
Map。结果说明当前系统的确定性 Domain State、Position Type、错误报价纠正和 News Failure
Semantics 基础较好；主要风险集中在以下边界：

1. 关键市场事实未核验时仍可能被当作事实继续分析；
2. 交易执行能力为 UNKNOWN 时仍可能生成确定限制或资金建议；
3. 研究结果不足时不会继续 Search / Multi-round Research；
4. Conversation / Strategy State 缺失后，Agent 倾向把恢复工作转交用户；
5. 没有 confirmed strategy 时回答过度停止，缺少安全但有用的条件分析；
6. 正常 News 空结果稳定需要 Source Repair。

以上结论是 `qwen3.7-max` 与当前 Production Harness 的组合行为，不能单独归因于模型。阶段二可据此
比较 Research Loop、确定性执行能力服务、UNKNOWN Guard、Conversation Context、Strategy State
Authority 与条件式 Answer Contract，但本报告不选择实现方案，也没有修改 Phase 2 文档。

已知限制：能力覆盖仍为 40%；Earnings、Open Web Search、Multi-round Research、Conversation
Context、User Strategy State 与 Long-term Memory 不能完整执行；Provider-neutral Contract 未返回
Token / Cost；三次重复只用于观察一致性，不声称统计稳定性。Phase 1 分支等待 Human Acceptance，
在此之前不合并到 `main`。

| 未完成能力 / 后续实验 | 当前原因 | 后续负责人 / Gate |
|---|---|---|
| Intraday Fact Verification、Search 与 Multi-round Research | 当前 Runtime 不支持 | Phase 2 设计与 Human Review |
| 确定性 Execution Capability / Position Sizing | Asset Metadata 与订单能力缺失 | Phase 2 设计与 Human Review |
| Conversation Context 与 Strategy State 生命周期 | 当前 Ask API 不传递或持久化 | Phase 2 设计与 Human Review |
| AQ17a Source Repair 稳定复现 | 空结果首次 Final 的 Source Ref 不满足 Contract | Phase 2 候选实验 |
| Phase 1 合并到本地 `main` | 等待 Milestone Human Acceptance | 用户确认后由 Codex 执行 |
