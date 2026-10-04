# 有限 4B 一致性 Gate 命令

仅当前冻结 Candidate `e9013eb4036b8714b7a8ea863f3b89113c505dac`，GOOGLE_GEMINI / gemini-3.8-flash。
新命令和外层 helper 位于执行分支，不改冻结 Production、Schema、Prompt、Budget、timeout 或 Retry。

```sh
zsh /private/tmp/position-pilot-phase4b-t6/docs/evaluation/reports/2026-10-04-phase4b-repeat.command
```

- AQ12 r1/r2/r3：每次独立 Fixture / 新 Thread，各三轮真实 ConversationService Ask，包含当前
  Strategy / NoOp Memory 路径和 Intent Native Schema，而非旧 4A adapter。
- AQ15 r2/r3：复用已 Review 的 Primary 脚本，各两轮 Ask；r1 引用本次 Primary 的独立 Artifact，
  核对相同冻结配置并记录其文件 digest，不复制成新运行。r1 的评分仍来自 Primary Review。
- 新增总计 **13 Ask**；这不是 13 次模型请求。预算保守上限 104 次 primary model request + 13 次
  inherited repair；计入每次一次 inherited transport retry 后，最多 234 次 HTTP model attempt。
  实际请求通常远少于上限，不主动重试 Case、增加 quota 或重复已完成补考。
- 首个 Runtime / 生命周期执行失败后停止余下 Run，保留已完成证据和 NOT_RUN；所有完成结果仍是
  PENDING_HUMAN_REVIEW，不能由脚本自动判断语义 Critical PASS。
- 每次写独立 `4B_REPEAT` Artifact，逐条记录 repetition，不混入 Primary / Research / AQ04。
- 用户终端沿用 `uv --env-file` 注入 GEMINI_API_KEY；Agent 未读取文件，不改 Aliyun OCR 配置。
- 运行后提交输出 / Artifact，Review 一致性 Gate 后才进入 T8，命令不会启动 T8 或合并 main。

离线：15 项相关 pytest 通过，Ruff lint / format、mypy 与 zsh 语法通过；`--plan-only` 从冻结副本
导入当前 Harness 并通过配置 / AQ15 r1 引用预检。没有发送新在线请求。

评分澄清：未接入 Web Search 与“可用固定 News Tool”不同；本次没有新闻 / 历史 Fixture，且目标是
生命周期。未调用 News 是 Trace 事实，但不据此认定模型“懒得查新闻”或遗漏必要研究。修订见
[Primary Review](2026-10-04-phase4b-primary-review.md)，不改原 Artifact。
