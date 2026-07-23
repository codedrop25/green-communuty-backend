"""인증/인가 공통 의존성.

**이 파일이 `modules/auth/` 가 아니라 `common/` 에 있는 이유:**
    `users` 라우터는 "현재 로그인한 유저"가 필요하고, `auth` 모듈은 유저를 조회하기 위해
    `users` 를 의존한다. `get_current_user` 를 `auth` 에 두면
    `users -> auth -> users` 순환 import 가 된다.
    두 모듈이 공유하는 자원이므로 PLAN.md 3-1 규칙대로 `common/` 으로 올린다.

인증(누구인가)과 인가(무엇을 할 수 있는가)를 분리해 제공한다 (PLAN.md 3-7).
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import TokenType, decode_token
from app.infrastructure.database.session import get_db
from app.modules.users.model import User, UserRole
from app.modules.users.repository import UserRepository

# auto_error=False 로 두고 직접 예외를 던진다.
# 기본값(True)은 FastAPI 의 HTTPException 을 발생시켜 우리 표준 오류 포맷을 우회한다.
_bearer_scheme = HTTPBearer(auto_error=False, description="Access Token (Bearer)")

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> User:
    """Access Token 을 검증하고 현재 유저를 돌려준다.

    토큰이 유효해도 그 사이 계정이 비활성화되었을 수 있으므로 매 요청 DB 를 확인한다.
    토큰에만 의존하면 차단된 계정이 토큰 만료 시각까지 계속 접근할 수 있다.
    """
    if credentials is None:
        raise UnauthorizedError("인증이 필요합니다.")

    payload = decode_token(credentials.credentials, TokenType.ACCESS)

    user = UserRepository(db).get_by_id(payload.user_id)
    if user is None:
        # 토큰은 유효하지만 유저가 삭제된 경우.
        raise UnauthorizedError("인증이 필요합니다.")
    if not user.is_active:
        raise ForbiddenError("비활성화된 계정입니다.")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: UserRole) -> Callable[[User], User]:
    """지정한 역할 중 하나를 가진 유저만 통과시키는 의존성을 만든다.

    사용 예:
        @router.get("/admin", dependencies=[Depends(require_role(UserRole.ADMIN))])

    라우트 전체를 막는 용도이며, 리소스 소유권 검증(내 글만 수정)은
    데이터를 봐야 판단할 수 있으므로 Service 계층에서 처리한다.
    """

    def dependency(current_user: CurrentUser) -> User:
        if current_user.role not in roles:
            raise ForbiddenError("접근 권한이 없습니다.")
        return current_user

    return dependency
