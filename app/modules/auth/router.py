"""Auth 엔드포인트.

Refresh Token 은 응답 본문이 아닌 **HttpOnly 쿠키**로 주고받는다 (PLAN.md 4-4).
쿠키 `Path` 를 이 라우터로 한정해, 다른 API 요청에는 아예 전송되지 않게 한다.
전송되지 않는 쿠키는 CSRF 의 공격 대상이 될 수 없으므로 노출면이 크게 줄어든다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from redis import Redis

from app.common.dependencies import CurrentUser, DbSession
from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.infrastructure.cache.redis import get_redis
from app.modules.auth.schemas import LoginRequest, MessageResponse, TokenResponse
from app.modules.auth.service import AuthService, IssuedTokens
from app.modules.users.user_schemas import UserCreate, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "refresh_token"

RedisClient = Annotated[Redis, Depends(get_redis)]


def _cookie_path() -> str:
    """Refresh 쿠키가 전송될 경로.

    `/api/v1/auth` 하위(재발급/로그아웃)에만 붙는다.
    """
    return f"{settings.API_V1_PREFIX}/auth"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        # JavaScript 에서 읽을 수 없게 한다. XSS 가 나도 Refresh Token 은 탈취되지 않는다.
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path=_cookie_path(),
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )


def _clear_refresh_cookie(response: Response) -> None:
    # 삭제 시에도 path 가 일치해야 브라우저가 해당 쿠키를 지운다.
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=_cookie_path(),
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )


def _token_response(response: Response, tokens: IssuedTokens) -> TokenResponse:
    _set_refresh_cookie(response, tokens.refresh_token)
    return TokenResponse(access_token=tokens.access_token, expires_in=tokens.expires_in)


def _client_ip(request: Request) -> str:
    """Rate Limit 키에 사용할 클라이언트 IP.

    운영에서 리버스 프록시 뒤에 있다면 `X-Forwarded-For` 를 봐야 한다.
    다만 이 헤더는 클라이언트가 위조할 수 있으므로,
    **신뢰할 수 있는 프록시가 덮어쓰는 구성**에서만 사용해야 한다.
    (uvicorn 의 `--proxy-headers` + `--forwarded-allow-ips` 조합)
    """
    return request.client.host if request.client else "unknown"


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회원가입",
)
def signup(payload: UserCreate, db: DbSession, redis: RedisClient) -> UserResponse:
    user = AuthService(db, redis).signup(payload)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse, summary="로그인")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
    redis: RedisClient,
) -> TokenResponse:
    tokens = AuthService(db, redis).login(
        email=payload.email,
        password=payload.password,
        client_ip=_client_ip(request),
    )
    return _token_response(response, tokens)


@router.post("/refresh", response_model=TokenResponse, summary="토큰 재발급 (회전)")
def refresh(
    request: Request,
    response: Response,
    db: DbSession,
    redis: RedisClient,
) -> TokenResponse:
    """Refresh Token 을 회전시키며 새 Access Token 을 발급한다.

    쿠키가 없으면 401 이다. 이 경우 클라이언트는 재로그인을 유도해야 한다.
    """
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise UnauthorizedError("세션이 만료되었습니다. 다시 로그인해주세요.")

    tokens = AuthService(db, redis).refresh(refresh_token)
    return _token_response(response, tokens)


@router.post("/logout", response_model=MessageResponse, summary="로그아웃 (현재 기기)")
def logout(
    request: Request,
    response: Response,
    db: DbSession,
    redis: RedisClient,
) -> MessageResponse:
    AuthService(db, redis).logout(request.cookies.get(REFRESH_COOKIE_NAME))
    _clear_refresh_cookie(response)
    return MessageResponse(message="로그아웃되었습니다.")


@router.post(
    "/logout-all",
    response_model=MessageResponse,
    summary="모든 기기에서 로그아웃",
)
def logout_all(
    current_user: CurrentUser,
    response: Response,
    db: DbSession,
    redis: RedisClient,
) -> MessageResponse:
    """비밀번호 변경이나 기기 분실 시 사용한다.

    Access Token 은 무상태라 만료 전까지 유효하므로,
    Access Token 수명을 짧게(기본 30분) 유지하는 것이 함께 필요하다.
    """
    revoked = AuthService(db, redis).logout_all(current_user.user_id)
    _clear_refresh_cookie(response)
    return MessageResponse(message=f"{revoked}개의 세션이 종료되었습니다.")
