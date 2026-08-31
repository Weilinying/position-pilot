"""本地 Account、密码与持久 Session Application Service。"""

import base64
import binascii
import hashlib
import hmac
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID, uuid4

from position_pilot.application.errors import (
    AuthenticationRequired,
    EmailAlreadyRegistered,
    InvalidCredentials,
    PortfolioAlreadyExists,
)
from position_pilot.application.portfolio_service import OpeningPositionInput
from position_pilot.domain.errors import InvalidPortfolioValue
from position_pilot.domain.portfolio import (
    OpeningPosition,
    User,
    normalize_timestamp,
    rebuild_portfolio,
)

EMAIL_PATTERN = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}$")
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SESSION_TOKEN_BYTES = 32
DEFAULT_SESSION_TTL = timedelta(days=7)


@dataclass(frozen=True, slots=True)
class Account:
    """本地登录身份及其可选单一 Portfolio Ownership。"""

    id: UUID
    email: str
    display_name: str
    password_hash: str
    portfolio_user_id: UUID | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AuthSession:
    """只保存 Token Digest 的可撤销本地 Session。"""

    id: UUID
    account_id: UUID
    token_digest: str
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class AccountSession:
    """API 可以安全返回的 Account 与新 Session Token。"""

    account: Account
    token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class RegisterAccountCommand:
    """创建本地 Account 所需的最小输入。"""

    email: str
    password: str
    display_name: str


@dataclass(frozen=True, slots=True)
class LoginCommand:
    """创建新 Session 所需的登录输入。"""

    email: str
    password: str


@dataclass(frozen=True, slots=True)
class SetupPortfolioCommand:
    """为已登录 Account 原子创建唯一 Portfolio。"""

    account_id: UUID
    initial_cash: Decimal
    opening_positions: tuple[OpeningPositionInput, ...] = ()


class AuthUnitOfWork(Protocol):
    """Auth Service 所需的最小持久化事务边界。"""

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def get_account_by_email(self, email: str, *, for_update: bool = False) -> Account | None: ...

    def get_account_by_id(
        self, account_id: UUID, *, for_update: bool = False
    ) -> Account | None: ...

    def add_account(self, account: Account) -> None: ...

    def set_account_portfolio(self, account_id: UUID, user_id: UUID) -> None: ...

    def get_auth_session(self, token_digest: str) -> AuthSession | None: ...

    def add_auth_session(self, auth_session: AuthSession) -> None: ...

    def delete_auth_session(self, token_digest: str) -> None: ...

    def add_user(self, user: User) -> None: ...

    def add_opening_positions(self, opening_positions: list[OpeningPosition]) -> None: ...

    def commit(self) -> None: ...


AuthUnitOfWorkFactory = Callable[[], AuthUnitOfWork]


def normalize_email(value: str) -> str:
    """生成稳定的本地 Email 登录标识。"""

    normalized = value.strip().casefold()
    if len(normalized) > 320 or EMAIL_PATTERN.fullmatch(normalized) is None:
        raise InvalidPortfolioValue("email 格式无效")
    return normalized


def normalize_display_name(value: str) -> str:
    """在 Portfolio 尚未创建时先校验 Account Display Name。"""

    normalized = value.strip()
    if not 1 <= len(normalized) <= 200:
        raise InvalidPortfolioValue("display_name 长度必须在 1 到 200 之间")
    return normalized


def validate_password(value: str) -> str:
    """限制密码长度，避免空密码和异常大的哈希输入。"""

    if not PASSWORD_MIN_LENGTH <= len(value) <= PASSWORD_MAX_LENGTH:
        raise InvalidPortfolioValue(
            f"password 长度必须在 {PASSWORD_MIN_LENGTH} 到 {PASSWORD_MAX_LENGTH} 之间"
        )
    return value


def _encode_base64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_base64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(value + padding, altchars=b"-_", validate=True)


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """使用带随机 Salt 的标准库 scrypt 生成自描述 Password Hash。"""

    validated = validate_password(password)
    actual_salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(
        validated.encode("utf-8"),
        salt=actual_salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return "$".join(
        (
            "scrypt",
            str(SCRYPT_N),
            str(SCRYPT_R),
            str(SCRYPT_P),
            _encode_base64(actual_salt),
            _encode_base64(digest),
        )
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    """校验已批准的 scrypt Hash 格式，非法持久化值只返回失败。"""

    try:
        algorithm, n_text, r_text, p_text, salt_text, digest_text = encoded_hash.split("$")
        if (
            algorithm != "scrypt"
            or int(n_text) != SCRYPT_N
            or int(r_text) != SCRYPT_R
            or int(p_text) != SCRYPT_P
        ):
            return False
        salt = _decode_base64(salt_text)
        expected = _decode_base64(digest_text)
        if len(salt) != 16 or len(expected) != SCRYPT_DKLEN:
            return False
        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=SCRYPT_N,
            r=SCRYPT_R,
            p=SCRYPT_P,
            dklen=SCRYPT_DKLEN,
        )
    except (ValueError, TypeError, UnicodeError, binascii.Error):
        return False
    return hmac.compare_digest(candidate, expected)


def digest_session_token(token: str) -> str:
    """把只存在于 Cookie 的 Raw Token 转为数据库可保存的摘要。"""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthService:
    """协调本地 Account、Session 与一次性 Portfolio Setup。"""

    def __init__(
        self,
        unit_of_work_factory: AuthUnitOfWorkFactory,
        *,
        clock: Callable[[], datetime] | None = None,
        session_ttl: timedelta = DEFAULT_SESSION_TTL,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock or (lambda: datetime.now(UTC))
        self._session_ttl = session_ttl
        # 缺失 Email 也执行等价哈希校验，避免明显的登录时序差异。
        self._dummy_password_hash = hash_password("positionpilot-dummy-password")

    def register(self, command: RegisterAccountCommand) -> AccountSession:
        """原子创建 Account 与首个 Session，不提前创建 Portfolio。"""

        email = normalize_email(command.email)
        display_name = normalize_display_name(command.display_name)
        password_hash = hash_password(command.password)
        now = normalize_timestamp(self._clock())
        token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
        account = Account(
            id=uuid4(),
            email=email,
            display_name=display_name,
            password_hash=password_hash,
            portfolio_user_id=None,
            created_at=now,
        )
        auth_session = self._create_session(account.id, token, now)

        with self._unit_of_work_factory() as unit_of_work:
            if unit_of_work.get_account_by_email(email) is not None:
                raise EmailAlreadyRegistered()
            unit_of_work.add_account(account)
            unit_of_work.add_auth_session(auth_session)
            unit_of_work.commit()
        return AccountSession(account=account, token=token, expires_at=auth_session.expires_at)

    def login(
        self,
        command: LoginCommand,
        *,
        current_session_token: str | None = None,
    ) -> AccountSession:
        """验证凭证，并在同一事务中轮换当前 Browser Session。"""

        email = normalize_email(command.email)
        try:
            password = validate_password(command.password)
            password_shape_is_valid = True
        except InvalidPortfolioValue:
            # 非法长度仍执行一次固定大小校验，再统一返回 Credential Failure。
            password = "positionpilot-invalid-password"
            password_shape_is_valid = False
        now = normalize_timestamp(self._clock())
        with self._unit_of_work_factory() as unit_of_work:
            account = unit_of_work.get_account_by_email(email)
            encoded_hash = (
                account.password_hash if account is not None else self._dummy_password_hash
            )
            if (
                not verify_password(password, encoded_hash)
                or account is None
                or not password_shape_is_valid
            ):
                raise InvalidCredentials()
            token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
            auth_session = self._create_session(account.id, token, now)
            if current_session_token:
                unit_of_work.delete_auth_session(digest_session_token(current_session_token))
            unit_of_work.add_auth_session(auth_session)
            unit_of_work.commit()
        return AccountSession(account=account, token=token, expires_at=auth_session.expires_at)

    def authenticate(self, token: str | None) -> Account:
        """解析 Cookie Session，并拒绝缺失、篡改或过期 Token。"""

        if not token:
            raise AuthenticationRequired()
        token_digest = digest_session_token(token)
        now = normalize_timestamp(self._clock())
        with self._unit_of_work_factory() as unit_of_work:
            auth_session = unit_of_work.get_auth_session(token_digest)
            if auth_session is None:
                raise AuthenticationRequired()
            if auth_session.expires_at <= now:
                unit_of_work.delete_auth_session(token_digest)
                unit_of_work.commit()
                raise AuthenticationRequired()
            account = unit_of_work.get_account_by_id(auth_session.account_id)
            if account is None:
                raise AuthenticationRequired()
            return account

    def logout(self, token: str | None) -> None:
        """幂等删除当前 Session；缺失 Cookie 不构成错误。"""

        if not token:
            return
        with self._unit_of_work_factory() as unit_of_work:
            unit_of_work.delete_auth_session(digest_session_token(token))
            unit_of_work.commit()

    def setup_portfolio(self, command: SetupPortfolioCommand) -> User:
        """原子创建 User、可选 Opening State 并绑定当前 Account。"""

        if len(command.opening_positions) > 100:
            raise InvalidPortfolioValue("opening_positions 最多支持 100 行")

        now = normalize_timestamp(self._clock())
        with self._unit_of_work_factory() as unit_of_work:
            account = unit_of_work.get_account_by_id(command.account_id, for_update=True)
            if account is None:
                raise AuthenticationRequired()
            if account.portfolio_user_id is not None:
                raise PortfolioAlreadyExists()

            user = User.create(
                display_name=account.display_name,
                initial_cash=command.initial_cash,
                created_at=now,
            )
            opening_positions = [
                OpeningPosition.create(
                    user_id=user.id,
                    ticker=item.ticker,
                    shares=item.shares,
                    average_cost=item.average_cost,
                    position_type=item.position_type,
                    recorded_at=now,
                )
                for item in command.opening_positions
            ]
            keys = {(position.ticker, position.position_type) for position in opening_positions}
            if len(keys) != len(opening_positions):
                raise InvalidPortfolioValue(
                    "opening_positions 不能包含重复的 ticker 与 position_type"
                )
            rebuild_portfolio(user, [], [], opening_positions)
            ordered = sorted(
                opening_positions,
                key=lambda position: (position.ticker, position.position_type.value),
            )
            unit_of_work.add_user(user)
            if ordered:
                unit_of_work.add_opening_positions(ordered)
            unit_of_work.set_account_portfolio(account.id, user.id)
            unit_of_work.commit()
            return user

    def _create_session(self, account_id: UUID, token: str, now: datetime) -> AuthSession:
        return AuthSession(
            id=uuid4(),
            account_id=account_id,
            token_digest=digest_session_token(token),
            created_at=now,
            expires_at=now + self._session_ttl,
        )
