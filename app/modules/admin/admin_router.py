"""관리자 페이지의 컨트롤러 영역."""

from fastapi import APIRouter, Query

from app.common.dependencies import AdminUser, DbSession
from app.modules.admin.admin_schemas import AdminUserListResponse, AdminUserResponse
from app.modules.admin.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["admin"])


# ge: >=
# le: <=
@router.get("/users", response_model=AdminUserResponse)
def list_users(
    admin: AdminUser,
    db: DbSession,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None),
) -> AdminUserListResponse:
    """관리자용 전체 회원 목록 조회."""

    service = AdminService(db)

    users = service.list_users(page=page, size=size, keyword=keyword)

    total = service.count_users(keyword=keyword)  # 전체 회원 수 조회
    total_pages = (total + size - 1) // size  # 전체 페이지 수 계산

    return AdminUserListResponse(
        items=[AdminUserResponse.model_validate(user) for user in users],
        total=total,
        page=page,
        size=size,
        total_pages=total_pages,
    )
