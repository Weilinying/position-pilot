# M13 — Position-Aware Market Chart 执行计划

状态：已实现并完成定向验证，等待 Human Acceptance。
目标版本：`v1.3.0`。M12 Technical Context 暂缓，保留编号、暂不绑定版本。

## 1. 目标与页面边界

用户从自己已有的持仓或交易记录进入图表，查看走势、成交量与自己的买卖日期。

- Current Portfolio 的 ticker 行增加紧凑 Chart 入口，原点击展开批次保持不变。
- 图表使用宽 Dialog，顶部固定显示入口 ticker，不增加 ticker 输入、Asset Search 或任意股票浏览。
- 已清仓 ticker 可从 Transaction History 的交易详情或 Accounting Detail 进入同一图表。
- 首版提供日 K、Volume、BUY / SELL 日期标记，支持 1M / 3M / 6M / 1Y，默认 3M。
- 当前持仓入口默认看最近区间；历史入口默认定位所选交易日期，Accounting 历史入口定位最近
  SELL 日期，保证清仓已久的股票也能看到有关记录。
- 支持缩放、拖动、十字光标、范围切换与手工刷新。图表按打开、范围切换和刷新请求数据，
  不加入新的后台轮询，不重置 Portfolio 已展开层级。
- M13 首版不依赖 SMA20 / SMA50；均线与 Agent Technical Context 留给 M12。

## 2. Chart Price Basis 与成本展示

### 2.1 日 K 口径

- 复用现有 Alpaca Adapter，明确发送 `adjustment=all`，Chart API 返回实际 `adjustment=ALL`。
  不依赖 Provider 默认值，不修改现有 Agent 的历史数据口径。
- API 保留 source、feed、currency、adjustment、market timestamp、fetched_at 与行情状态。
  图中简短标注为复权日 K，来源信息可展开查看。
- 沿用 SIP 历史行情和已完成日 K 的处理。盘中未完成日 K 不冒充最终日线；不把 IEX 最新价
  拼入 SIP 蜡烛。复用现有常规收盘与陈旧判断，不新增完整交易日历系统。

### 2.2 Transaction Marker

- BUY / SELL 仅按纽约市场日期定位，标记放在 K 线上下，不用成交价或录入成本指定 Y 坐标。
- 详情显示真实记录的时间、股数、费用及价格口径：含费 BUY 使用“买入成本”，不冒充成交价。
- 多笔同日交易可汇总成一个日期标记，打开后列出每笔交易，不能只保留其中一笔。
- 当天尚无已完成 K 线或该日期没有 Bar 时，不把交易移到相邻交易日；在同一详情区显示
  该范围内尚无对应 K 线的交易，保留正确时间。
- Opening / Reconciliation 不生成 BUY 标记。BUY 更正使用有效版本及有效购买时间；历史
  类型变更不反向改写买卖归属。SELL 跨类型时按现有 allocation 明细显示分配，不硬选一种类型。

### 2.3 Average Cost Line

- 显示前提是 Portfolio 成本与 Chart 价格口径已被明确验证为可直接比较；`adjustment` 字段
  本身不能证明成本可比，切换 RAW 也不能解决未入账公司行动造成的成本问题。
- 当前 Portfolio 没有 Corporate Action Accounting 或成本对齐证明，因此本版对有持仓的股票
  返回 `cost_basis_comparable=false`，不画 ticker / 类型 Average Cost Line。
- 保留现有 Shares、Average Cost、Cost Basis 数字，标注“记录成本”，不把它们叠加到价格轴，
  不从复权日 K 与未对齐成本额外计算图表盈亏。
- 成本线不可用原因通过 `cost_line_unavailable_reason` 返回，当前为 `UNVERIFIED_PRICE_BASIS`；
  完全清仓为 `NO_CURRENT_POSITION`，没有当前成本不填零冒充持仓。
- 不凭“近期买入”“刚校准”“常见股票”或用户勾选推定可比；不增加手工覆盖开关、复权因子
  推算、公司行动查询或会计系统。以后有明确对齐依据时再开放成本线，并补充对应验收。

## 3. 现有能力与接口

| 已有能力 | M13 的使用方式 |
|---|---|
| MarketDataService / HistoricalBarsQuery | 图表按区间读取日线，不受 Agent 45 天 / 30 根查询限制 |
| AlpacaMarketDataProvider / HistoricalBars | 复用 OHLCV、分页、时间、ALL 复权和失败状态 |
| Market Context 的日线完成与陈旧规则 | 只提取实际重复部分供图表复用，不改变 Regime 计算 |
| PortfolioService / ReplayResult | 当前持仓与 SELL allocation 同源，继续使用 Decimal 核算 |
| BUY Correction 与现有历史记录读取 | 输出有效交易标记，保留原事实；前端不另算更正结果 |
| M11 交易详情 / Accounting 明细 | 图表入口及卖出明细复用现有 UI 与字段 |

拟新增只读接口：

`GET /v1/portfolio/chart?ticker=GOOG&range=3M`

- 可选 `anchor_date=YYYY-MM-DD` 用于历史入口，以目标日期为右端定位区间。
  `anchor_date` 为纽约市场日历日期的查询窗口锚点，不要求该日期存在交易 Bar，也不自动移动至最近交易日；省略时使用当前纽约市场日期。
  行情最终边界仍服从已完成 Bar 规则。
  历史窗口的数据覆盖检查相对所选区间末尾进行，不因历史日期距今天很远就标为陈旧行情。
- `1M / 3M / 6M / 1Y` 表示日历时间范围，由 Chart Application 层解析为明确的 requested start / end，再交由行情服务查询，不按固定 Bar 数量解释。
- 用户身份仅从 Session 获取。ticker 必须属于该账户的当前持仓或已有交易记录；不提供
  任意 ticker 的公开行情入口。不存在于该账户的 ticker 返回 404，不请求外部行情。
- ticker 规范化与 Asset Identity 沿用 M9 已有规则；Chart Service 不建立第二套 symbol identity，访问权限基于当前用户已有 Portfolio / Transaction 对应的资产事实判断。
- 返回 ticker、range、实际区间、行情状态、bars、来源时间和明确 adjustment；同时返回
  当前成本摘要、`cost_basis_comparable`、`cost_line_unavailable_reason`、有效交易与标记日期。
- 价格和成本 API 字段继续用 Decimal 字符串；图表库需要的数字转换只发生在绘图边界，
  不回写或重新核算账户金额。
- 行情缺失、陈旧与 Provider Failure 区分。正常无成交量或无交易标记不能等同于接口失败；
  失败不制造替代价格。已有账户记录在行情失败时仍可查看。
- Application 组装 Chart View，复用一次事实读取与 Replay；API 只校验和序列化。
  不修改 accounting / valuation 的职责，不新增数据库表、缓存或持久化图表状态。

## 4. 执行任务

### T1 — Chart Contract 与行情读取

主线程确认上述数据口径与字段；后端 worker 实现 Chart Application Service、Response 和
Session 绑定路由，复用 MarketDataService 与现有日线过滤逻辑。

验收：返回 adjustment；范围与历史定位正确；ticker 属于当前用户；无行情与失败状态明确；
当前 Agent 的历史范围和 Regime 行为不变。

### T2 — 持仓、历史交易与价格口径映射

在 T1 约定的 Chart View 内复用当前持仓、有效 BUY 更正及 SELL 分配结果，生成日期标记与详情。
输出明确成本不可比状态，本版不生成 Average Cost Line；不复制 Replay 或估算复权后的成本。

验收：多笔同日交易完整保留；跨类型 SELL、已清仓、BUY 更正正确；未对齐的 200 美元成本
与约 100 美元复权 K 线不会被画成可比较的成本线。

### T3 — 图表库与独立渲染模块

前端 worker 使用 TradingView Lightweight Charts，锁定具体版本并随项目静态资源托管，
保留 LICENSE / NOTICE 与官方要求的署名链接。绘图代码放入独立小模块，避免全部继续堆进 app.js。
日 K 与 Volume 共用时间轴，支持十字光标、拖动缩放与 resize；首版不引入新 UI Framework。

验收：图表实际可操作；销毁 Dialog 时释放实例与监听器；数值显示与服务端口径一致。

### T4 — Portfolio / History 入口与 Dialog

连接持仓行、交易详情和 Accounting Detail 的 Chart 入口。Dialog ticker 固定，无搜索框；
展示日期范围、K 线、Volume、交易标记和紧凑的记录成本，复用中英文与原有详情交互。
切换范围或关闭图表后，旧请求不得覆盖新状态。图表打开/关闭不干扰持仓展开或编辑控件。

验收：用户可以从当前或已清仓股票进入正确图表；可选择多笔同日交易；详情标明 BUY 成本含费
等已有记录口径；当前没有可比较依据时不提供成本线开关。

### T5 — 定向验证、Review 与验收

- 后端：范围与 anchor_date、用户隔离、completed/stale、来源与 adjustment、BUY 更正、
  SELL 多类型、已清仓历史、无对应 Bar 日期、不可比较成本线。
- 前端：日期标记和同日明细、两个入口路径、范围切换旧响应保护、不可比成本不画线、实例清理。
- 只维护直接受影响的测试；不建立全量浏览器矩阵，不重复跑未改的 M11 核算回归。
- 运行相关 Ruff / Formatter / mypy / Node 检查，完成 Automated Review 后复跑受影响检查，
  做一次桌面端浏览器验证。
- 实施时同步 Architecture、Changelog 与图表价格口径 ADR；没有新 Failure 不另写重复 Note。

## 5. 分工、顺序与边界

- 主线程先定公共 Contract 与数据口径；后端 worker 执行 T1–T2，前端 worker 执行 T3–T4，
  约定固定响应后可并行；主线程负责整合、Review、文档和本地提交。
- 当前 M11 仍待 Human Acceptance。M13 从验收后的 M11 基线建立 `codex/m13-position-chart`；
  本次计划整理不代表已授权合并 M11，也不提前改动产品代码。
- M13 不做 M12 指标、任意股票浏览、公司行动会计、分钟 K、WebSocket、图表预测、画线工具、
  回测或账户收益曲线。
- 后续任意股票浏览可复用行情服务另行增加入口，不需要现在扩展 Portfolio Chart 的访问范围。

## 6. Human Acceptance

1. 从持仓行进入对应股票图表；原展开批次功能正常。
2. 从已清仓股票的交易详情或 Accounting Detail 进入历史区间，仍能看到买卖日期和历史记录。
3. 切换 1M / 3M / 6M / 1Y，缩放、拖动、十字光标正常，无旧请求覆盖。
4. 同日多笔交易能全部查看；BUY 更正反映到有效记录；不把校准/起始持仓标为真实买入。
5. API 明确返回 ALL 复权口径；标记不按交易价格定位 Y 轴。未经对齐的成本只显示为记录数字，
   不出现误导性的 Average Cost Line，且没有新增公司行动系统。
6. 图表没有 ticker 搜索或独立股票浏览功能；行情不可用时不展示伪造价格。

## 7. 实施记录

- 新增 Session 限定的 `GET /v1/portfolio/chart`，由一次 Portfolio 事实读取取得统一 ReplayResult
  与有效交易；ticker 不属于当前持仓或交易事实时，在访问行情前拒绝。
- 后端按纽约日期解析日历范围与历史锚点，过滤未完成日 K，并返回来源、SIP、`ALL` 复权、
  当前记录成本、按日期分组的有效交易和 SELL 批次分配。
- 前端使用自托管的 TradingView Lightweight Charts 5.2.0，持仓行、交易详情与 Accounting Detail
  均可进入固定 ticker 的宽图表 Dialog；收益明细有 SELL 时锚定最近一次 SELL 的纽约市场日期，
  没有 SELL 时使用最近区间；支持范围切换、刷新、缩放、拖动、十字光标、同日记录选择和实例清理。
- 当前成本只显示为记录数字，API 固定返回不可比状态，前端没有 Average Cost Line 或强制开启入口。
- 真实浏览器验证覆盖当前持仓入口、历史交易入口、Accounting Detail 的最近 SELL 锚点 / 无 SELL
  最近区间、日 K / Volume、SELL 日期标记、复权来源、成本提示、区间切换和 Provider Failure 下
  保留交易事实。验收时发现的上游分块读取中断已映射为 `PROVIDER_UNAVAILABLE`，不再泄漏为 API 500。
- 定向验证覆盖 Chart Service / API / Product Interface / Market Context、Frontend Chart 与背景行情
  刷新，以及相关 Ruff、Formatter、mypy 和 JavaScript syntax；未运行全量测试。
