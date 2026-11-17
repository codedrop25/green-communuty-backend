from pydantic import BaseModel, ConfigDict, EmailStr

from app.modules.users.user_model import UserRole


class AdminUserResponse(BaseModel):
    """관리자용 회원 조회 응답."""

    # SQLAlchemy 의 User 객체를 Pydantic 응답 모델로 변환한다.
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    user_email: str


# 회원 한 명의 응답 구조와, 회원 목록의 응답구조를 분리.
class AdminUserListResponse(BaseModel):
    """관리자용 회원 목록 응답."""

    items: list[AdminUserResponse]
    total: int
    page: int
    size: int
    total_pages: int


class AdminUserDetailResponse(BaseModel):
    """관리자용 회원 단일 조회 응답."""

    # SQLAlchemy 의 User 객체를 Pydantic 응답 모델로 변환한다.
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    user_email: EmailStr
    user_nickname: str
    user_role: UserRole
    user_is_active: bool


class AdminUserStatusRequest(BaseModel):
    """회원 상태 수정용 요청."""

    user_is_active: bool
