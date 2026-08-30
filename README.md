# PositionPilot

当前仓库已实现 Portfolio / Transaction Structured State、Current Quote、Price History、Recent News、SPY Market Context、Single Investment Agent，以及 M8 Local Portfolio Management。M8 实现已完成，正在等待 Human Acceptance。

## 前置条件

- Python 3.13
- [uv](https://docs.astral.sh/uv/)
- Docker Desktop（用于本地 PostgreSQL 17）

## 本地开发

在仓库根目录执行：

```bash
# 安装锁定的运行与开发依赖
uv sync --frozen

# 建立本地环境变量文件
cp .env.example .env

# 启动本地 PostgreSQL 17
docker compose up -d postgres

# 对数据库执行所有 Migration；重复运行是安全的
uv run alembic upgrade head

# 启动应用
uv run uvicorn --app-dir backend position_pilot.main:app \
  --host 127.0.0.1 --port 8000 --reload
```

应用启动后，可访问本地界面：

```text
http://127.0.0.1:8000/app/
```

也可以在另一个终端检查：

```bash
curl http://127.0.0.1:8000/health
```

预期响应：

```json
{"status":"ok"}
```

`/health` 只表示应用进程存活，**不检查数据库或其他外部依赖**。

## Local Portfolio Management

页面由 FastAPI 同源托管，不需要 Node、前端安装或单独构建步骤。首次打开 `/app/` 会进入 Start / Recover 引导页，可直接输入 Portfolio Name 与 Initial Cash 创建本地 Portfolio，无需先运行 Demo Seed 或准备 UUID。这是本地 Portfolio 初始化，不是账号注册；M8 没有 Authentication。Initial Cash 在界面中实际默认为 `0`，用户可改为 PositionPilot 开始跟踪时的可用现金。创建成功后，页面会保存最近一次成功加载的 User ID 本地指针并读取完整 Ledger-derived Snapshot。

加载成功后进入单一应用壳：左侧导航在 Decision Chat 与 Portfolio Workspace 之间切换。Decision Chat 采用连续问答流，当前浏览器标签页内的多个 Question / Answer 会依次保留并可从侧栏跳转；它们不会写入 `localStorage`、不会跨刷新恢复，也不会作为下一次模型请求的 Conversation Memory。Portfolio Workspace 将 Positions、Transactions 与 Cash Activity 分开，避免初始化、账本输入和问答堆在同一页面。表单中的灰色内容统一带 `e.g.` / “例如”前缀，只是示例；缺少或非法字段会标记具体输入框并给出对应说明，后端领域失败同时展示稳定 Error Code 与安全 Detail。

M8 的 Positions 只显示由真实 Transaction / Cash Ledger 重放得到的当前状态，尚不能把系统开始跟踪前已经存在的仓位直接导入。已有仓位不能伪造成历史 BUY；Text / Screenshot Import 与 Opening Position 语义属于 M9 `v1.1.0` 的 Human Review 范围。

页面支持：

- 通过既有 UUID 恢复 Portfolio，或只忘记浏览器本地指针；Forget 不删除 Server Ledger；
- 追加 BUY / SELL，并独立选择 `LONG_TERM` 或 `SWING`；
- 追加 DEPOSIT / WITHDRAWAL；
- 在独立 Decision Chat 中连续提交多个 Investment Question，并分别展示 Answer、`OK` / `DEGRADED` 和本轮 Context Sources；
- 中文与英文一键切换；切换只改变本地展示文案与时间格式，不改写 Agent Answer 或 Provider Metadata。

Ledger 表单中的发生时间默认留空，此时由 Backend Application Clock 产生当前时间。只有补录历史记录时才填写本地时间；Browser 会转换为带时区的 ISO timestamp。Cash、Shares、Average Cost、Cost Basis、Transaction Amount 与 Fee 始终由后端 Decimal 规则和完整 Ledger replay 产生，Browser 不自行计算。

本地指针只保存最近一个成功加载的 UUID，不保存 Snapshot、交易、问题、回答或 Secret。UUID 不是 Credential；清除浏览器 Storage 或换浏览器后，需要使用 URL 或已保存的 UUID 恢复。

开发与测试仍可选择创建一份带固定 Ledger Records 的隔离 Demo Portfolio：

```bash
uv run --directory backend python -m position_pilot.demo_seed
```

命令会通过正式 Application Service 创建 User 与三条 BUY Ledger Records，并输出 User ID 与可直接访问的本地页面 URL。它不是正常使用前置条件；重复执行会创建新的 Demo User，不覆盖既有 Portfolio。

如果 Mutation POST 的连接在响应前中断，页面会将当前 Snapshot 标记为需要刷新且不会自动重试。重新 Load 只取得最新 deterministic State，M8 不保证仅凭 Snapshot 精确判断某一次不确定 POST 是否已经执行。Create Response 丢失时也可能留下当前 UI 无法恢复的本地 Portfolio，这是无 Idempotency、Enumeration 与 Authentication 的已知 localhost 限制。

当前没有 Authentication / Authorization，User ID 不是访问控制。推荐启动命令只绑定 `127.0.0.1`；不得把该 Demo Server 直接暴露到公网或不受控局域网。

## Market Data

M2 使用 Alpaca Market Data API v2 REST。Current Quote 来自实时 IEX feed，Historical Daily OHLCV 来自至少延迟 15 分钟的 SIP feed。调用方通过 Application Service 获取结构化结果；当前没有 Market Data REST endpoint。

在本地 `.env` 配置 `ALPACA_API_KEY_ID` 与 `ALPACA_API_SECRET_KEY` 后，可显式运行真实 Provider smoke test：

```bash
RUN_ALPACA_ONLINE_TESTS=1 uv run pytest tests/integration/test_alpaca_market_data_online.py
```

默认测试不会访问 Alpaca。Provider 选择、数据覆盖限制和备选方案见 [`ADR 0004`](docs/adr/0004-alpaca-market-data-provider.md)。

## Investment Agent

Agent 使用 Single Agent + Native Function Calling。Portfolio Snapshot 必定注入，Quote、History、News 与 Market Context 由 Agent 按需调用；默认 LLM Provider 为阿里云 Model Studio，业务层只依赖通用 `LLMProvider`。

在本地 `.env` 配置 `LLM_API_KEY` 后，可以调用开发用问答接口：

```bash
curl -X POST http://127.0.0.1:8000/v1/investment/questions \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"<existing-user-uuid>","question":"GOOG 今天还能加一点吗？"}'
```

`LLM_BASE_URL`、`LLM_MODEL` 和 `LLM_REQUEST_TIMEOUT_SECONDS` 均可覆盖。当前接口没有 Authentication / Authorization，只适合本地或开发环境，不应直接公开部署。

真实模型 Behavioral Eval 使用固定 Fake Market Data，不进入默认 CI：

```bash
RUN_REAL_LLM_BEHAVIORAL_EVAL=1 \
LLM_API_KEY=<local-secret> \
uv run pytest tests/evaluation/test_real_model_behavior.py -s
```

长期 Evaluation 入口、Human Grounding 与 Model Selection 说明见 [`docs/evaluation/README.md`](docs/evaluation/README.md)，Agent / LLM 决策见 [`ADR 0005`](docs/adr/0005-native-function-calling-and-llm-provider-boundary.md)。

停止本地数据库：

```bash
docker compose down
```

## 测试与质量检查

```bash
uv run pytest
uv run ruff format --check backend tests alembic
uv run ruff check backend tests alembic
uv run mypy backend
uv lock --check
```

默认测试不要求真实数据库；PostgreSQL 集成测试需要显式提供可清理的测试数据库：

```bash
TEST_DATABASE_URL=postgresql+psycopg://position_pilot:position_pilot_dev_password@localhost:5432/position_pilot uv run pytest -m integration
```

数据库集成测试只删除自身创建的 User 与 Transaction。当前模块边界、Structured State 恢复和 Market Data Provider 边界见 [`ARCHITECTURE.md`](ARCHITECTURE.md)。
