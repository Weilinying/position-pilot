# PositionPilot

当前仓库已完成 Portfolio / Transaction Structured State、Current Quote、Price History、Recent News、SPY Market Context，以及基于 Native Function Calling 的 Single Investment Agent。当前 Milestone 为 M7 Minimal Product Interface。

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

## Minimal Product Interface

M7 页面由 FastAPI 同源托管，不需要 Node、前端安装或单独构建步骤。页面支持加载只读 Portfolio Snapshot、提交 Investment Question，并展示 Answer、`OK` / `DEGRADED` 和本轮 Context Sources。

准备好 PostgreSQL 与 Migration 后，可以创建一份新的隔离 Demo Portfolio：

```bash
uv run --directory backend python -m position_pilot.demo_seed
```

命令会通过正式 Application Service 创建 User 与三条 BUY Ledger Records，并输出 User ID 与可直接访问的本地页面 URL。重复执行会创建新的 Demo User，不覆盖既有 Portfolio。

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
uv run ruff format --check backend tests
uv run ruff check backend tests
uv run mypy
```

默认测试不要求真实数据库；PostgreSQL 集成测试需要显式提供可清理的测试数据库：

```bash
TEST_DATABASE_URL=postgresql+psycopg://position_pilot:position_pilot_dev_password@localhost:5432/position_pilot uv run pytest -m integration
```

数据库集成测试只删除自身创建的 User 与 Transaction。当前模块边界、Structured State 恢复和 Market Data Provider 边界见 [`ARCHITECTURE.md`](ARCHITECTURE.md)。
