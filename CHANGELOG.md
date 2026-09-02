# Changelog

本文件记录 PositionPilot 面向用户的重要变更。格式参考
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/)，版本号遵循
[Semantic Versioning](https://semver.org/)。

## [Unreleased]

### Added

- 增加 Massive-backed Asset Search 与 exact validation，Opening Position 最终只写入 Provider
  验证后的 canonical symbol，不建立本地 Asset Master。
- 增加仅用于 Portfolio Opening State 的 Manual、Text 与 Screenshot Import；Recognition Draft
  可编辑且只存在于当前 Browser / Request 生命周期。
- 增加 Alibaba Model Studio `qwen3-vl-flash` Recognition Boundary、图片隐私披露与 opt-in
  Provider Smoke Tests。

### Changed

- Ask Composer 支持按 Enter 提交问题、按 Shift+Enter 插入换行；按钮继续复用同一标准
  Form Submit 路径。
- Recognition Confidence 只作为 Human Review Signal；最终写入仍要求用户确认、Asset
  Validation 与 deterministic Domain Validation。

### Fixed

- 中文等输入法仍在 composing 时，Enter 不会误提交问题。
- 空问题、键盘自动重复事件和进行中的请求不会产生额外 Question Request。
- 保留既有 Question Failure、Cancellation 与恢复行为。

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
