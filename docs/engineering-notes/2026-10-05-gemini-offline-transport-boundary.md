# Gemini 离线测试的真实 Transport 边界

2026-10-05。

## Problem

本次新增 Smoke 草稿中的错误脱敏测试直接调用真实 Factory，却遗漏了 Transport Mock。
首次全量尝试可能以固定假 Key 连接 Google；没有使用真实 Key，但不能证明没有连接尝试，
该次运行不能作为严格离线证据。主线程在 Worker 完成交付前启动全量检查，也应承担检查边界责任。

Production Runtime 会正常地将 Provider / 网络异常映射为失败结果。只断言“没有泄露 Key”的
测试可能因此通过，不能证明没有发出请求。联网失败与测试成功不能互相替代。

## Decision

新增 Gemini Runtime 与 Smoke 测试模块各自使用局部 autouse Fixture，阻断真实
`httpx.AsyncHTTPTransport.handle_async_request`，通过 `pytest.fail` 直接失败。
它不受 Runtime 的普通 `Exception` 捕获影响，也不影响明确的 `MockTransport`。
错误脱敏测试必须显式注入异常；另有测试验证漏 Mock 时确实失败。修复后重新运行完整离线检查。

## Trade-off / Future

只修当前已发生的漏 Mock 模式，不改 Production Error Handling、不增加网络 Fallback / Retry，
也不引入全仓新测试框架。本次未执行获准在线 Smoke，未将历史或假 Key 的失败尝试作为在线验收。
其他 Provider 出现同类实际 Failure 时再扩大该测试边界。
