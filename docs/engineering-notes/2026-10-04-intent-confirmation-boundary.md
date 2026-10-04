# 持续意图确认的事务与权威边界

## Problem

ACTIVE 与 PENDING 必须共存，第一次确认前尚无 Active 行也必须防止同 scope 竞争。
模型草案、成功 Assistant Answer 和确认版本不能形成半提交；长期仓和波段仓不能共享预算空间。

## Decision

- 三种 Intent 统一采用 canonical ticker + 显式 Position Type，Owner 与 kind 构成完整冲突域。
- 稳定 identity 行与独立 PENDING / ACTIVE Partial Unique Index 提供锁与数据库兜底。
  Thread → identity 锁序与 Conversation 删除一致；不同 Thread / scope 不持有 Account-wide 锁。
- Draft 与真实同 Turn 的 User / 成功 Assistant 在一个 Conversation UoW 写入。确认单独短事务，
  绑定 Candidate ID、revision、base version 与 account-owned idempotency key，旧 Active / 新版本原子替代。
- Pending、过期、Stale、Superseded、Invalidated 不进入决策 Context。用户确认目标不等于确认实时建议。
- 剩余目标预算只从当前 Ledger 派生；BUY / SELL 后重新计算，不从历史 Assistant 或缓存 JSON 恢复。

## Trade-off

增加一张小型 identity 表，避免首个版本前不存在行锁与 Account-wide 锁造成的误阻塞。
过期状态按读取时刻生效，下次同 scope 起草时写回 EXPIRED，无新增后台任务。
Source 逐字依据与 typed payload 能验证来源和字段边界，不能证明任意自然语言 Thesis 的语义正确；
该行为继续由 T7 模型 Eval / Human Review 判断，不增加关键词分类器或“自动确认”。
前端支持取消旧 Pending 后重新起草；Service 同时保留带匹配旧 ID / revision 的原子显式 replacement。

## Trigger / Future

只有 T7 实际暴露行为问题才调整对应通用语义。完整 Memory、自动执行、Search 与价格触发策略不在本次范围。
回退应用代码时保留 0011 表和数据；不能通过 downgrade 删除正式 Intent 历史。
