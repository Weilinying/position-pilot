# PositionPilot

当前仓库包含可运行的 Python 工程基础、健康检查、本地 PostgreSQL 17 开发环境，以及 M1 Portfolio / Transaction Structured State；尚不包含 Market Data、LLM 或 Investment Agent。

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
uv run uvicorn --app-dir backend position_pilot.main:app --reload
```

应用启动后，可在另一个终端检查：

```bash
curl http://127.0.0.1:8000/health
```

预期响应：

```json
{"status":"ok"}
```

`/health` 只表示应用进程存活，**不检查数据库或其他外部依赖**。

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

集成测试只删除自身创建的 User 与 Transaction。M1 的模块边界和 Structured State 恢复流程见 [`ARCHITECTURE.md`](ARCHITECTURE.md)。
