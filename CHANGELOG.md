# Changelog

本文件记录 PositionPilot 面向用户的重要变更。格式参考
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/)，版本号遵循
[Semantic Versioning](https://semver.org/)。

## [Unreleased]

尚无已记录变更。

## [1.3.0] - 2026-09-13

这是自 `v1.0.0` 后的累计发布。原规划的 `v1.1.0`（M8.1 / M9）与 `v1.2.0`（M11）没有单独创建
Git Tag 或 GitHub Release，其能力与 M13 一并在 `v1.3.0` 发布。

### M11 / M13

#### Added

- M13 增加从当前持仓、历史交易与收益明细进入的宽屏日 K / Volume 图表，支持 1M、3M、6M、1Y 日历范围、
  缩放拖动、十字光标、手工刷新，以及同日多笔 BUY / SELL 记录查看。
- 增加 Session 限定的只读 Portfolio Chart API，返回已完成历史 Bar、`ALL` 复权口径、行情来源、
  当前记录成本和 Replay 派生的有效交易日期；已清仓 ticker 仍可通过交易事实查看历史区间。
- M11 增加单次及累计已实现盈亏，保留完全卖出股票的历史收益；卖出明细显示各批次分配成交额、
  费用、净收入、释放成本和盈亏，按卖出时类型归属。
- 增加紧凑收益摘要、交易历史 P/L 列，以及按 ticker / 持仓类型展开的收益明细。
- 当前持仓表增加 Cost Basis（总成本），显示股票、类型和批次的剩余持仓成本，行情缺失时仍可查看。
- 增加独立只读 accounting 接口与首页 summary 聚合，复用现有 valuation；行情缺失不影响历史
  已实现收益，组合未实现与总额不使用部分股票冒充完整结果。

#### Changed

- 图表交易标记只按纽约市场日期定位，不使用录入价格决定 Y 轴；在账本成本与复权行情没有可验证
  对齐依据时，仅显示记录成本，不绘制 Average Cost Line。
- Portfolio 与卖出收益由统一 ReplayResult 派生，继续保留历史费用、BUY 更正、校准和分类事实。
- M10 Transaction Import 暂缓，M11 基于 M9 手工交易事实推进，目标版本调整为 `v1.2.0`。

#### Fixed

- Alpaca 返回不完整的分块响应时，行情读取会转换为明确的 Provider unavailable 状态，不再让
  Portfolio Chart 请求返回未处理的服务器错误。

### M8.1 / M9

#### Added

- 增加从 BUY、Opening 与 Reconciliation 事实派生的当前持仓批次；SELL 必须明确分配批次，批次
  类型调整与 BUY 成交更正以不可变事件保存并参与完整重放。
- 增加 ticker 总体、策略类型小计和购买批次三层当前估值；同一 ticker 共享一次行情读取，报价
  失败时仍保留股数与成本事实。
- 增加紧凑可展开的当前持仓层级，按 UNSPECIFIED、SWING、LONG_TERM 顺序展示并允许直接修改
  整个批次的类型、打开购买批次更正。

- 增加 Finnhub-backed Asset Search 与 Recognition symbol 自动验证；Opening Position 只使用本地
  Browser Draft 已绑定的 canonical symbol，不建立本地 Asset Master。
- 增加仅用于 Portfolio Opening State 的 Manual、Text 与 Screenshot Import；Recognition Draft
  可编辑且只存在于当前 Browser / Request 生命周期。
- 增加 Alibaba Model Studio `qwen3-vl-flash` Recognition Boundary、图片隐私披露与 opt-in
  Provider Smoke Tests。
- 增加已有 Portfolio 的 immutable Position Reconciliation；Replay 直接校准目标仓位的 Shares 与
  Average Cost，不生成交易、不修改 Cash，未出现在截图中的持仓保持不变。
- Screenshot Attachment Composer 支持一次选择、拖放或连续粘贴最多两张图片，以本地缩略图预览；
  只有用户点击“开始识别”后才依次上传并合并 Draft。

#### Changed

- 图片录入移除独立“浏览图片”按钮，上传后的缩略图可直接打开大图；ticker 改为输入框内联想
  下拉，保存后的导入汇总持仓无需再次上传即可生成手工校准 Draft。
- Portfolio 主持仓页聚焦当前状态，不再并列显示起始持仓与校准事件记录。

- Ask Composer 支持按 Enter 提交问题、按 Shift+Enter 插入换行；按钮继续复用同一标准
  Form Submit 路径。
- Recognition Confidence 只作为 Human Review Signal；手工输入必须选择 Provider 候选，验证成功的
  Recognition symbol 可自动绑定。Confirm 在 loopback 本地信任边界内不重复调用 Provider，并继续
  要求用户确认与 deterministic Domain Validation。
- Asset Identity 缩减为 canonical symbol、display name 与 exchange；不把 Provider 未明确提供的
  active / inactive 状态推断为 Portfolio Domain Truth。
- Finnhub Adapter 改用项目可工作的 HTTP transport；exact validation 对外明确区分
  `VALID / INVALID / PROVIDER_UNAVAILABLE`，Provider 恢复后的 canonical match 仍需用户确认。

#### Fixed

- 中文等输入法仍在 composing 时，Enter 不会误提交问题。
- 空问题、键盘自动重复事件和进行中的请求不会产生额外 Question Request。
- 保留既有 Question Failure、Cancellation 与恢复行为。
- 修复 Provider 网络 / timeout / 429 / 5xx 异常被误判为 invalid ticker，以及可选 Position Type
  被错误显示为必填缺失的问题。
- 修复 Vision 已识别出明确 ticker、但缺少 `suggested_symbol` 时没有执行 exact validation，导致
  TSLA 等有效标的仍被错误要求手工选择候选的问题。

## [1.0.0] - 2026-09-01

### Added

- 提供本地 Email / Password 注册、登录、退出与持久 Session，并由服务端 Session 确定
  Portfolio Ownership。
- 提供 Initial Cash、Existing Positions、BUY / SELL、DEPOSIT / WITHDRAWAL 与完整只读
  Ledger Records，Portfolio State 由确定性 Ledger Replay 产生。
- 提供基于 Portfolio、Current Quote、Price History、Recent News 与 SPY Market Context 的
  Single Investment Agent 问答，并展示经过后端验证的 Context Sources。
- 提供无构建、由 FastAPI 同源托管的 Local Self-Service Product Interface。

[Unreleased]: https://github.com/Weilinying/position-pilot/compare/v1.3.0...HEAD
[1.3.0]: https://github.com/Weilinying/position-pilot/compare/v1.0.0...v1.3.0
[1.0.0]: https://github.com/Weilinying/position-pilot/tree/v1.0.0
