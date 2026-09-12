# M11 — Accounting & P&L 执行计划

日期：2026-09-11；2026-09-12 修订。状态：T1–T4 已实现并通过定向验证与 Automated Review，待 Human Acceptance。

已确认：M10 Transaction Import 暂缓，M11 直接承接已合并的 M9；保留 Milestone 编号。
目标版本：`v1.2.0`。收益口径与只读 API 已获批准；下文已纳入分配审计字段、统一 ReplayResult
与独立 accounting / valuation、首页 summary 聚合三项修订。

## 1. 目标与当前实现

用户可以看见每次卖出赚亏多少、所有已记录卖出的累计盈亏，以及当前持仓的浮动盈亏。
手工 BUY / SELL 已足够提供交易事实，M11 不依赖截图识别交易。

| 已有实现 | M11 复用方式 |
|---|---|
| `domain/portfolio.py` 的 `rebuild_portfolio()` | 在同一 Replay 的 SELL 分配处产生已实现结果，不另写一套重放 |
| immutable Transaction / Opening / Reconciliation / Classification Change / BUY Correction | 保留事实结构、经济顺序与现有写入规则 |
| SELL 显式 `LotAllocation` | 确定每次卖出释放哪个批次的成本 |
| `domain/portfolio_valuation.py` | 复用每个 ticker、类型和批次的当前市值、未实现盈亏与百分比 |
| `PortfolioValuationService` | 复用行情读取、新鲜度检查与失败语义 |
| `PortfolioService` / Unit of Work | 从同一批完整账本事实计算持仓与已实现盈亏 |
| 当前持仓表、紧凑交易历史和详情 Dialog | 增加收益摘要与卖出明细，保留现有页面层级 |

当前缺口：SELL 已经扣减成本，但释放成本并未作为结果返回；全部卖出的 Lot 从当前视图移除。
因此不能仅从当前持仓或前端历史行反推累计收益。当前只支持 BUY 更正，未实现 SELL 更正或 Void；
本轮不把这些能力当作已有基础，也不顺带建设通用交易历史编辑器。

## 2. 已批准核算口径

### D1：M11 先提供收益金额和单次卖出收益率

- 单次卖出已实现盈亏 = 卖出成交金额 − 已记录卖出费用 − 实际释放的批次成本。
- 单次卖出收益率 = 单次已实现盈亏 / 释放成本 × 100%。
- 累计已实现盈亏 = 全部已记录 SELL 的已实现盈亏之和，包括已经清仓的 ticker。
- 当前未实现盈亏与百分比沿用 M9，不预扣未来卖出费用。
- 交易盈亏合计 = 累计已实现盈亏 + 当前未实现盈亏，仅为账本覆盖范围内的金额汇总。
- 不提供一个把多次卖出百分比相加或平均得到的“账户收益率”。TWR、MWR / XIRR、每日净值和
  收益曲线继续留在后续范围；需要它们时另行制定资金和历史估值方案。

Opening / Reconciliation 的买入日期未知不妨碍按已确认成本计算后续卖出的盈亏，但无法恢复
导入前未记录的卖出历史。不把上述指标称为券商账户成立以来的完整历史收益。

### D2：费用与成本沿用 M9；舍入后严格对账

- 新手工 BUY 的输入价已经含费；不再次追加佣金。旧版 BUY 的批次成本继续包含原已记录佣金。
- SELL 使用其实际持久化费用；同一 SELL 跨批次时按分配股数占比分摊费用和成交金额。
- 金额使用 Decimal，内部保持现有 8 位小数与 ROUND_HALF_EVEN；UI 按美元两位小数显示。
- 批次分配的舍入余数放入稳定排序后的最后一个分配项，确保子项之和等于整笔金额和费用。
- 释放成本取同一 SELL 分配步骤中的“扣减前成本 − 扣减后成本”；全卖时释放全部剩余成本。
  当前部分卖出按已舍入单位成本计算剩余成本，直接另算“单位成本 × 卖出量”可能产生尾差。
  此方案沿用 M9 剩余持仓结果，不重算历史买入费用或调整原成本扣减算法。
- 无 SELL 时累计已实现为 0；有合法 SELL 但释放成本因极小数舍入为 0 时，金额照常返回，
  收益率为空，不用异常或虚构百分比替代。

### D3：已实现收益按卖出当时的批次类型归属

- 使用 Replay 处理该 SELL 时 Lot 的 `UNSPECIFIED / SWING / LONG_TERM`。
- 后续改变剩余批次类型，只改变当前持仓及未实现分类，不搬动已经发生的卖出收益。
- 一笔 SELL 涉及不同类型时按实际分配拆分收益，不将整笔收益归到 Transaction 的单一类型字段。
- 相同时间继续沿用现有顺序：Cash → Reconciliation → Transaction → Classification Change；
  因此同一时间戳的类型变更在 SELL 之后生效。
- BUY 更正会影响引用该批次的历史 SELL 成本；接受更正后已实现及未实现结果一起重算。

### D4：校准、出入金不产生交易收益

- Opening、Reconciliation、DEPOSIT、WITHDRAWAL 本身不产生已实现盈亏。
- Reconciliation 按既有语义影响生效后的剩余成本；不追溯改写校准前 SELL 的成本结果。
- 校准后总资产或未实现盈亏变化不能称为当天赚亏；M11 不提供当日收益或资金流推导的账户收益率。
- 存在校准时，在收益详情显示一句短说明：收益按已记录交易与确认成本计算。工程机制不放主页面。

### 算例

买入 10 股，含费均价 $100；卖出 4 股，每股 $120，卖出费用 $1：

- 释放成本 $400；净收入 $479；已实现盈亏 $79，单次收益率 19.75%。
- 剩余 6 股，成本 $600；若现价 $110，则未实现盈亏 $60，未实现收益率 10%。
- 交易盈亏合计 $139。后续把剩余 6 股从波段改为长期，过去的 $79 仍归波段。

## 3. 页面结构

```text
Current Portfolio
已实现 +$79   未实现 +$60   交易盈亏 +$139   [明细]
[现有 ticker → 未分类批次 / 波段 / 长期持仓表]

Transaction History
Time | Ticker | Side | Shares | Price | Fee | Type | P/L | Status
```

- 收益摘要使用一行轻量文字和数字，不堆叠大 Card。
- 主持仓表保留 M9 列与展开方式；已清仓 ticker 不重新塞回 Current Portfolio。
- 历史 SELL 行增加已实现 P/L；BUY 与 Cash 行显示 `—`。单次收益率放详情，控制表格宽度。
- SELL 详情显示成交额、费用、净收入、释放成本、已实现盈亏及收益率；下面紧凑列出各来源批次、
  卖出时类型、分配股数、释放成本和收益。
- 摘要“明细”打开紧凑 Dialog，按 ticker / 类型查看已实现与未实现汇总；包括已清仓 ticker。
  默认统计全部已记录历史，本阶段不增加日期筛选与图表。
- 显示历史收益分类时明确为“卖出时类型”；历史交易原类型继续保留，避免同一字段出现两种含义。
- 行情失败时已实现仍正常展示；有持仓但任一所需行情不可用时，组合未实现与交易盈亏合计显示
  `—` / “部分行情不可用”，不把部分股票之和显示为完整总额。可用 ticker 明细仍显示。
- 全部清仓时未实现为 0，交易盈亏合计等于已实现，不为已清仓 ticker 请求当前行情。
- 刷新沿用现有交互和取消机制，不因收益读取锁住编辑表单；前端不计算金融数值。

## 4. 实施任务

### T1 — 在现有 Replay 输出卖出成本与收益

涉及 `domain/portfolio.py`，按职责需要新增小型 `domain/portfolio_accounting.py`。
在 SELL 扣减处产生不可变的派生结果：transaction_id、lot_id、ticker、source、occurred_at、
position_type_at_sale、shares、allocated_gross_proceeds、allocated_fee、allocated_net_proceeds、
released_cost、realized_pnl。三个 allocated 字段分别保留该分配的成交额、费用和净收入，便于审计。
从这些结果按交易、ticker / 类型、Portfolio 聚合，生成单次收益率。

`replay_portfolio()` 统一返回 `ReplayResult(portfolio: PortfolioState, sell_allocation_results)`。
`rebuild_portfolio()` 只保留为该核心的 `.portfolio` wrapper。持仓与收益核算必须读取同一 ReplayResult，
不得复制 Replay 或持久化第二份可编辑 P&L 事实表。

验收：部分卖出、多批次卖出与完全卖出的收益一致，分项金额对账；BUY 更正与类型时间语义正确。

### T2 — 核算读取服务和只读 API

涉及 `application/portfolio_service.py`、估值服务、新核算服务、`bootstrap.py`、`main.py`。

- 新增 `GET /v1/portfolio/accounting`，只返回已实现收益、交易及分配明细，不访问行情。
- 现有 `GET /v1/portfolio/valuation` 继续只负责行情估值。
- 新增 `GET /v1/portfolio/summary` 作为首页聚合接口，复用当前 Session Ownership。
- 一次读取完整事实、一次 Replay 获得当前持仓与已实现结果；同一份当前持仓输入已有估值计算。
- 每个当前 ticker 至多调用一次行情；返回摘要、ticker / 类型汇总、SELL 与 allocation 明细，
  以及复用现有字段结构的当前估值、行情状态、来源和时间。
- 新页面以 `/summary` 替代原 `/portfolio` 和 `/valuation` 的独立请求，避免同次刷新重复读取。
- 金额仍用 Decimal 字符串传输；空行情与零收益明确区分。前端按交易 ID 关联收益明细。
- 不增加定时任务、缓存、数据库或估值快照表，预计无 Schema Migration。

验收：当前用户隔离正确；历史已实现不依赖行情成功；组合部分行情缺失不生成假总额。

### T3 — 紧凑收益 UI

修改 `frontend/index.html`、`frontend/app.js`、`frontend/styles.css`：一行摘要、历史 P/L 列、
SELL 详情与按 ticker / 类型汇总 Dialog。复用现有中英文文案、数字格式和异步状态处理。

验收：卖出、现有 BUY 更正、分类变更与刷新后数据更新；完全卖出的收益仍可查询；未实现持仓表
保持原层级与编辑入口，批次详情无需暴露 Replay / Ledger 等工程术语。

### T4 — 定向验证、Review 与文档

- 维护直接受影响的 `tests/unit/test_portfolio_domain.py`、`test_portfolio_service.py`、
  `test_portfolio_valuation.py`；收益聚合和 API 可新增小型专用测试文件。
- 核心用例：盈利/亏损、部分/全部卖出、不同成本批次、碎股连续卖出与舍入尾差、跨类型费用分摊、
  历史佣金、BUY 更正、分类前后、校准前后、出入金不记收益、全清仓、部分行情缺失。
- 只修改受影响的 `tests/test_product_interface.py` 与已有刷新测试；针对摘要、SELL 详情和刷新
  做一次小范围浏览器验证，不新增全量 browser matrix，不调用真实 LLM 做收益测试。
- 运行修改文件相关的现有 Ruff、Formatter、mypy 检查；通过后 Automated Review，按 Review 修复
  并仅重跑受影响检查。Review 重点是成本守恒、费用只计一次、分类时点和校准不伪造收益。
- 计划批准后同步 `PROJECT.md` 的核算语义并记录收益 ADR；实现完成后同步 Architecture、
  Changelog 和本计划状态。无需为普通实现步骤再创建 Engineering Note。

## 5. 边界与依赖

- 顺序：批准 D1–D4 / API → T1 → T2 → T3 → T4 → Human Acceptance。
- 不实现 M10 Transaction Import，不增加买入执行价/独立费用输入，不改历史手续费版本。
- 不实现 SELL Correction / Void、税务成本、股息、汇率、公司行动、账户收益曲线或新增 Agent Tool。
- 现有 Agent Context 尚不携带累计已实现数据；本阶段核算结果用于 Portfolio UI，不宣称问答已支持
  新收益指标。若后续要求 Agent 回答收益问题，可基于本服务增加按需 Context。
- 在 `codex/m11-accounting-pnl` 实施，保留用户原有未跟踪 `main.py`。已批准的规划文档一并纳入，
  按完整且验证通过的任务创建 Atomic Commits；
  Human Acceptance 前不合并，未经授权不 Push / Tag / 发布 Release。

## 6. Human Acceptance

1. 手工录入上述 $79 / $60 算例，检查摘要、SELL 行和批次明细一致。
2. 一次卖出两批不同成本/类型的股票，确认分项之和等于整笔卖出收益。
3. 把剩余波段仓改为长期，确认之前卖出收益不移动；更正仍可编辑的 BUY 成本时收益重新计算。
4. 全部卖出后 Current Portfolio 移除持仓，历史与收益明细仍保留。
5. 行情不可用时历史已实现可见、组合未实现显示缺失；恢复行情后正常刷新。
6. 校准导入持仓或入金不产生一笔“盈利”；页面不把交易收益金额叫做完整账户历史收益率。

## 7. 执行与验证记录（2026-09-12）

- T1：统一 `ReplayResult`，SELL 分配保存成交额、费用、净收入、释放成本和已实现盈亏；
  `portfolio_accounting.py` 从同一结果按交易、ticker、卖出时类型聚合。
- T2：accounting / valuation 保持独立；summary 使用一次 Replay 和每个当前 ticker 一次行情读取。
  不新增数据库字段或 Migration，不改变原交易写入 Contract。
- T3：顶部紧凑收益摘要、历史 SELL P/L 列、分配明细和 ticker / 类型汇总 Dialog 已连接 summary。
  后台刷新只更新数字，保留当前操作控件与焦点；网络失败保留上次显示结果。
- T4：相关 Domain 测试 52 passed；Accounting API、Summary / Portfolio / Valuation Service 测试
  48 passed；产品界面测试 8 passed；原 valuation API 定向测试 1 passed。
  Node 刷新与金额格式测试、JS 语法检查通过；15 个变更 Python 文件 Ruff / Formatter / mypy 通过。
  未运行全量测试，也未调用真实 LLM 或行情 Provider 做收益核算验证。
- Automated Review 已完成，无待修 finding；浏览器发现的 `0E-8` 金额显示问题已修复并补充
  正负零、极小金额断言。格式调整后，受影响的 Domain / 产品界面测试共 60 passed。
- 浏览器使用独立内存账户：买入 10 股、含费成本 240，卖出 4 股、成交价 260、Fee 1，
  固定行情 250；摘要、历史 SELL、批次明细和类型汇总均得到已实现 79、未实现 60、合计 139。
  桌面端卖出明细扩宽，分摊列完整可见；汇总 Dialog 已修正宽度与边距。
- 真实本地服务按原方式重启，8000 端口已加载 accounting / summary 新接口；未修改真实持仓数据。
- 已同步 PROJECT、ROADMAP、ARCHITECTURE、CHANGELOG 和 ADR 0013；无需额外 Engineering Note。
  本阶段只提交 Feature Branch，Human Acceptance 前不合并到 main。

### 验收建议补充（2026-09-12）

- 补充 BUY Correction → 多次 Historical SELL P&L 测试：6 股买入成本由 100 更正为 110，
  已发生的两笔卖出收益分别从 39 / 28 重算为 19 / 18，累计从 67 变为 37；检查分配成本、
  ticker / 类型汇总同步，卖出成交额与费用不变，剩余 3 股成本为 330，原 BUY 保留。
- Cost Basis 展示记入 ROADMAP 的 Portfolio UI 后续增强，待排期，不扩展本轮 UI 范围。
- 新增用例定向运行 1 passed；变更测试文件 Ruff / Formatter / mypy 通过，差异 Review 完成。
