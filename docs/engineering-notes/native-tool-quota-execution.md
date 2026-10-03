# Native Tool quota、Observation 重放与 Final headroom

2026-10-03 Human Review 批准。适用于当前 NativeInvestmentAgent / PydanticAI Runtime。

## Problem

金融 Executor 已有同轮只读缓存，但 Native Session 在查询缓存前预留 per-tool quota。
Quote 第二次可复用，Market 第二次却因 quota=1 抛异常并终止整轮；已有 Observation 和
未用尽的 Request Budget 都不能保住 Final。Framework 的整批工具 UsageLimit 还有同样问题。

## Decision

- 保持 Descriptor 配额 Quote/History/News 各 2、Market 1；不增大预算。
- 先做总 attempt admission、参数和授权校验，再重放匹配的同轮 Observation；
  新逻辑执行才原子预留 per-tool quota。缓存 Key 包含完整 Args（含 Quote purpose）。
- 自动/显式 Market 用同一重放规则；缓存维持原时间与 Source ID，不重记关联执行。
  明确负结果保持原状态；不扩展底层异常重试/缓存策略。
- per-tool 拒绝产生 TOOL_QUOTA_EXHAUSTED，零 Provider fetch/新执行。
  已有失败观察可被准确标识，但不冒充成功行情。单工具拒绝不撤掉其他合法工具。
- 重复、拒绝、非法与整批超额均有 observed attempt；准入 slots 有限。
  超额批次按响应顺序 admission，而 Trace 按实际完成顺序产生，通过 Call ID 对照。
- `A=sum(exposed quotas)`、`R=A+1`；当前为 7/8。
  自动 Context 占 Application execution quota，不占 model-issued attempt 或额外 Request。
- 公共 SDK after_model_request hook 登记 admission，prepared Toolset 在 A 耗尽或最后一次
  Request 时隐藏业务工具。Native Schema/Final Output Tool 不变，不改 Provider abstraction。
- 移交终止型 Framework tool_calls_limit 给上述 admission；保留 request_limit 和原 wall-clock。
  不把总取证耗尽后的违法 Tool Call、Schema 错误或 Provider failure 伪装成成功。

## Trade-off

缓存重复不再挤占不同参数的新执行配额，但仍占总 attempt；最大新取证量不增加。
Final headroom 保证机会，不保证模型遵循、证据充分或剩余时间足够。COMPLETED 仍需独立
Rubric/Critical Gate Review。Provider fetch 计 Reader 调用，不能当成底层 HTTP 或付费次数。

## Trigger / Future

FunctionModel + Fixture 验证执行边界，不证明 Gemini 行为已通过。
新 Candidate 仅定向 AQ12；其 t3 首请求约 26s、总 30s timeout 的既有证据独立保留。
仅在延迟再次稳定复现后另评 wall-clock policy。本轮不加 Prompt、Retry、Repair、Search 或 quota。
