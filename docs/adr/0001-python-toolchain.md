# ADR 0001：Python 工程工具链

## 状态

已接受（2026-08-20）

## 背景

M0 需要建立可运行、可测试、可继续演进的最小 Python 工程骨架。`PROJECT.md` 已确定使用 Python、FastAPI、Pydantic 和 pytest，但尚未确定 Python 版本、依赖管理、Formatter、Lint 和 Type Check 工具。

这些选择会成为后续 Milestone 的共同工程基线，因此需要在开始 M0 实现前统一，并避免同时维护功能重叠的工具。

## 候选方案

### Python 版本

- Python 3.12
- Python 3.13

### 依赖管理

- uv
- Poetry
- pip-tools

### Formatter 与 Lint

- Ruff 同时负责格式化和 Lint
- Black、isort 与 Flake8 组合

### Type Check

- mypy
- Pyright

## 决策

- 项目 Python 基线使用 Python 3.13。
- 依赖使用 uv 管理，以 `pyproject.toml` 声明依赖并提交 `uv.lock`。
- Ruff 同时负责 Formatter 和 Lint。
- mypy 负责 Type Check。
- pytest 继续作为测试框架。

## 理由

- Python 3.13 与当前开发机命令行环境一致，避免为项目额外维护另一套 Python 基线。
- uv 可以统一依赖声明、锁定和开发命令，且当前开发环境已经具备该工具。
- Ruff 同时承担格式化和 Lint，可以减少工具数量和重复配置。
- mypy 能为核心业务代码和稳定 Schema 提供静态类型检查，并符合项目对 Type Hints 的要求。

## Trade-off

- 使用 Python 3.11 或 3.12 的开发环境需要升级或安装 Python 3.13。
- uv 是团队需要共同采用的额外开发工具。
- Ruff 的格式化结果将成为仓库统一风格，不再同时维护 Black、isort 和 Flake8 配置。
- mypy 在严格检查第三方库时可能需要少量兼容配置，但不因此预先引入额外类型工具。

## 重新考虑条件

- 已确定的核心依赖无法可靠支持 Python 3.13。
- 团队环境或部署平台形成了不同且必须遵守的 Python 或依赖管理标准。
- Ruff 或 mypy 出现无法通过合理配置解决的实际兼容问题。
