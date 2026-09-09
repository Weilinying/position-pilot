# Changelog

本文件记录 PositionPilot 面向用户的重要变更。格式参考
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/)，版本号遵循
[Semantic Versioning](https://semver.org/)。

## [Unreleased]

### Added

- 增加 Finnhub-backed Asset Search 与 Recognition symbol 自动验证；Opening Position 只使用本地
  Browser Draft 已绑定的 canonical symbol，不建立本地 Asset Master。
- 增加仅用于 Portfolio Opening State 的 Manual、Text 与 Screenshot Import；Recognition Draft
  可编辑且只存在于当前 Browser / Request 生命周期。
- 增加 Alibaba Model Studio `qwen3-vl-flash` Recognition Boundary、图片隐私披露与 opt-in
  Provider Smoke Tests。
- 增加已有 Portfolio 的 immutable Position Reconciliation；Replay 直接校准目标仓位的 Shares 与
  Average Cost，不生成交易、不修改 Cash，未出现在截图中的持仓保持不变。
- Screenshot Attachment Composer 支持选择文件、拖放、Cmd/Ctrl+V 粘贴与本地预览，只有用户
  点击“开始识别”后才上传。

### Changed

- Ask Composer 支持按 Enter 提交问题、按 Shift+Enter 插入换行；按钮继续复用同一标准
  Form Submit 路径。
- Recognition Confidence 只作为 Human Review Signal；手工输入必须选择 Provider 候选，验证成功的
  Recognition symbol 可自动绑定。Confirm 在 loopback 本地信任边界内不重复调用 Provider，并继续
  要求用户确认与 deterministic Domain Validation。
- Asset Identity 缩减为 canonical symbol、display name 与 exchange；不把 Provider 未明确提供的
  active / inactive 状态推断为 Portfolio Domain Truth。
- Finnhub Adapter 改用项目可工作的 HTTP transport；exact validation 对外明确区分
  `VALID / INVALID / PROVIDER_UNAVAILABLE`，Provider 恢复后的 canonical match 仍需用户确认。

### Fixed

- 中文等输入法仍在 composing 时，Enter 不会误提交问题。
- 空问题、键盘自动重复事件和进行中的请求不会产生额外 Question Request。
- 保留既有 Question Failure、Cancellation 与恢复行为。
- 修复 Provider 网络 / timeout / 429 / 5xx 异常被误判为 invalid ticker，以及可选 Position Type
  被错误显示为必填缺失的问题。

## [1.0.0] - 2026-09-01

### Added

- 提供本地 Email / Password 注册、登录、退出与持久 Session，并由服务端 Session 确定
  Portfolio Ownership。
- 提供 Initial Cash、Existing Positions、BUY / SELL、DEPOSIT / WITHDRAWAL 与完整只读
  Ledger Records，Portfolio State 由确定性 Ledger Replay 产生。
- 提供基于 Portfolio、Current Quote、Price History、Recent News 与 SPY Market Context 的
  Single Investment Agent 问答，并展示经过后端验证的 Context Sources。
- 提供无构建、由 FastAPI 同源托管的 Local Self-Service Product Interface。

[Unreleased]: https://github.com/Weilinying/position-pilot/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Weilinying/position-pilot/tree/v1.0.0
