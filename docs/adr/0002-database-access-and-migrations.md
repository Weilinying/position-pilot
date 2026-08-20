# ADR 0002：Database Access 与 Migration 基础方案

## 状态

已接受（2026-08-20）

## 背景

`PROJECT.md` 已确定 PostgreSQL 是 V1 Structured State 的关系型数据库。M0 只需要建立 Development PostgreSQL 连接和 Migration 基础能力，不创建 M1 的 User、Cash、Transaction 或 Position 等业务 Schema。

数据库访问方案需要支持后续确定性业务逻辑、明确依赖边界和可追踪的 Schema 变更，同时避免在尚无并发需求证据时引入异步复杂度。

## 候选方案

### Database Access

- 同步 SQLAlchemy 2.0 + psycopg 3
- SQLModel
- raw psycopg

### Migration

- Alembic
- 独立 SQL Migration 工具
- 手写 SQL Migration 流程

### Development PostgreSQL

- 使用 Docker Compose 提供标准本地实例
- 由开发者自行安装 PostgreSQL
- 使用共享远程开发数据库

## 决策

- Database Access 使用同步 SQLAlchemy 2.0 和 psycopg 3。
- Migration 使用 Alembic。
- 标准本地 Development PostgreSQL 通过 Docker Compose 提供，并固定 PostgreSQL 17。
- 应用通过 `DATABASE_URL` 连接数据库，允许开发者将其指向兼容的外部开发实例。

## 理由

- SQLAlchemy 2.0 能为 M1 提供成熟的数据访问能力，同时允许 Domain 层与具体 ORM 解耦。
- 同步访问方式足以满足当前 Milestone，避免提前承担异步 Session、事务和测试复杂度。
- Alembic 与 SQLAlchemy 配合直接，能够让 Schema 变化进入可审查、可追踪的 Migration 流程。
- Docker Compose 提供可复现的本地 PostgreSQL 环境，而 `DATABASE_URL` 保留使用已有开发实例的能力。

## Trade-off

- SQLAlchemy 相比 raw psycopg 多一层抽象。
- 同步数据库访问不以最大并发能力为目标；只有真实性能需求出现后才考虑异步方案。
- Alembic 增加了 Migration environment 配置，自动生成的 Migration 仍需人工审查。
- 标准本地方案依赖 Docker daemon；不使用 Docker 的开发者需要自行提供兼容的 PostgreSQL 17 连接。

## 重新考虑条件

- 实际负载或 Evaluation 证明同步访问成为明确瓶颈。
- 部署环境或团队基础设施要求不同的 PostgreSQL major 或开发数据库供应方式。
- SQLAlchemy 或 Alembic 无法满足已经出现的 Schema、事务或 Migration 需求。
