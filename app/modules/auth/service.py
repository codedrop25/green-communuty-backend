"""인증 비즈니스 로직.

이 파일의 핵심은 **Refresh Token Rotation + 재사용 탐지** (PLAN.md 4-2) 이다.

회전이 없으면 Refresh Token 이 한 번 탈취됐을 때 만료(수일)까지 공격자가
무한히 Access Token 을 재발급받을 수 있다. 회전을 넣으면 토큰은 1회용이 되고,
"이미 쓴 토큰이 다시 제출됐다"는 사실 자체가 탈취의 증거가 된다.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from redis import Redis
from sqlalchemy.orm import Session

from app.common.rate_limit import RateLimiter
from app.core.config import settings
from app.core.exceptions import RateLimitedError, UnauthorizedError
from app.core.logging_config import get_logger
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token,
    verify_password,
)
from app.modules.auth.token_store import RefreshTokenStore, TokenState
from app.modules.users.user_model import User
from app.modules.users.user_repository import UserRepository
from app.modules.users.user_schemas import UserCreate
from app.modules.users.user_service import UserService

logger = get_logger(__name__)


@dataclass(frozen=True)
class IssuedTokens:
    """발급된 토큰 쌍. Router 가 Refresh Token 을 쿠키로 심는다."""

    access_token: str
    refresh_token: str
    expires_in: int


class AuthService:
    def __init__(self, db: Session, redis: Redis) -> None:
        self._db = db
        self._users = UserRepository(db)
        self._user_service = UserService(db)
        self._token_store = RefreshTokenStore(redis)
        self._rate_limiter = RateLimiter(redis)

    # ------------------------------------------------------------------ 회원가입

    def signup(self, payload: UserCreate) -> User:
        """회원가입. 생성 로직은 UserService 에 위임한다 (중복 구현 방지)."""
        return self._user_service.create(payload)

    # ------------------------------------------------------------------ 로그인

    def login(self, email: str, password: str, client_ip: str) -> IssuedTokens:
        """이메일/비밀번호 인증 후 토큰을 발급한다."""
        self._check_login_rate_limit(email, client_ip)

        user = self._users.get_by_email(email)

        # 사용자 존재 여부에 따라 응답이나 처리 시간이 달라지면
        # 공격자가 가입된 이메일 목록을 수집할 수 있다.
        # 유저가 없어도 해시 검증을 수행해 응답을 동일하게 맞춘다.
        password_ok = verify_password(
            password,
            user.user_password_hash if user is not None else _DUMMY_PASSWORD_HASH,
        )

        if user is None or not password_ok:
            logger.warning("login_failed", email=email, reason="invalid_credentials")
            raise UnauthorizedError("이메일 또는 비밀번호가 올바르지 않습니다.")

        if not user.user_is_active:
            logger.warning("login_failed", user_id=user.user_id, reason="inactive")
            raise UnauthorizedError("이메일 또는 비밀번호가 올바르지 않습니다.")

        # 정상 로그인했으므로 실패 카운터를 비운다.
        # 이것이 없으면 정상 사용자가 오타 몇 번으로 윈도우 내내 잠긴다.
        self._reset_login_rate_limit(email, client_ip)

        logger.info("login_succeeded", user_id=user.user_id)
        return self._issue_tokens(user.user_id)

    def _check_login_rate_limit(self, email: str, client_ip: str) -> None:
        """이메일과 IP 두 축으로 카운트한다.

        이메일만 세면 공격자가 계정을 바꿔가며 우회하고,
        IP 만 세면 분산된 공격이 통과한다.
        """
        for key in self._rate_limit_keys(email, client_ip):
            result = self._rate_limiter.hit(
                key,
                max_attempts=settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS,
                window_seconds=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
            )
            if not result.allowed:
                logger.warning("login_rate_limited", key=key, attempts=result.current)
                raise RateLimitedError(
                    "로그인 시도가 너무 많습니다. 잠시 후 다시 시도해주세요.",
                    retry_after=result.retry_after,
                )

    def _reset_login_rate_limit(self, email: str, client_ip: str) -> None:
        for key in self._rate_limit_keys(email, client_ip):
            self._rate_limiter.reset(key)

    @staticmethod
    def _rate_limit_keys(email: str, client_ip: str) -> tuple[str, str]:
        return f"ratelimit:login:email:{email.lower()}", f"ratelimit:login:ip:{client_ip}"

    # ------------------------------------------------------------------ 토큰 재발급

    def refresh(self, refresh_token: str) -> IssuedTokens:
        """Refresh Token 회전 + 재사용 탐지 (PLAN.md 4-2).

        처리 분기 (`TokenState` 참고):
          - ACTIVE           → 정상. 기존 jti 를 소비 처리하고 새 토큰 쌍 발급
          - REUSED / FORGED  → 탈취 정황. 해당 유저의 **모든** 세션 무효화 후 401
          - UNKNOWN          → 만료/로그아웃. 해당 요청만 401 (다른 세션은 건드리지 않음)

        REUSED 를 UNKNOWN 과 구분하는 것이 중요하다.
        둘을 합치면 정상적으로 로그아웃한 토큰을 다시 제출한 사용자까지
        모든 기기에서 강제 로그아웃당한다.
        """
        payload = decode_token(refresh_token, TokenType.REFRESH)
        state = self._token_store.verify(payload.user_id, payload.jti, refresh_token)

        if state in (TokenState.REUSED, TokenState.FORGED):
            # 누가 진짜 주인인지 알 수 없으므로 전부 끊고 재로그인을 요구한다.
            revoked = self._token_store.revoke_all(payload.user_id)
            logger.warning(
                "refresh_token_compromise_detected",
                user_id=payload.user_id,
                jti=payload.jti,
                state=state.value,
                revoked_sessions=revoked,
            )
            raise UnauthorizedError("세션이 만료되었습니다. 다시 로그인해주세요.")

        if state is TokenState.UNKNOWN:
            logger.info("refresh_token_not_found", user_id=payload.user_id, jti=payload.jti)
            raise UnauthorizedError("세션이 만료되었습니다. 다시 로그인해주세요.")

        user = self._users.get_by_id(payload.user_id)
        if user is None or not user.user_is_active:
            self._token_store.revoke_all(payload.user_id)
            raise UnauthorizedError("세션이 만료되었습니다. 다시 로그인해주세요.")

        # 회전: 새 토큰을 발급하기 전에 사용된 토큰을 소비 처리한다.
        remaining = int((payload.expires_at - datetime.now(UTC)).total_seconds())
        self._token_store.rotate(payload.user_id, payload.jti, remaining)

        logger.info("token_refreshed", user_id=user.user_id)
        return self._issue_tokens(user.user_id)

    # ------------------------------------------------------------------ 로그아웃

    def logout(self, refresh_token: str | None) -> None:
        """현재 기기의 세션만 종료한다.

        토큰이 없거나 이미 무효해도 예외를 던지지 않는다.
        로그아웃은 멱등해야 하며, 실패시켜 봐야 클라이언트가 할 수 있는 일이 없다.
        """
        if not refresh_token:
            return
        try:
            payload = decode_token(refresh_token, TokenType.REFRESH)
        except UnauthorizedError:
            return

        self._token_store.revoke(payload.user_id, payload.jti)
        logger.info("logout", user_id=payload.user_id)

    def logout_all(self, user_id: int) -> int:
        """모든 기기에서 로그아웃한다 (인덱스 Set 기반, KEYS 미사용)."""
        revoked = self._token_store.revoke_all(user_id)
        logger.info("logout_all", user_id=user_id, revoked_sessions=revoked)
        return revoked

    # ------------------------------------------------------------------ 내부

    def _issue_tokens(self, user_id: int) -> IssuedTokens:
        access_token = create_access_token(user_id)
        refresh_token, jti = create_refresh_token(user_id)

        # 원문이 아닌 해시를 저장한다 (Redis 유출 대비).
        self._token_store.save(user_id, jti, hash_token(refresh_token))

        return IssuedTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )


# 존재하지 않는 계정으로 로그인을 시도해도 실제 계정과 동일한 시간이 걸리도록
# 검증에 사용하는 더미 해시. bcrypt 로 미리 계산해 둔 고정값이며 어떤 계정과도 무관하다.
_DUMMY_PASSWORD_HASH = "$2b$12$C6UzMDM.H6dfI/f/IKcEe.6qL8x4rY4rB0LHhCwZgHUqvOeYlqQvi"
