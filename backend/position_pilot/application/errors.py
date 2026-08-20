"""Application 层错误。"""

from uuid import UUID


class ApplicationError(Exception):
    """所有 Application 层错误的基类。"""


class UserNotFound(ApplicationError):
    """请求引用的 User 不存在。"""

    def __init__(self, user_id: UUID) -> None:
        self.user_id = user_id
        super().__init__(f"User {user_id} 不存在")
