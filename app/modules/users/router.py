"""User 엔드포인트.

Router 규칙 (PLAN.md 3-1): 요청/응답과 DTO 검증만 담당하고 비즈니스 로직은 두지 않는다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.common.dependencies import CurrentUser, DbSession, require_role
from app.common.pagination import PageParams, PageResponse
from app.modules.users.model import UserRole
from app.modules.users.schemas import UserResponse, UserUpdate
from app.modules.users.service import UserService

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


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="회원 탈퇴 (계정 비활성화)",
)
def deactivate_me(current_user: CurrentUser, db: DbSession) -> None:
    UserService(db).deactivate(current_user)


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
