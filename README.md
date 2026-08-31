# PositionPilot

当前仓库已完成并通过 M8 Human Acceptance：Portfolio / Transaction Structured State、Current Quote、Price History、Recent News、SPY Market Context、Single Investment Agent 与 Local Portfolio Management 已形成 `v1.0.0` Local Self-Service MVP。Git Tag / GitHub Release 可在发布时单独创建。

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

页面由 FastAPI 同源托管，不需要 Node、前端安装或单独构建步骤。未认证用户首次打开 `/app/` 只看到产品主页以及 Register / Login；正常产品流程不要求输入、保存或理解 User UUID，也不依赖 Demo Seed。

注册只需要 Display Name、Email 与 Password。Password 使用带随机 Salt 的 `scrypt` Hash 存入本地 PostgreSQL；Browser 只持有七天有效的 `HttpOnly + SameSite=Lax` Session Cookie，Database 只保存 Token Digest。登录成功会轮换当前 Browser Session；Logout、Session 过期或认证失败会清空当前页面的 Portfolio 与 Question Presentation State。M8 不提供 Email Verification、Password Reset、OAuth、MFA、Role / Permission 或远程 Session 管理。

注册后进入一次性 Portfolio Setup。Initial Cash 默认是 `0`；Existing Positions 为可选批量输入，可记录开始跟踪前已经持有的 ticker、shares、average cost 与可选 Position Type。它们属于 immutable Opening State，不扣减现金、不产生交易 sequence，也不会伪造成历史 BUY。用户可以直接从零开始，并在第一笔 Opening Position、Transaction 或 Cash Event 之前稍后添加 Existing Positions；Text / Screenshot Recognition 仍属于 M9 `v1.1.0`。

完成 Setup 后进入单一应用壳：左侧导航在 Decision Questions 与 Portfolio Workspace 之间切换。Question History 会保留当前浏览器标签页内的多个 Question / Answer 并支持跳转；它们不会写入 `localStorage`、不会跨刷新恢复，也不会作为下一次模型请求的 Conversation Memory。每次提问只发送当前 `question`，User Identity 由 Server Session 注入，并调用正式 `InvestmentAgent`；Answer 是默认视觉主体，Sources 默认折叠。Portfolio Workspace 将 Positions、Transactions 与 Cash Activity 分开，避免初始化、账本输入和问答堆在同一页面。

页面支持：

- 通过 HttpOnly Session 恢复当前 Account 与唯一 Portfolio；
- 追加 BUY / SELL；Position Type 可留空并归一为 `UNSPECIFIED`，与 `LONG_TERM`、`SWING` 独立维护；
- 追加 DEPOSIT / WITHDRAWAL；
- 分别查看完整的 Opening Position、Transaction 与 Cash Event 只读记录；
- 在独立 Decision Questions 页面连续提交多个 Investment Question，并分别展示 Answer、`OK` / `DEGRADED` 和本轮 Context Sources；
- 中文与英文一键切换；切换只改变本地展示文案与时间格式，不改写 Agent Answer 或 Provider Metadata。

Ledger 表单中的发生时间默认留空，此时由 Backend Application Clock 产生当前时间。只有补录历史记录时才填写本地时间；Browser 会转换为带时区的 ISO timestamp。Cash、Shares、Average Cost、Cost Basis、Transaction Amount 与 Fee 始终由后端 Decimal 规则和完整 Ledger replay 产生，Browser 不自行计算。

Browser 不把 Account、Email、Password、Session Token、Portfolio、Ledger、Question、Answer 或 Provider Data 写入 `localStorage`。内部 User UUID 仍存在于兼容 API 与 Ledger Response 中，但不是正常 UI 的身份或恢复方式；所有 Portfolio、Ledger 与 Investment Request 都由 Server 校验当前 Session Ownership。

开发与测试仍可选择创建一份带固定 Ledger Records 的隔离 Demo Portfolio：

```bash
uv run --directory backend python -m position_pilot.demo_seed
```

命令会通过正式 Application Service 创建 User 与三条 BUY Ledger Records。它是开发 Fixture，不会自动创建 Account、认领 Portfolio 或替代正常注册流程；重复执行会创建新的 Demo User，不覆盖既有 Portfolio。

如果 Ledger Mutation POST 的连接在响应前中断，页面会将当前 Snapshot 标记为需要刷新且不会自动重试。Reload 只取得最新 deterministic State 与只读 Records，M8 不保证仅凭它们精确判断某一次不确定 POST 是否执行或恰好执行一次。Register Response 丢失时应使用相同 Email 尝试 Login；Portfolio Setup Response 丢失时应刷新并恢复当前 Session State。M8 不增加 Idempotency、Mutation Reconciliation 或 Exactly-once Infrastructure。

M8 Authentication 只服务本地 Self-Service 闭环，不是完整公网 Account Security。推荐启动命令只绑定 `127.0.0.1`；Cookie 为 loopback HTTP 明确使用 `Secure=false`，没有 Rate Limit、TLS、Email Verification 或 Password Recovery，不得把该 Server 宣称为可安全暴露到公网或不受控局域网。

## Market Data

M2 使用 Alpaca Market Data API v2 REST。Current Quote 来自实时 IEX feed，Historical Daily OHLCV 来自至少延迟 15 分钟的 SIP feed。调用方通过 Application Service 获取结构化结果；当前没有 Market Data REST endpoint。

在本地 `.env` 配置 `ALPACA_API_KEY_ID` 与 `ALPACA_API_SECRET_KEY` 后，可显式运行真实 Provider smoke test：

```bash
RUN_ALPACA_ONLINE_TESTS=1 uv run pytest tests/integration/test_alpaca_market_data_online.py
```

默认测试不会访问 Alpaca。Provider 选择、数据覆盖限制和备选方案见 [`ADR 0004`](docs/adr/0004-alpaca-market-data-provider.md)。

## Investment Agent

Agent 使用 Single Agent + Native Function Calling。Portfolio Snapshot 必定注入，Quote、History、News 与 Market Context 由 Agent 按需调用；默认 LLM Provider 为阿里云 Model Studio，业务层只依赖通用 `LLMProvider`。

在本地 `.env` 配置 `LLM_API_KEY` 后，登录用户可以直接在 Decision Questions 页面调用真实 Agent。开发者若需要直接检查 API，必须先取得本地 Session Cookie；Question Body 不接受 `user_id`：

```bash
curl -c /tmp/positionpilot-cookie.txt \
  -X POST http://127.0.0.1:8000/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"<local-email>","password":"<local-password>"}'

curl -b /tmp/positionpilot-cookie.txt \
  -X POST http://127.0.0.1:8000/v1/investment/questions \
  -H 'Content-Type: application/json' \
  -d '{"question":"GOOG 今天还能加一点吗？"}'
```

`LLM_BASE_URL`、`LLM_MODEL` 和 `LLM_REQUEST_TIMEOUT_SECONDS` 均可覆盖。Authentication 仍只适合本地或受控开发环境，不应直接公开部署。

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

数据库集成测试只清理自身创建的 Account、Auth Session、User、Opening Position、Transaction 与 Cash Event。当前模块边界、Structured State 恢复和 Market Data Provider 边界见 [`ARCHITECTURE.md`](ARCHITECTURE.md)。
