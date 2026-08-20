# M0 — Project Foundation 执行计划

## 1. 状态与目标

本计划记录已经通过 Human Review 的 M0 技术方案和最小执行顺序。创建本文档不代表 M0 已开始实现，Milestone 状态仍以 `ROADMAP.md` 为准。

M0 的目标是建立可运行、可测试、可继续演进的最小 Python 工程骨架，不实现投资业务。

## 2. 已确认技术方案

- Python 3.13。
- uv 管理依赖，使用 `pyproject.toml` 和 `uv.lock`。
- FastAPI、Pydantic 和 pytest 沿用 `PROJECT.md` 已确定方向。
- Uvicorn 作为 ASGI Server。
- `pydantic-settings` 负责类型化运行时配置。
- 同步 SQLAlchemy 2.0 + psycopg 3 负责 Database Access。
- Alembic 负责 Migration。
- Docker Compose 提供标准本地 Development PostgreSQL 17；应用通过 `DATABASE_URL` 连接，并允许使用兼容的外部开发实例。
- Ruff 同时负责 Formatter 和 Lint。
- mypy 负责 Type Check。

## 3. Scope

- 建立最小 Python package 和 FastAPI application 入口。
- 实现 `GET /health`。
- 建立环境变量配置和 Development PostgreSQL 连接。
- 建立 Alembic Migration 基础能力。
- 建立 pytest、Ruff 和 mypy 配置。
- 补充 `.env.example`、`.gitignore` 和最小本地开发说明。

## 4. Non-Goals

- 不实现 User、Cash、Transaction、Position、BUY / SELL 或 `LONG_TERM` / `SWING`。
- 不创建 M1 业务表或提前设计 Position Persistence Strategy。
- 不引入 LLM、Agent Orchestration、Market Data、News、Fundamentals 或其他外部 Provider。
- 不建设前端、认证、Redis、Cache、Queue、Vector Database、微服务或完整 Observability Platform。
- 不创建自定义 Codex planner、reviewer、worker 或 explorer。

## 5. Acceptance Criteria

### 5.1 工程基线

- 仓库明确声明 Python 3.13。
- 可通过 uv 从锁定依赖建立开发环境。
- 项目依赖只覆盖 M0 和紧接的 M1 所需基础能力。

### 5.2 Application

- FastAPI application 可以按项目文档在本地启动。
- `GET /health` 返回 HTTP 200 和稳定的最小 JSON Response。
- `/health` 只表示 Application 存活，不与数据库连通性耦合。
- `/health` 存在 pytest 自动化测试。

### 5.3 Database 与 Migration

- Development PostgreSQL 17 可以按项目文档通过 Docker Compose 启动。
- 数据库连接信息从 `DATABASE_URL` 读取，不硬编码 Credential。
- Alembic 使用相同的配置建立数据库连接。
- 对干净的开发数据库执行 Migration 到 head 成功，并可重复执行。
- M0 不创建投资业务 Schema。

### 5.4 质量检查

- pytest 可以发现并通过 M0 测试。
- Ruff format check、Ruff lint 和 mypy 均可运行并通过。
- 检查范围覆盖项目源码和测试，不扫描虚拟环境、缓存或 IDE 文件。

### 5.5 配置与文档

- `.env.example` 存在，只包含安全的示例值或占位值。
- `.env`、虚拟环境、Python 缓存、测试/类型检查缓存和构建产物被 Git 忽略。
- 项目文档说明依赖安装、数据库启动、Migration、Application 启动、测试和质量检查方式。

### 5.6 范围检查

- 没有实现 M1 或未来 Milestone 的产品能力。
- 没有为未来需求增加未经证明的 Framework 或 Infrastructure。

## 6. 当前 Repository 约束

- `backend/`、`tests/` 和 `docs/` 当前没有实现内容，应复用这些既有目录意图，不重新套用大型项目模板。
- 根目录 `main.py` 是未跟踪的 PyCharm 示例文件，不属于现有产品实现。M0 不依赖、不覆盖也不提交该文件；若后续需要删除，应先由用户确认。
- `frontend/` 不属于 M0，保持不动。
- `.idea/` 继续作为本地 IDE 配置，不进入 Git。

## 7. 最小任务与依赖

```text
T1 工程与依赖基线
  ↓
T2 FastAPI /health 与测试
  ↓
T3 PostgreSQL 配置与 Alembic
  ↓
T4 环境示例、Git Ignore 与开发说明
  ↓
T5 全量验证
  ↓
T6 Automated Review → 修复 → 再验证
  ↓
Human Acceptance
```

### T1：工程与依赖基线

- 建立 Python package、`pyproject.toml` 和 `uv.lock`。
- 配置 pytest、Ruff 和 mypy。
- 只加入已批准的 M0 依赖。

该任务修改所有后续任务依赖的公共配置，应由主线程串行完成。

### T2：FastAPI Health Slice

- 建立 FastAPI application 和 Uvicorn 入口。
- 实现 `GET /health`。
- 增加 health 测试。

任务边界明确，适合交给 worker；必须在 T1 后执行。

### T3：Database 与 Migration

- 建立 `pydantic-settings` 配置边界。
- 建立同步 SQLAlchemy engine 和连接配置。
- 增加 Development PostgreSQL 17 的 Docker Compose 配置。
- 建立 Alembic environment，不创建 M1 业务 Schema。
- 验证数据库连接与 Migration 到 head。

任务边界明确，适合交给 worker。由于会接触公共配置和依赖，默认在 T2 后串行执行。

### T4：开发环境文档收口

- 创建安全的 `.env.example`。
- 补充 `.gitignore`。
- 记录实际可运行的本地开发命令。

该任务适合交给 worker，但必须等待 T1 至 T3 的真实命令和目录结构稳定。

### T5：全量验证

- 从锁定依赖验证安装流程。
- 验证 PostgreSQL 启动和连接。
- 验证 Migration、Application、`GET /health`、pytest、Ruff 和 mypy。
- 检查没有无关修改或 M1 内容。

该任务由主线程串行完成。

### T6：Review 与再验证

- 在基础检查通过后执行 Automated Review。
- 修复需要处理的问题。
- 重新运行所有受影响的测试和质量检查。
- 准备 Human Acceptance；未经明确授权不合并到 `main`。

该任务由主线程或独立 reviewer 执行；不需要创建自定义 reviewer。

## 8. 并行原则

M0 规模较小，T2 和 T3 都依赖 T1，并会共享配置边界。默认按顺序执行，避免为了并行增加协调成本。只有在文件所有权和公共接口已经稳定、修改范围确认不冲突时，才考虑并行。
