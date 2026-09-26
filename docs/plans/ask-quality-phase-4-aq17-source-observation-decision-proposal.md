# Phase 4 AQ17 Source Observation Decision Proposal

**Status:** APPROVED — AQ17a / b TARGETED ONLINE PASS；FULL CORE PENDING（2026-09-27）

**Human Review 决定：**批准最小 Source Projection 调整，并明确模型可见的 `sources`
只能表示可进入 `source_refs` 的可引用来源。失败 / 空结果的 `status`、`error_code`
等信息由独立的 `attempt_observations` 表达，不再以 Source 形状提供。内部 Trace /
Source Registry 保持完整，SourceValidator 继续作为最终确定性安全边界。

## 1. Problem / Evidence

4A Core Recheck `p4-4a-jun08-core-recheck-1/r1` 再次为 `11 / 13 COMPLETED`。
AQ17a 的 News 为 `NO_NEWS_FOUND`，AQ17b 为 `PROVIDER_UNAVAILABLE`；两者
模型可见的 Tool Observation 均包含 `source_id=null` 的 `RECENT_NEWS(GOOG)`
审计项。模型首个 Final 正确解释 UNKNOWN，却在 `source_refs` 中复制该失败
Source；PositionPilot 正确拒绝。各一次 No-Tool Repair 均发生
`OUTPUT_RETRY_EXHAUSTED / ToolRetryError`，没有可用最终回答。

此前 AQ17a 的单次定向成功不能覆盖两次完整 Primary 中的失败。现有通用 Prompt
已经明确“非 OK Source 不可引用”；再增加示例可能改善概率，但不能证明 AQ17a / b
满足冻结的首轮 Final、`Repair=0` 及三次 Repeat Gate。当前不执行更多同配置付费测试。

## 2. Proposed Minimal Change

只调整 Native Runtime **模型可见** Tool Observation 的 Source 投影：

- `sources` 只列出 `status=OK`、可引用且有 `source_id` 的外部来源；
- `NO_NEWS_FOUND`、`PROVIDER_UNAVAILABLE` 等状态及 `error_code` 继续如实提供，
  非 OK 的尝试仍保留在 Application Tool Trace / Source Registry 供审计和降级响应；
- 若无成功外部来源，模型可见结构显式包含 `"sources": []`，并以通用说明明确：只解释失败或空结果
  不构成成功来源，未使用 Portfolio Facts 时 `source_refs=[]`；
- 混合结果只暴露成功项为可引用来源，不能因整体 `DEGRADED` 隐藏其中成功来源；
  整体状态及各失败关联调用的状态 / `error_code` 仍须模型可见。

这是已冻结 Tool Observation Contract 的修改，已获 Human Review 批准。
它减少模型把审计项误当 Source 的歧义，**不保证**模型永不生成非法引用；
SourceValidator 仍是最终安全边界。

## 3. Unchanged Boundaries / Alternatives

不修改 Public API、`{answer, source_refs}` Output Contract、PydanticAI Framework、
Provider、Tool Authorization、SourceValidator、Citation 规则、一次 Repair、60 秒预算、
AQ17 首轮 `Repair=0` 与三次 Repeat Gate；不重写历史 Artifact。

不采用 Application 静默删除错误 `source_refs`、隐藏 Framework Retry、JSON 文本
Fallback 或把 Repair 成功伪装成首轮合规。仅继续加重 Prompt 是低成本备选，
但两次完整 Primary 均出现 AQ17a 首轮违规，其中后一次已经包含 Prompt 澄清；
目前不能据此认定 Prompt-only 路线足以可靠验收。

## 4. Approved Minimum Verification

1. 离线验证模型可见 `sources` 与内部 Trace 分离：空结果 / Provider Failure
   显式为 `sources: []`，混合成功 / 失败仍保留整体及关联失败状态 / `error_code`；
   Validator 继续拒绝模型声明失败 Source。
2. 使用同一模型 / Endpoint，在新 Artifact 中先定向验证 AQ17a / b 的首轮 Final
   与 `Repair=0`；若仍失败，不反复跑完整 Core，而是重新提出证据与方案。
3. 定向结果达标后再采集完整 Core Primary、冻结 Repeat 与 Rubric / Critical Gate，
   交付 4A Human Review；在此之前不进入 P4-T6～T8。Research Gate 继续独立。

实施后的离线验证及在线定向结果记录于 4A Report。AQ17a / b 定向首轮通过只满足
进入完整 Core 的前置条件，不代表 4A Gate 已通过。
