# 4B AQ12 / AQ15 Repeat Review

2026-10-04。Reviewer：Codex；依据实际 Artifact、Rubric 0.1 与既有冻结 Gate 离线审阅。**Runtime 完成，六次 Case 执行的 Critical 建议均 PASS；AQ12 r1 有质量最低分未达标，整体验收待 Human Review。** 不自动修改 Prompt、重跑或进入 T8。

## 独立证据与版本

- 新 Run：`p4b-gemini-repeat-v1-20261004T145019Z`，`run_kind=4B_REPEAT`。
- Artifact：`/Users/linyingwei/Documents/position-pilot/build/evaluation-runs/p4b-gemini-repeat-v1-20261004T145019Z`。
- 当前 Run 仅新增 AQ12 r1/r2/r3、AQ15 r2/r3，共 13 Ask。AQ15 r1 只引用
  `p4b-gemini-primary-v1-20261004T141232Z` 的真实 Primary，不复制或算成新执行。
- AQ15 r1 引用文件 SHA256 `dbad5b2992b2bddfe66a0e62436f90f97feccb906b9dcbbc36bc85115f98dc93` 与现存 `cases.jsonl` 一致。
- Frozen commit `e9013eb4036b8714b7a8ea863f3b89113c505dac`；GOOGLE_GEMINI / gemini-3.8-flash；PydanticAI 1.107.6。冻结副本离线 `verify_candidate` 再次通过。
- 全部新增轮次原始 Runtime Prompt SHA256：`34821d82b65d01e736a94378177b164bc6cc42045d00b1f0600b46cdb4831ef5`。
- Intent Native Schema SHA256：`8fc4671a333243ecfca2bd9e0ead8200c23882c85b8d0df8d24e78bd1fd99845`；预算仍为 7 Tool Attempts / 8 Model Requests / 60s per turn，继承既有 Retry / Repair。
- 外层 Repeat driver SHA256 `124f141fe00030b0baec6066a8c5ea14158e5503243baec1b6f5fa4665ba1c27` 与实际文件一致，不改变冻结 Production。
- 新 Run 及 Primary 原始 Artifact 不修改，Behavioral PENDING / Critical NOT_EVALUATED 留存；以下是独立 Review 建议。

## 逐次建议

Rubric：回答有效性 / 研究充分性 / 上下文选择 / 状态权威 / 证据与推断 / 对话推进。
按完整 Case 最弱相关轮次评分，不用其他轮次抵消偏差。

| Case / 次数 | Runtime | Behavioral / 最低分建议 | Critical 建议 | Rubric 建议 |
| --- | --- | --- | --- | --- |
| AQ12 r1 | 3/3 COMPLETED | 未达冻结最低分，History 概括偏强 | PASS | 2 / 2 / 1 / 2 / 1 / 2 |
| AQ12 r2 | 3/3 COMPLETED | PASS | PASS | 2 / 2 / 2 / 2 / 2 / 2 |
| AQ12 r3 | 3/3 COMPLETED | PASS | PASS | 2 / 2 / 2 / 2 / 2 / 2 |
| AQ15 r1（Primary 引用） | 2/2 COMPLETED | PASS，沿用独立 Primary Review | PASS | 2 / N/A / 2 / 2 / 2 / 2 |
| AQ15 r2 | 2/2 COMPLETED | PASS | PASS | 2 / N/A / 2 / 2 / 2 / 2 |
| AQ15 r3 | 2/2 COMPLETED | PASS | PASS | 2 / N/A / 2 / 2 / 2 / 2 |

AQ12 的研究只要求当前可执行证据满足多轮对象恢复和比较；每轮重新取得相关 Quote。当前没有开放式 Search，不能因未核验财报扣分。AQ15 是撤销与有效状态检查，不需要市场研究。

### AQ12 实际观察

三次均在同一 Thread 完成 GOOG → MSFT → GOOG；每轮实际 Quote Tool 的 ticker 正确且返回 OK。
GOOG 210.25 / MSFT 500.50 与 Fixture 一致；第三轮各有新 GOOG Quote Source，未引用 MSFT Source。
全部引用匹配本轮 OK Source，Portfolio / Cash / 平均成本 / 成本权重与可见确定性 Context 相符。
未出现主动现金对单股价格比较、把现金变成预算、未经确认的 Candidate 或 Active Intent。

**AQ12 r1 t3 的扣分证据：**

> 因此之前的分析与审慎观望结论依然成立

第一轮只给了持仓 / 现价 / 盈亏事实，以及具体调整需补充策略约束的边界，并未明确形成“观望”建议。
第三轮确认这些事实不变是合法的；将此前事实分析概括成已有“审慎观望结论”则强化了真实 History 的承诺程度。
这是已有 Conversation Continuity / commitment-level 规则下的 Rubric violation：CS / EI 建议各扣至 1。
它不是“第一轮失败却凭空声称存在回答”：第一轮确实成功；也没有声称用户确认策略、写入持久状态，
或基于假市场事实发出确定交易动作。因此建议 Critical PASS，不把两种 Failure Mode 混为一谈。

r2 没有添加不存在的观望结论；r3 第一轮确实包含继续持有 / 暂缓增仓的条件式分析，第三轮仍按条件式描述，
没有强化成用户确认决定。r3 中 NORMAL 大盘代理与浮盈作为条件使用，保留启发式、投资逻辑未验证和未知项，
不因既有已接受的分析表达重新调整 Prompt。

### AQ15 实际观察

r2/r3 首轮均生成 `GOOG:LONG_TERM / POSITION_PLAN_V1 / INVALIDATE / PENDING`，答案明确需要 UI / 系统显式确认。
确认前 `active_before=active_after=1`；独立 Service 确认产生 INVALIDATED v2，随后重建 Service / 新 Thread，
第二轮 `active_before=active_after=0`，没有复活旧 target plan 或写入新 Candidate。
`invalidation_candidate_matches_requested_scope`、`pending_not_injected`、`portfolio_context_unchanged` 均为 true。
第二轮说明旧计划不再生效，未否认历史曾经有确认版本；没有 Market Tool over-routing、Ledger Mutation
或 remaining target budget 持久化。结合 Primary r1，三次生命周期建议均通过。

## Runtime、transport 与警告

- 新增五次 Case 执行全部完成，13/13 Ask 完成，NOT_RUN=0；没有最终 Request Failure / timeout。
- 22 次逻辑模型请求，23 次记录到的 Provider model request attempts；9 次模型 Tool Attempt；
  12 次 Application / Fixture fetch，含 r3 三次自动 Market Context。自动补充不增加模型请求次数。
- 一次 transport retry：AQ12 r2 t2 的首个 Model Request（全局 `request_index=9`）首次
  `ConnectError`，21.31ms，cause chain 只有 ConnectError，底层 category UNKNOWN；同一请求的
  attempt 2 恢复并返回 Quote Tool Call，之后 Final 完成。逻辑请求数仍为 2，不把 HTTP attempt 算成新逻辑请求。
- 不强行归因 Google、网络、配额或 socket 类型；既有重试恢复不算 Agent Behavioral failure。
- Repair=0；未观察到 framework retry、duplicate / cache reuse、per-tool denial、Final-only。
- 13 轮 latency 总计 196.12s，中位 12.59s，最大 33.94s（AQ12 r1 t3）。此轮第二模型请求生成
  Final 约 27.77s，整轮仍在 60s 内。没有因此提高 timeout / Retry / Budget。
- Token / Cost UNKNOWN，不作零值估算。

终端 `non-text parts ... ['function_call']` 警告来自已安装 Google SDK 的 response 文本读取属性：
该属性只拼接 text 部分，并提示其他部分需读取完整 parts。PydanticAI GoogleModel 的实际映射使用
`candidate.content.parts`。本次轨迹明确有 ToolCallPart → Quote 执行 → 后续请求携带 Tool Result → TextPart Final，
没有工具丢失证据。未记录警告的精确请求关联，不能由这条日志单独归因某一次请求失败，亦不扩大成兼容性调研。

## Gate 结论与下一步

1. **4B Repeat 的 Critical 一致性要求建议通过：** AQ12 三次、AQ15 三次均建议 Critical PASS；新执行
   与 Primary 引用分开，未用最好结果或平均值覆盖其他结果。
2. **冻结质量最低分尚未无条件通过：** [Decision Proposal §9.1/§9.3](../../plans/ask-quality-decision-proposal.md)
   要求 AQ12 CS / EI 等维度为 2，重复每次达到最低分；r1 的 1 分不能因 r2/r3 通过抹去。
3. 该 finding 不触发 Critical，影响是历史建议的语言概括偏强，没有状态写入或错误金额建议。
   建议由 Human 明确决定是否接受为已知质量瑕疵并给予本次验收例外，然后进入 T8；不自动放宽
   全局 Rubric，也不因为此项立即追加 Prompt、重跑 AQ12 或全量 Core。
4. 如 Human 不接受该例外，先做通用修复 Decision Review；本轮不擅自实现或发送在线补考。
5. T8 仍是最终浏览器 / 集成、保留数据的回退演练、清理及最终 Human Acceptance；整个 Phase 4
   当前尚未最终完成。AQ04 / Research / Web Search 继续延期，不接新 Provider。

本轮只做离线 Artifact / 引用 digest / 来源与生命周期一致性检查、冻结预检和文档 Review。
无 Production 修改，无新增在线请求，无 .env 读取，无 main 合并 / push。没有代码变更，不重复无关 pytest。

## Human Decision（2026-10-04）

Human 明确接受 AQ12 r1 历史概括偏强为已知 non-blocking finding，给予本次压力测试例外通过。
原 CS / EI 建议 1 分及冻结最低分保持原始记录；Critical PASS；不改 Prompt，不重跑任何测试。
批准进入 T8 浏览器、数据保留回退演练和最终报告。整个 Phase 4 Final Acceptance 仍待 T8 后单独确认。
