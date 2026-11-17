"""User 엔드포인트.

Router 규칙 (PLAN.md 3-1): 요청/응답과 DTO 검증만 담당하고 비즈니스 로직은 두지 않는다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.common.dependencies import CurrentUser, DbSession, RedisClient, require_role
from app.common.pagination import PageParams, PageResponse
from app.modules.auth.auth_router import _clear_refresh_cookie
from app.modules.auth.auth_schemas import MessageResponse
from app.modules.auth.auth_service import AuthService
from app.modules.users.user_model import UserRole
from app.modules.users.user_schemas import UserResponse, UserUpdate, UserWithdrawRequest
from app.modules.users.user_service import UserService
from app.modules.users.user_withdrawals_service import UserWithdrawalService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse, summary="내 정보 조회")
def get_me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse, summary="내 정보 수정")
def update_me(
    payload: UserUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> UserResponse:
    user = UserService(db).update(current_user, payload)
    return UserResponse.model_validate(user)


@router.get(
    "",
    response_model=PageResponse[UserResponse],
    summary="유저 목록 조회 (관리자 전용)",
    # 역할 기반 인가 (PLAN.md 3-7). 반환값이 필요 없으므로 route dependency 로 건다.
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
def list_users(
    params: Annotated[PageParams, Depends()],
    db: DbSession,
) -> PageResponse[UserResponse]:
    users, total = UserService(db).list_users(params)
    return PageResponse.create(
        items=[UserResponse.model_validate(user) for user in users],
        total=total,
        params=params,
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="유저 단건 조회",
)
def get_user(user_id: int, db: DbSession) -> UserResponse:
    user = UserService(db).get(user_id)
    return UserResponse.model_validate(user)


@router.patch(
    "/me/withdraw",
    response_model=MessageResponse,
    summary="회원 탈퇴 (계정 비활성화)",
)
def withdraw_me(
    current_user: CurrentUser,
    payload: UserWithdrawRequest,
    response: Response,
    db: DbSession,
    redis: RedisClient,
) -> MessageResponse:
    """일반 회원 탈퇴."""

    # 1. 회원 탈퇴 처리
    UserWithdrawalService(db).withdraw_me(current_user.user_id, payload)

    # 2. 모든 기기의 세션 종료
    AuthService(db, redis).logout_all(current_user.user_id)

    # 3. Refresh Token 쿠키 삭제
    _clear_refresh_cookie(response)

    return MessageResponse(message="로그아웃되었습니다.")
