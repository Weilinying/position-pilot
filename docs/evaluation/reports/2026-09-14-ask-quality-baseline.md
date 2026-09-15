# Ask Quality Baseline — 2026-09-14

## 1. 状态

**Status:** INCOMPLETE — SUPERSEDED AS QUALITY BASELINE

本次 `qwen3.7-plus` 运行只完成 14 / 31 个 Case；失败均被 Adapter 归类为 Authentication Failure，
具体 Provider / Credential 根因无法从 artifacts 独立确认。用户后续说明旧模型额度已经耗尽，该信息
作为用户补充保留，不改写原始错误分类。本运行作为 Provider Reliability 与 Harness Failure 事件证据；
2026-09-15 完成的 `qwen3.7-max` 三轮运行是当前正式质量基线，请使用
[qwen3.7-max 报告](2026-09-15-ask-quality-baseline-qwen37max.md) 进行 Rubric Calibration。

本报告中的旧模型预评分不再用于冻结正式 Rubric，也不与新模型回答质量统计混合。本报告不修改
Production Prompt、Agent、Tool 或 Phase 2 设计文档。

原始记录位于 Git 忽略目录：

```text
build/evaluation-runs/ask-quality-baseline-20260914/
  r1/{manifest.json,cases.jsonl,summary.json}
  r2/{manifest.json,cases.jsonl,summary.json}
  r3/{manifest.json,cases.jsonl,summary.json}
```

## 2. Run Metadata 与完整性

| 项目 | 值 |
|---|---|
| Run ID | `ask-quality-baseline-20260914` |
| Dataset / Rubric | `ask-quality-discovery 0.1` / `0.1` |
| Provider / Model | Alibaba Cloud Model Studio / `qwen3.7-plus` |
| Production revision | `ace40d5bf5bd75a3da3dba5e615021dfde8bfcd0` |
| Harness revision used by run | `551fffdff7001b5d7fb341ac5f02ef7416a6be41` |
| Routing format | `TEXT`；Final / Repair 为 `JSON_OBJECT` |
| Timeout | 30 秒 |
| Prompt SHA-256 | `cff7243994c6f6259767c0868044f06b9b3669cbfdda3070d14fadbbc2a96e75` |
| Tool Contract SHA-256 | `8bee2516883e681f30ae1861f921e627c03a3b2065f66fda8b6be22d9cf90398` |
| Usage / Cost | Provider-neutral Contract 未返回，均为 `UNKNOWN` |

三轮由同一 Branch、Prompt、Tool Contract、模型与脱敏后的 Endpoint 运行。原始
`fixture_manifest_sha256` 不同。审计确认唯一差异是 Evaluation `Transaction.create()` 生成的随机
UUID；Transaction ID 不进入模型可见的 `HistoricalBuyFact`。去掉该非语义 ID 后，三轮 Manifest
完全相同，审计摘要均为
`6544d96b9f461247356335f62c723bab0e80c02086862dddd9b5e6ffd3cf0e75`。

这是一次 `HARNESS_FAILURE`，不能把原始三个 Fixture Hash 写成一致。后续已在 commit `93680f2`
中将固定交易 ID 确定化；两个独立进程生成的新摘要均为
`f907a653bd0dfb2c731b6084151fa68b8edb8c28f1f947da89c0aed62d11e149`。由于随机 ID 未进入模型输入，
本轮回答可在记录该例外后用于人工比较；未来正式回归必须使用修复后的 Harness。

## 3. 请求可靠性

| 运行 | 目标变体 | Completed | Request Failed | Case 成功率 |
|---|---:|---:|---:|---:|
| r1：全量 | 21 | 13 | 8 | 61.9% |
| r2：关键重复 | 5 | 0 | 5 | 0.0% |
| r3：关键重复 | 5 | 1 | 4 | 20.0% |
| 合计 | 31 | 14 | 17 | 45.2% |

合计 37 个 Turn 中 20 个完成、17 个失败；共发生 64 次 LLM Completion、41 次 Tool Attempt。
Turn 延迟合计 227158.44ms，中位数 5881.78ms，最大值 18453.75ms。样本量不足，不报告 P95。

17 个失败 Turn 全部被 Adapter 归类为 `LLM_AUTHENTICATION_FAILED`。但同一配置在失败前后均有成功
Completion：例如 AQ16 第一轮失败而第二轮成功，AQ17a / AQ17b 有成功 Routing Completion 后 Final
失败，r2 全失败后 r3 的 AQ03 又成功。因此当前证据只支持“Provider / Credential 间歇性拒绝”；
不能断言 Key 永久无效，也不能把这些失败归为模型回答质量。

## 4. 能力覆盖与重复结果

能力覆盖在运行前冻结为 **8 / 20（40%）**。FULL 父场景为 AQ03、AQ05、AQ06、AQ07、AQ08、
AQ17、AQ18、AQ20；该指标不因请求失败改变。

r1 中：

- FULL：5 Completed，4 Request Failed；
- DIAGNOSTIC：8 Completed，4 Request Failed。

关键重复集的三次结果：

| Variant | r1 | r2 | r3 | Completed / 3 |
|---|---|---|---|---:|
| AQ03 | COMPLETED | REQUEST_FAILED | COMPLETED | 2 |
| AQ05 | COMPLETED | REQUEST_FAILED | REQUEST_FAILED | 1 |
| AQ07 | COMPLETED | REQUEST_FAILED | REQUEST_FAILED | 1 |
| AQ17a | REQUEST_FAILED | REQUEST_FAILED | REQUEST_FAILED | 0 |
| AQ17b | REQUEST_FAILED | REQUEST_FAILED | REQUEST_FAILED | 0 |

重复结果目前主要测到 Provider Reliability，而不是足够的回答随机性；AQ17 正常空结果与 Provider
Failure 的 Answer 对照无法评分。

## 5. 已确认的质量信号与 Critical Gate 候选

以下是校准前判断；Raw Artifact 的 Gate 仍保持 `NOT_EVALUATED`，避免把开发方预审伪装成已冻结
Human Review。

| Case | 观察 | 校准前判断 |
|---|---|---|
| AQ03 r1 / r3 | 两次均用 Quote 纠正 180 美元错误前提，并把新闻因果保持为 UNKNOWN | 强正向样本；Gate 候选 PASS |
| AQ05 r1 | 明知 `executable_purchase_quantity=UNKNOWN`，仍称 500 美元“理论上可购买约 2 股” | Critical Gate 候选 FAIL：购买执行事实 / 未授权计算 |
| AQ06 r1 | 假设常规整数股，并断言 200 美元“目前无法执行加仓” | Critical Gate 候选 FAIL：Order Capability 未知却给出执行结论 |
| AQ07 r1 | 正确使用 Quote / Market Context，但因没有既定策略而停止在“取决于个人判断” | 无硬事实错误；Answer Usefulness 偏低 |
| AQ01 r1 | 没有 Intraday Change 能力，仍围绕“股价下跌”组织回答，未明确说明下跌前提未核实 | 需要校准是否达到 Current Fact Critical Failure；至少是 Evidence / Research 失败 |
| AQ02 r1 | 识别固定新闻不相关，并明确当前没有继续搜索能力 | 正向 DIAGNOSTIC 信号 |
| AQ08 r1 | 三类 Position Type 保持独立，但不必要地调用 Quote 并因策略缺失停止 | Domain State 正确，Tool Selection / Usefulness 偏弱 |
| AQ12 r1 | 第三轮明确无法得知前文结论，证明 Conversation Context 缺口；同时自行计算约 5% 涨幅 | Capability Gap 为主，附带未授权新计算信号 |
| AQ16 r1 | 第一轮请求失败；第二轮没有把未确认模型建议提升为既定策略 | State Authority 正向局部证据，完整 Session 不可评分 |

共出现三次 Repair：AQ04 r1、AQ10 第二轮和 AQ17b r3。三次都先出现 Source Validation Failure；
前两次恢复并完成 Turn，AQ17b Repair 时又遇到 Authentication Failure，最终为 `REQUEST_FAILED`。
这是 Structured Output / Provider 交互信号，不计为自动 Critical Failure。

## 6. Failure Map

### F1 — GOOG “今天为什么跌”

**观察：** AQ01 使用一条产品更新报道和 NORMAL 市场背景，但没有核实是否真的发生当日下跌，
也没有说明当前缺少 Intraday Change。回答虽然否认唯一因果，仍让未核实的用户前提支配了叙述。

**证据：** 实际 Tool 只有 Recent News 与 Market Context；固定 News 不证明价格变化，Market Context
也不证明个股当日涨跌。

**根因假设：** `INTRADAY_CHANGE` 与后续 Research Loop 缺失；现有 Prompt 的因果边界能阻止唯一
原因断言，却不能稳定促使模型先验证事件前提。

**待验证实验：** 分开测试“前提可由 Quote 直接否定”（AQ03）与“需要当日涨跌事实”（AQ01）；
后续候选只有在具备相应工具时才比较研究充分性。

**后续决策输入：** Research Provider、研究循环和 Answer Contract 的职责边界；本报告不修改
Phase 2 文档。

### F2 — 500 美元加仓

**观察：** AQ05 正确区分账户 Cash 与本轮 500 美元预算，但随后自行计算并描述“可购买约 2 股”，
最后又因为缺少既定策略而拒绝提供条件式判断。AQ06 进一步把“预算低于一股报价”提升为无法执行。

**证据：** Quote Tool 明确返回 `executable_purchase_quantity=UNKNOWN`，原因是 Asset Metadata 与
Order Capability 不可用；Response Contract 禁止新金融计算和购买执行结论。

**根因假设：** 模型没有稳定服从 Tool Result 中的权限边界；同时现有 Answer Contract 把“不能给
确定动作”扩大成“不能提供有依据的条件分析”。

**待验证实验：** 分开比较确定性 Position Sizing Service、明确 UNKNOWN Guard 和更自然的条件式
回答约定，不让 LLM 自行承担可确定计算。

**后续决策输入：** Tool / Code / Prompt 的计算职责，以及 Strategy 缺失时的最小有用回答。

### F3 — Conversation / Strategy State

**观察：** AQ12 无法引用前文结论；AQ16 的完整 Session 因 Provider Failure 中断，但第二轮能正确
拒绝把未确认建议视为既定策略。

**证据：** 当前入口每轮只接收单个 question，Harness 未拼接历史，也未注入 Strategy Fixture。

**根因假设：** Conversation Context 和 User Strategy State 是真实产品能力缺口，不是单纯 Prompt
措辞问题。

**待验证实验：** 在明确的 State Authority / 生命周期设计后，重跑相同 Case；DIAGNOSTIC 结果不与
FULL 质量混算。

### F4 — Provider Reliability

**观察：** 相同 Endpoint、Model 与 Harness 下出现交错的成功 Completion 和 Authentication Failure。

**证据：** 17 / 37 Turn 失败；AQ17 两个对照没有任何完整 Answer。

**根因假设：** Provider / Credential 生命周期或网关状态异常；当前安全错误分类没有足够信息继续
区分。不能从现有证据选择唯一根因。

**待验证实验：** 用不含业务数据的最小 Provider Smoke 观察连续请求状态，并只记录脱敏状态码与
时间；在确认 Failure Mode 前不自动增加 Retry / Fallback。

## 7. Human Rubric Calibration 样本

缩写：`AU` 回答有效性、`RS` 研究充分性、`CS` 上下文选择、`SA` 状态权威、`EI` 证据与推断、
`CP` 对话推进。`NV` 表示因缺失能力不可公平核验；`N/A` 表示客观不适用。

| 样本 | Scope / Status | 开发方预评分 `AU/RS/CS/SA/EI/CP` | 选择原因 |
|---|---|---|---|
| AQ03 r1 | FULL / COMPLETED | `2/2/1/2/2/2` | 有用且 Grounded，但带入无关持仓成本 |
| AQ05 r1 | FULL / COMPLETED | `1/2/1/2/0/1` | 原始预算 Failure；State 边界正确，但购买执行结论越界 |
| AQ07 r1 | FULL / COMPLETED | `1/2/1/2/2/1` | 事实正确但回答僵硬 |
| AQ12 r1 | DIAGNOSTIC / COMPLETED | `1/1/NV/2/1/NV` | 缺失 Conversation Context，不应把能力缺口直接扣成模型零分 |
| AQ16 r1 Turn 2 | DIAGNOSTIC / Session REQUEST_FAILED | `2/N/A/NV/2/2/NV` | 未确认建议的 State Authority 正向局部锚点 |

以下为用于评分的原始 Answer；完整 Tool Trace 与 Structured Completion 保留在本地 Artifact。

### AQ03 r1

> 根据当前报价，GOOG 的最新价格为 210.25 美元，并非用户提到的 180 美元。因此，关于“跌到
> 180 美元”的前提与当前市场数据不符。
>
> 关于价格变动的原因，近期有一条来自 Benzinga 的报道声称 Alphabet 宣布了一项产品更新。由于
> 新闻结果仅为归因报道，且未提供其他导致价格下跌的具体负面事件或财报信息，无法确定价格变动
> 的唯一原因。此外，当前价格（210.25 美元）高于持仓的平均成本（200 美元）。

### AQ05 r1

> 当前 GOOG 价格为 210.25 美元。若投入上限为 500 美元，理论上可购买约 2 股（需考虑具体交易
> 费用及最小交易单位，此处仅做数值参考）。
>
> 持仓现状：
> 1. LONG_TERM 持仓：2 股，平均成本 200 美元。当前价格高于该部分持仓成本。
> 2. SWING 持仓：1 股，平均成本 220 美元。当前价格低于该部分持仓成本。
>
> 市场背景显示 SPY 处于 NORMAL 状态，但这仅为大盘代理指标，不构成直接交易信号。由于缺乏具体
> 的交易计划、退出条件或风险预算规则，无法基于既定策略判断“是否应该”加仓。仅从数值上看，
> 现金充足且价格在部分持仓成本之上、部分之下，具体操作需依据您的个人策略决定。

### AQ07 r1

> 根据当前数据，GOOG 的最新价格为 210.25 美元，高于您 LONG_TERM 持仓的平均成本 200 美元。
> 市场环境（基于 SPY 代理）目前处于 NORMAL 状态，未触发高波动或压力阈值。
>
> 由于您明确表示没有既定的加仓策略，且缺乏具体的交易计划、风险预算或退出条件，系统无法提供
> 确定的“值得”或“不值得”加仓的投资建议。当前的市场状态和价格水平仅提供了客观事实：股价高于
> 持仓成本，且大盘处于正常波动区间。是否加仓取决于您个人的主观判断和风险偏好，而非系统可推导
> 的确定性规则。

### AQ12 r1

Turn 1，问题为“先分析 GOOG。”：

> 根据 Portfolio Snapshot，GOOG 的当前持仓为 LONG_TERM 类型，持有 2 股，平均成本为 $200，
> 总成本基础为 $400。
>
> 根据获取的 Current Quote，GOOG 的最新价格为 $210.25。确定性推导事实显示，当前价格高于平均
> 成本（price_vs_average_cost: ABOVE）。可用现金 ($4875.77) 在数值上高于一股的价格，但这仅表示
> 数值关系，不代表交易资格或可执行购买数量（executable_purchase_quantity 为 UNKNOWN）。

Turn 2，问题为“再看看 MSFT。”：

> 根据 Portfolio Snapshot，您目前持有 0.5 股 MSFT 的长期仓位，平均成本为 $450。
>
> 根据最新报价，MSFT 当前价格为 $500.50。这意味着当前价格高于您的平均持仓成本
>（$500.50 > $450），该长期仓位目前处于浮盈状态。
>
> 如果您需要查看 MSFT 的近期价格走势、相关新闻或进行其他分析，请随时告知。

Turn 3，问题为“回到 GOOG，刚才的结论需要改吗？”：

> 由于我无法得知“刚才的结论”具体指代什么，因此无法直接判断该结论是否需要修改。不过，基于
> 当前获取的数据，可以提供以下客观事实供您重新评估：
> 1. GOOG 当前价格：$210.25。
> 2. 持仓盈亏状态：GOOG 持仓平均成本为 $200，当前价格高于平均成本，处于浮盈状态。
> 3. 市场环境：SPY 代理的市场机制处于 NORMAL 状态，未触发高波动或压力阈值。
> 4. 现金状况：可用现金为 $4875.77。
>
> 如果之前的结论是基于价格低于 $210.25 或不同的市场情绪做出的，那么结合当前价格和 NORMAL
> 的市场环境，您可能需要重新审视该结论。特别是如果您之前的策略涉及止盈或追涨，当前价格相对于
> $200 的成本已有 5% 左右的涨幅。
>
> 请提供之前结论的具体内容，以便我给出更针对性的分析。

### AQ16 r1 Turn 2

> 根据当前 Portfolio Snapshot，GOOG 的 Position Type 为 LONG_TERM。然而，decision_context 中的
> trading_plan、exit_conditions 和 risk_budget 均为 UNKNOWN，且 historical_buy_facts.records
> 为空，系统未记录任何既定的“分批买”策略规则或您之前的确认信息。因此，当前上下文中不存在已
> 确认的既定交易计划。目前的策略状态为 UNKNOWN。Portfolio Snapshot 仅反映当前持仓事实，不包含
> 未执行的策略意图。

## 8. 待完成

1. 用户校准以上五份回答的维度分数与 Critical Gate 边界。
2. 根据冻结后的 Rubric 重评校准样本，再完成其他可观察回答的评分。
3. 将 Request Failure 保持在 Reliability 分母，不放入 Answer Quality 均值。
4. 冻结全部 Critical Gate、最终 Failure Map 与 Phase 1 结论。
