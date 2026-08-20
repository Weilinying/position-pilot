"""数据库访问的基础设施边界。"""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from position_pilot.config import get_settings


class Base(DeclarativeBase):
    """所有 SQLAlchemy 持久化 Model 的共同元数据。"""


def get_database_url() -> str:
    """返回已校验的 SQLAlchemy 数据库连接地址。"""

    return str(get_settings().database_url)


def create_database_engine(database_url: str) -> Engine:
    """创建同步 SQLAlchemy 数据库引擎。

    参数:
        database_url: 已校验的 SQLAlchemy 连接地址。
    """

    return create_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """创建同步 Session Factory，每次 Application 操作独占一个 Session。"""

    return sessionmaker(bind=engine, expire_on_commit=False)
