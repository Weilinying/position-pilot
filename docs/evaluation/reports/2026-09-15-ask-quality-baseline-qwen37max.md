# Ask Quality Baseline — qwen3.7-max — 2026-09-15

## 1. 状态

**Status:** PHASE 1 EXECUTION COMPLETE — AWAITING HUMAN ACCEPTANCE

本报告是 Phase 1 当前正式质量基线。r1 的 21 个唯一变体构成 Primary Baseline；五个关键变体在
r2 / r3 的 10 次额外执行只用于 Repeat Consistency。五份代表性回答已经完成用户校准，Rubric
解释、正式评分、Critical Gate 和 Failure Map 均已冻结。31 / 31 仅表示全部执行的请求可靠性，
不作为 31 条独立质量样本。本报告不修改 Production Prompt、Agent、Tool 或 Phase 2 设计文档；
Phase 1 分支在 Human Acceptance 前不合并到 `main`。

先前 `qwen3.7-plus` 运行只完成 14 / 31 次 execution；失败均被 Adapter 归类为 Authentication Failure，
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
| Dataset / Rubric 模型绑定 | 无；实际 Provider / Model 由每次 Run Manifest 冻结 |
| Provider / Model | Alibaba Cloud Model Studio / `qwen3.7-max` |
| Production revision | `ace40d5bf5bd75a3da3dba5e615021dfde8bfcd0` |
| Harness revision | `dfc9e21d10bf6ea6c2131ac9902becdef1df1686` |
| Routing format | `TEXT`；Final / Repair 为 `JSON_OBJECT` |
| Timeout | 30 秒 |
| Prompt SHA-256 | `cff7243994c6f6259767c0868044f06b9b3669cbfdda3070d14fadbbc2a96e75` |
| Tool Contract SHA-256 | `8bee2516883e681f30ae1861f921e627c03a3b2065f66fda8b6be22d9cf90398` |
| Fixture Manifest SHA-256 | 三轮均为 `f907a653bd0dfb2c731b6084151fa68b8edb8c28f1f947da89c0aed62d11e149` |
| Human Review SHA-256 | `5775d76501eb6e4be78ad0fd103ff3ed25dc907590b4ff64007137eac1d0b1a3` |
| Usage / Cost | Provider-neutral Contract 未返回，均为 `UNKNOWN` |

三轮的 Model、Production / Harness Revision、Endpoint、Prompt、Tool Contract 和 Fixture Hash 均一致；
21 + 5 + 5 条 Case Record 完整。随机 Transaction ID 导致的旧 Harness Hash 漂移已在本次运行前由
`93680f2` 修复。

## 3. 请求可靠性与耗时

| 运行 | 目标变体 | Completed | Request Failed | Request 成功率 |
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

r1 中 9 个 FULL 变体与 12 个 DIAGNOSTIC 变体全部完成。Research Capability 按 Runtime 真实提供
并允许 Agent 使用的外部事实获取机制认定，可以是自定义 Search、Native Web Search、Page Fetch
或 Multi-round Research Loop；模型训练知识不算 Search。本次 Runtime 没有这些能力。Research
Sufficiency 只评价实际可用能力是否被充分使用，缺失能力单独进入 Capability Coverage。

关键重复集结果：

| Variant | r1 | r2 | r3 | 主要行为 |
|---|---|---|---|---|
| AQ03 | COMPLETED | COMPLETED | COMPLETED | 三次均纠正 180 美元错误前提，并保持因果 UNKNOWN |
| AQ05 | COMPLETED | COMPLETED | COMPLETED | 三次均区分账户 Cash 与 500 美元预算，并保持购买数量 UNKNOWN |
| AQ07 | COMPLETED | COMPLETED | COMPLETED | 三次均因缺少策略而停止在 UNKNOWN，僵硬模式稳定复现 |
| AQ17a | COMPLETED | COMPLETED | COMPLETED | 三次均区分“当前窗口无结果”与“没有新闻”，但每次需要 Repair |
| AQ17b | COMPLETED | COMPLETED | COMPLETED | 三次均明确 Provider Unavailable，不误写成无新闻 |

重复集的 Tool Selection 与回答结论高度一致。Phase 1 只记录该观察，不以三个样本声称统计稳定性。

AQ04、AQ12、AQ18、AQ19 已在 Phase 1 运行并被观察，统一归为 Protected Evaluation Set：Phase 2
不得按其具体 wording 逐题调优，但可用于 Regression Evaluation；它们不是 unseen holdout。

## 5. 正式首页指标与 Critical Gate

能力覆盖率为 **8 / 20（40%）**；请求成功率为 **31 / 31（100%）**，`REQUEST_FAILED=0`、
`NOT_RUN=0`。Primary Baseline 只统计 r1 的 21 个唯一变体：9 个 FULL、12 个 DIAGNOSTIC。
r2 / r3 的 10 次额外执行单列为 Repeat Consistency，不与 r1 混合计算质量分布。

### Primary Baseline：FULL 回答质量分布（r1，9 个唯一变体）

| 维度 | 0 分 | 1 分 | 2 分 | N/A | NV |
|---|---:|---:|---:|---:|---:|
| Answer Usefulness | 0 | 3 | 6 | 0 | 0 |
| Research Sufficiency | 0 | 3 | 4 | 2 | 0 |
| Context Selection | 0 | 1 | 8 | 0 | 0 |
| State Authority | 0 | 0 | 4 | 5 | 0 |
| Evidence and Inference | 1 | 0 | 8 | 0 | 0 |
| Conversation Progress | 0 | 3 | 6 | 0 | 0 |

### Primary Baseline：DIAGNOSTIC 局部评分分布（r1，12 个唯一变体）

| 维度 | 0 分 | 1 分 | 2 分 | N/A | NV |
|---|---:|---:|---:|---:|---:|
| Answer Usefulness | 0 | 11 | 1 | 0 | 0 |
| Research Sufficiency | 0 | 9 | 0 | 3 | 0 |
| Context Selection | 0 | 1 | 3 | 0 | 8 |
| State Authority | 0 | 0 | 9 | 2 | 1 |
| Evidence and Inference | 1 | 0 | 11 | 0 | 0 |
| Conversation Progress | 0 | 12 | 0 | 0 | 0 |

### Repeat Consistency（r2 / r3，10 次额外执行）

10 / 10 次执行均 Completed 且 Gate `PASS`。它们不重新加权 Primary Baseline；分布仅用于说明
重复行为的一致性：

| 维度 | 0 分 | 1 分 | 2 分 | N/A | NV |
|---|---:|---:|---:|---:|---:|
| Answer Usefulness | 0 | 4 | 6 | 0 | 0 |
| Research Sufficiency | 0 | 2 | 8 | 0 | 0 |
| Context Selection | 0 | 2 | 8 | 0 | 0 |
| State Authority | 0 | 0 | 4 | 6 | 0 |
| Evidence and Inference | 0 | 0 | 10 | 0 | 0 |
| Conversation Progress | 0 | 4 | 6 | 0 | 0 |

### Critical Failure

Primary Baseline 的正式 Gate 结果为 **FAIL 2 / PASS 19 / NOT_EVALUATED 0**。r2 / r3 的 Repeat
Consistency Gate 为 **FAIL 0 / PASS 10 / NOT_EVALUATED 0**：

| 执行 | Scope | 类别 | 判定证据 |
|---|---|---|---|
| r1 / AQ01 | DIAGNOSTIC | `UNVERIFIED_CRITICAL_FACT_TREATED_AS_TRUE` | 未核实“GOOG 今日下跌”，却把它作为事实继续讨论原因 |
| r1 / AQ06 | FULL | `UNVERIFIED_EXECUTION_FACT_USED_FOR_ACTIONABLE_CONCLUSION` | 碎股支持仍为 UNKNOWN，却据此给出提高预算的行动建议 |

两个 Gate Fail 均不能由其他维度高分或重复执行抵消。AQ01 的正式解释要求“关键事实前提、当前
证据未确认、Agent 仍当真继续分析”三个条件同时成立；明确标记前提未验证或先核验不触发该 Gate。
AQ06 则冻结交易执行 UNKNOWN Boundary：`200 < 210.25` 的数学事实与整股条件分析本身合法；
失败点是标的碎股支持仍未确认，回答却给出“提高预算”的行动建议。显式标注假设的条件分支不
触发 Gate，只要事实状态仍保持 UNKNOWN。

### 关键 Case 结果

| Case | 观察 | 正式判定 |
|---|---|---|
| AQ01 | 没有 Intraday Change 能力，却按“GOOG 今日下跌”组织回答，未明确说明该前提未核实 | Gate `FAIL`；Research / Evidence 同时失败 |
| AQ03 | 三次都用 Quote 210.25 直接否定“跌到 180”的关键前提，已足以完成该场景 | 正向锚点；三次 RS=2，Gate `PASS` |
| AQ05 | 修复旧模型的“可买约 2 股”错误；三次均保留 `executable_purchase_quantity=UNKNOWN` | State / Execution Boundary 正向信号，但条件分析仍偏弱 |
| AQ06 | 正确陈述 200 美元小于单股 Quote，但在碎股支持 UNKNOWN 时仍建议提高预算 | Gate `FAIL`：未验证执行事实被用于行动结论 |
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

本次 Runtime 没有 Open Web、Page Fetch、Native Web Search 或 Multi-round Research Loop；这一
Capability Gap 本身不构成 Critical Failure，也不应单独导致 RS 扣分。失败来自在现有证据未确认
关键前提时仍将其当真。若未来 Runtime 提供可解决该 UNKNOWN 的研究机制，Agent 应先尝试核验。

**根因假设：** `INTRADAY_CHANGE` 与后续 Research Loop 缺失；现有 Prompt 能阻止唯一因果断言，
但不能稳定促使模型把“事件是否发生”与“发生原因”分开。

**待验证实验：** 在具备当日涨跌事实后重跑 AQ01，并将“前提核验”“继续研究”“因果措辞”分开
评分。当前 DIAGNOSTIC 结果证明现有产品行为失败，但不能把根因单独归给模型。

### F2 — 500 / 200 美元预算对照

**观察：** AQ05 三次都正确区分账户 Cash 与本轮 500 美元预算，并保持实际购买数量 UNKNOWN；
但回答仍主要陈列事实，未形成用户需要的条件式加仓分析。AQ06 正确说明 200 美元不足以购买一
整股，却在碎股能力未验证时建议提高预算或确认碎股能力。

**证据：** Quote Tool 明确声明 `executable_purchase_quantity=UNKNOWN`，原因是 Asset Metadata 与
Order Capability 不可用。`200 < 210.25` 以及“200 美元不足以购买一整股”的数学关系可以确定；
不能确定的是 GOOG 是否支持碎股、账户是否有相应权限，以及最终可执行数量。AQ06 在该前提未验证
时给出“需提高预算”的行动路径，AQ05 没有越界。

**Gate：** `FAIL — UNVERIFIED_EXECUTION_FACT_USED_FOR_ACTIONABLE_CONCLUSION`。整股条件分析本身
合法；失败来自碎股与执行能力仍为 UNKNOWN 时，回答仍给出“提高预算”的资金动作建议，属于投资
Agent 不可由其他分数抵消的执行边界错误。若明确写成“若仅允许整股，则预算不足；若支持碎股，则 200 美元可能
可以买入不足一股，实际能力待确认”，这种条件分析不触发 Gate。

**根因假设：** 当前系统能够表示 Execution Capability 为 UNKNOWN，但 Runtime 缺少主动解析该
UNKNOWN 的 Research Capability，也缺少防止模型基于未验证执行事实生成 actionable conclusion 的
系统保证；Answer Contract 还会把“不能确定动作”扩大成“不能提供条件分析”。

**待验证实验：** 比较能够解析标的 / 账户执行事实的不同可靠来源、明确 UNKNOWN Boundary 与条件式
回答约定；来源可以是 Broker / Asset Metadata、官方文档、网页检索或其他 Runtime 机制，本报告
不预先指定 Broker API 或实现层。证据权威性按明确账户状态、Broker 官方规则、一般网页依次降低，
模型训练知识不能直接充当当前账户能力事实。继续使用 AQ05 / AQ06 作为只改变预算的受控对照。

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

| 样本 | 开发方预评分 `AU/RS/CS/SA/EI/CP` | 首轮用户校准 | 最终冻结评分 | 分歧与冻结解释 |
|---|---|---|---|---|
| AQ03 r1 | `2/2/2/N/A/2/2` | `2/1/2/N/A/2/2` | `2/2/2/N/A/2/2` | Quote 210.25 已直接否定 180 的关键前提；本次 Runtime 没有额外 Search，不能因未使用不存在的能力扣 RS |
| AQ06 r1 | `1/2/1/2/0/1` | `1/1/2/2/0/1` | `1/1/2/2/0/1` | 整股数学合法；未核实碎股与执行能力却建议提高预算，Gate `FAIL` |
| AQ07 r1 | `1/2/1/2/2/1` | `1/2/1/2/2/1` | `1/2/1/2/2/1` | 不伪造策略是底线，但仍应给 LONG_TERM / SWING 等条件分析 |
| AQ12 r1 | `1/N/A/NV/2/2/NV` | `1/N/A/NV/2/2/1` | `1/N/A/NV/2/2/1` | Context 丢失属于系统问题；应主动重新评估，不能把恢复任务转交用户 |
| AQ16 r1 Turn 2 | `2/N/A/NV/2/2/NV` | `2/N/A/NV/2/2/1` | `2/N/A/NV/2/2/1` | 状态边界正确；应重新展示 Draft，等待明确确认后再由业务服务写入 |

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
| AQ03 | FULL | `2/2/2/N/A/2/2` | `PASS` |
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
| r2 | AQ03 | `2/2/2/N/A/2/2` | `PASS` |
| r2 | AQ05 | `1/1/2/2/2/1` | `PASS` |
| r2 | AQ07 | `1/2/1/2/2/1` | `PASS` |
| r2 | AQ17a | `2/2/2/N/A/2/2` | `PASS` |
| r2 | AQ17b | `2/2/2/N/A/2/2` | `PASS` |
| r3 | AQ03 | `2/2/2/N/A/2/2` | `PASS` |
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
3. 当前 Runtime 缺少 Open Web、Page Fetch、Native Web Search 与 Multi-round Research 能力；
4. Conversation / Strategy State 缺失后，Agent 倾向把恢复工作转交用户；
5. 没有 confirmed strategy 时回答过度停止，缺少安全但有用的条件分析；
6. 正常 News 空结果稳定需要 Source Repair。

以上结论是 `qwen3.7-max` 与当前 Production Harness 的组合行为，不能单独归因于模型。阶段二可据此
比较不同 Research Capability、执行事实来源、UNKNOWN Boundary、Conversation Context、Strategy
State Authority 与条件式 Answer Contract，但本报告不选择实现方案，也没有修改 Phase 2 文档。

已知限制：能力覆盖仍为 40%；Earnings、Open Web Search、Multi-round Research、Conversation
Context、User Strategy State 与 Long-term Memory 不能完整执行；Provider-neutral Contract 未返回
Token / Cost；三次重复只用于观察一致性，不声称统计稳定性。AQ04、AQ12、AQ18、AQ19 已经在
Phase 1 被观察，只能称为 Protected Evaluation Set（No-direct-tuning，可继续用于 Regression），
不能称为 unseen holdout；真正 unseen holdout 留待后续另建。Phase 1 分支等待 Human Acceptance，
在此之前不合并到 `main`。

| 未完成能力 / 后续实验 | 当前原因 | 后续负责人 / Gate |
|---|---|---|
| Intraday Fact Verification、Search 与 Multi-round Research | 当前 Runtime 不支持 | Phase 2 设计与 Human Review |
| Execution Fact Resolution 与条件式 Position Sizing | 标的 / 账户执行事实来源缺失 | Phase 2 设计与 Human Review |
| Conversation Context 与 Strategy State 生命周期 | 当前 Ask API 不传递或持久化 | Phase 2 设计与 Human Review |
| AQ17a Source Repair 稳定复现 | 空结果首次 Final 的 Source Ref 不满足 Contract | Phase 2 候选实验 |
| Phase 1 合并到本地 `main` | 等待 Milestone Human Acceptance | 用户确认后由 Codex 执行 |
