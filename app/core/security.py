"""비밀번호 해싱과 JWT 발급/검증.

라이브러리 선택 근거 (PLAN.md 2-1):
    - `passlib` 대신 `bcrypt` 직접 사용.
      passlib 1.7.4(2020) 는 유지보수가 멈췄고 bcrypt 4.1+ 와 조합 시 오류를 낸다.
    - `python-jose` 대신 `PyJWT`.
      python-jose 는 미패치 CVE(알고리즘 혼동, JWE 디컴프레션 폭탄)를 안고 방치되어 있다.
"""

import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import bcrypt
import jwt

from app.core.config import settings
from app.core.exceptions import UnauthorizedError

# bcrypt 는 입력의 72바이트 초과분을 조용히 버린다.
# 길이 검증은 스키마(Pydantic)에서 하고, 여기서는 방어적으로 한 번 더 막는다.
BCRYPT_MAX_PASSWORD_BYTES = 72


class TokenType(StrEnum):
    """토큰 용도.

    payload 의 `type` 으로 넣어 검증 시 대조한다.
    이것이 없으면 Access Token 을 Refresh 엔드포인트에 제출하는 식의
    토큰 용도 혼동 공격이 가능해진다.
    """

    ACCESS = "access"
    REFRESH = "refresh"


@dataclass(frozen=True)
class TokenPayload:
    """검증을 통과한 토큰의 내용."""

    user_id: int
    token_type: TokenType
    jti: str
    expires_at: datetime


# --------------------------------------------------------------------- 비밀번호


def hash_password(password: str) -> str:
    """비밀번호를 bcrypt 해시로 변환한다."""
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(
            f"비밀번호는 UTF-8 기준 {BCRYPT_MAX_PASSWORD_BYTES}바이트를 넘을 수 없습니다."
        )
    return str(bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8"))


def verify_password(password: str, password_hash: str) -> bool:
    """비밀번호와 저장된 해시를 대조한다.

    `checkpw` 는 상수 시간 비교를 사용하므로 타이밍 공격에 안전하다.
    저장된 해시가 손상된 경우 예외가 나는데, 이를 그대로 500 으로 흘리면
    "해시가 깨진 계정"과 "비밀번호 틀림"을 공격자가 구분할 수 있으므로 False 로 수렴시킨다.
    """
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > BCRYPT_MAX_PASSWORD_BYTES:
        return False
    try:
        return bool(bcrypt.checkpw(password_bytes, password_hash.encode("utf-8")))
    except ValueError:
        return False


# --------------------------------------------------------------------- JWT


def _create_token(
    user_id: int,
    token_type: TokenType,
    expires_delta: timedelta,
) -> tuple[str, str, datetime]:
    """토큰을 발급하고 (토큰, jti, 만료시각) 을 돌려준다.

    `jti` 는 토큰 하나하나를 식별하는 고유 ID 다.
    Refresh Token 회전/폐기를 이 값 기준으로 처리한다 (PLAN.md 4-1).
    """
    now = datetime.now(UTC)
    expires_at = now + expires_delta
    jti = uuid.uuid4().hex

    payload: dict[str, Any] = {
        "sub": str(user_id),  # JWT 표준상 sub 는 문자열이어야 한다.
        "type": token_type.value,
        "jti": jti,
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(
        payload,
        settings.SECRET_KEY.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )
    return token, jti, expires_at


def create_access_token(user_id: int) -> str:
    token, _, _ = _create_token(
        user_id,
        TokenType.ACCESS,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return token


def create_refresh_token(user_id: int) -> tuple[str, str]:
    """Refresh Token 을 발급하고 (토큰, jti) 를 돌려준다.

    호출자는 `jti` 로 Redis 에 저장/회전 처리를 한다.
    """
    token, jti, _ = _create_token(
        user_id,
        TokenType.REFRESH,
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return token, jti


def decode_token(token: str, expected_type: TokenType) -> TokenPayload:
    """토큰을 검증하고 payload 를 돌려준다.

    실패는 모두 `UnauthorizedError` 로 수렴시킨다.
    "만료됨" 과 "서명 위조" 를 구분해 알려주면 공격자에게 정보를 주게 되므로,
    상세 원인은 로그에만 남기고 클라이언트에는 동일한 응답을 준다.
    """
    try:
        claims = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            # 알고리즘을 명시하지 않으면 토큰의 alg 헤더를 신뢰하게 되어
            # 알고리즘 혼동 공격에 노출된다. 반드시 화이트리스트로 지정한다.
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "sub", "jti", "type"]},
        )
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("유효하지 않은 토큰입니다.") from exc

    if claims.get("type") != expected_type.value:
        # 예: Access Token 을 토큰 재발급에 사용하려는 시도.
        raise UnauthorizedError("유효하지 않은 토큰입니다.")

    try:
        user_id = int(claims["sub"])
    except (TypeError, ValueError) as exc:
        raise UnauthorizedError("유효하지 않은 토큰입니다.") from exc

    return TokenPayload(
        user_id=user_id,
        token_type=expected_type,
        jti=str(claims["jti"]),
        expires_at=datetime.fromtimestamp(claims["exp"], tz=UTC),
    )


# --------------------------------------------------------------------- 토큰 해시


def hash_token(token: str) -> str:
    """Refresh Token 을 Redis 에 저장하기 위한 SHA-256 해시.

    원문을 저장하지 않는 이유: Redis 가 유출되어도 토큰 자체는 노출되지 않게 하기 위함이다.
    비밀번호와 달리 bcrypt 를 쓰지 않는 것은, 토큰이 이미 충분한 엔트로피를 가진
    무작위 값이라 사전 공격 대상이 아니고, 매 요청마다 검증되므로 속도가 중요하기 때문이다.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token_hash(token: str, stored_hash: str) -> bool:
    """토큰 해시를 상수 시간으로 비교한다.

    `==` 로 비교하면 일치하는 접두사 길이에 따라 소요 시간이 달라져
    해시를 한 바이트씩 알아낼 수 있다.
    """
    return hmac.compare_digest(hash_token(token), stored_hash)
