"""Application 层错误。"""

from uuid import UUID


class ApplicationError(Exception):
    """所有 Application 层错误的基类。"""


class UserNotFound(ApplicationError):
    """请求引用的 User 不存在。"""

    def __init__(self, user_id: UUID) -> None:
        self.user_id = user_id
        super().__init__(f"User {user_id} 不存在")


class OpeningStateSealed(ApplicationError):
    """Portfolio 已有起始仓位或正常经济记录，不能再初始化 Opening State。"""

    def __init__(self) -> None:
        super().__init__("Opening State 已封闭，不能再录入 Existing Positions")
