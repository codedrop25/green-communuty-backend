from pydantic import BaseModel, ConfigDict


class AdminUserResponse(BaseModel):
    """관리자용 회원 조회 응답."""

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
