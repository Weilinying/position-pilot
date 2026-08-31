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


class EmailAlreadyRegistered(ApplicationError):
    """规范化 Email 已绑定本地 Account。"""

    def __init__(self) -> None:
        super().__init__("该 Email 已注册")


class InvalidCredentials(ApplicationError):
    """登录凭证无效，错误不区分 Email 与 Password。"""

    def __init__(self) -> None:
        super().__init__("Email 或 Password 不正确")


class AuthenticationRequired(ApplicationError):
    """请求没有携带有效且未过期的本地 Session。"""

    def __init__(self) -> None:
        super().__init__("需要登录后继续")


class PortfolioAlreadyExists(ApplicationError):
    """当前 Account 已绑定唯一 Portfolio。"""

    def __init__(self) -> None:
        super().__init__("当前 Account 已创建 Portfolio")
