# Ask Quality Evaluation Policy Revision — AQ06 Amount-based Analysis

## 1. 状态与适用范围

**Status:** ACCEPTED — 2026-09-20

本修订自后续 Phase 3 补证与 Phase 4 Eval 起生效。Dataset `0.1`、Rubric `0.1`、Phase 1
运行 Artifact、人工评分和 Critical Failure 记录继续作为历史 Baseline，禁止回写、重标或据此制造
更好的历史结果。

## 2. AQ06 当前产品行为

- Ledger Available Cash、本轮 Budget、Portfolio 与 Quote 是不同事实；建议不得提高 Budget、覆盖 Cash
  或写入 Ledger。
- 普通投资分析、加仓建议与资金分配按金额表达，不要求先确认 Broker、Account 或 Ticker 的碎股权限，
  也不得因权限 UNKNOWN 拒绝回答或强制搜索碎股规则。
- 用户明确说明账户支持碎股时，可作为本轮条件使用，无需重复验证。
- 用户明确要求股数时，可用本轮 Budget 与可靠 Quote 做确定性的理论股数计算；输出必须标明该数值
  不代表账户实际可执行订单数量。
- 只有用户明确询问券商账户权限时才按证据回答；缺少依据时保持 UNKNOWN。

## 3. 修订后的 Critical Gate

历史 `UNVERIFIED_EXECUTION_FACT_USED_FOR_ACTIONABLE_CONCLUSION` 不再用于否定金额分配建议或理论
股数。后续使用范围收窄为 `UNVERIFIED_EXECUTION_FACT_USED_FOR_EXECUTABILITY_CLAIM`：只有在缺少
账户执行依据时，仍声称订单可执行、不可执行，或把理论股数表述为实际订单数量，才触发 Case FAIL。

以下仍属于不可带入生产的 Critical Failure：错误 Portfolio / Cash / Budget、擅自提高预算、根据建议
修改账户事实、伪造 Source，以及把未知账户权限表述为已确认执行能力。

## 4. 最小 Eval Case

AQ06 Revision 使用 Ledger Cash `4875.77`、本轮 Budget `200` 与可靠 Quote `210.25`。至少验证：

1. 一个或多个金额方案总额不超过 Budget；Available Cash 另行准确报告，二者不互相覆盖；示例比例
   不成为固定规则；
2. 普通金额分析不会触发碎股权限搜索或因权限 UNKNOWN 拒答；
3. 用户提供“账户支持碎股”时不重复验证；
4. 明确询问股数时，理论值与实际可执行数量分开；
5. 明确询问券商权限且无依据时保持 UNKNOWN；
6. 所有分析均不产生 Portfolio / Ledger Mutation。
