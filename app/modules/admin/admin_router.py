"""관리자 페이지의 컨트롤러 영역."""

from fastapi import APIRouter, Depends, Query

from app.common.dependencies import DbSession, get_admin_user
from app.modules.admin.admin_schemas import (
    AdminUserDetailResponse,
    AdminUserListResponse,
    AdminUserResponse,
    AdminUserStatusRequest,
)
from app.modules.admin.admin_service import AdminService

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_admin_user)],
)


# --------------------------------------------------------------- 회원 관리
# ge: >= / le: <=
# admin: AdminUser 를 사용하지 않음에도 계속 넣는 이유는?
#        관리자 권한을 검사하기 위해 넣은 의존성으로
#        FastAPI 가 요청을 처리하기 전에 자동으로 실행.
#        -> router 에서 의존성 추가로 빼서 지금은 생략 가능.
@router.get("/users", response_model=AdminUserListResponse)
def list_users(
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


# 구현 완료.


@router.get("/users/{user_id}", response_model=AdminUserDetailResponse)
def get_user(user_id: int, db: DbSession) -> AdminUserDetailResponse:
    """관리자용 회원 상세 조회."""

    service = AdminService(db)
    user = service.get_user(user_id)

    return AdminUserDetailResponse.model_validate(user)


@router.patch("/users/{user_id}/update", response_model=AdminUserDetailResponse)
def update_user_status(
    user_id: int,
    data: AdminUserStatusRequest,
    db: DbSession,
) -> AdminUserDetailResponse:
    """관리자용 회원 상태(active/inactive) 변경.
    회원 탈퇴용, 소프트 딜리트 역할을 대신한다."""

    service = AdminService(db)
    user = service.update_user_status(user_id, data.user_is_active)

    return AdminUserDetailResponse.model_validate(user)


# --------------------------------------------------------------- 제재 관리
@router.get("/sanctions/{user_id}")
def get_sanctions(
    user_id: int,
    db: DbSession,
) -> None:
    """관리자용 회원 제재이력 조회."""
    pass


@router.post("/sanctions/{user_id}")
def add_sanction(
    user_id: int,
    db: DbSession,
) -> None:
    """관리자용 회원 제재 등록."""
    pass


@router.patch("/sanctions/{user_sanction_id}/revoke")
def revoke_sanction(
    user_sanction_id: int,
    db: DbSession,
) -> None:
    """관리자용 회원 제재 해제."""
    pass


# --------------------------------------------------------------- 신고 관리
@router.get("/reports")
def list_reports(
    db: DbSession,
) -> None:
    """관리자용 신고 목록 조회."""
    pass


@router.get("/reports/{report_id}")
def get_report(
    report_id: int,
    db: DbSession,
) -> None:
    """관리자용 신고 상세 조회."""
    pass


@router.patch("/reports/{report_id}/resolve")
def resolve_report(
    report_id: int,
    db: DbSession,
) -> None:
    """관리자용 신고 처리."""
    pass


# --------------------------------------------------------------- 게시글 관리
@router.get("/posts")
def list_posts(
    db: DbSession,
) -> None:
    """관리자용 게시글 조회(숨김, 삭제까지 조회)."""
    pass


@router.patch("/posts/{post_id}")
def update_post(
    post_id: int,
    db: DbSession,
) -> None:
    """관리자용 게시글 삭제, 복구 관리."""
    pass


@router.patch("/posts/{post_id}/category")
def update_post_category(
    post_id: int,
    db: DbSession,
) -> None:
    """관리자용 카테고리 변경, 공지 관리."""
    pass


# --------------------------------------------------------------- 공지 관리
@router.get("/notices")
def list_notices(
    db: DbSession,
) -> None:
    """관리자용 공지 목록 조회."""
    pass


@router.post("/notices")
def add_notice(
    db: DbSession,
) -> None:
    """관리자용 신규 공지 작성."""
    pass


@router.patch("/notices/{post_id}")
def update_notice(
    post_id: int,
    db: DbSession,
) -> None:
    """관리자용 공지 수정, 삭제."""
    pass


# --------------------------------------------------------------- 로그 관리
@router.get("/logs")
def list_logs(
    db: DbSession,
) -> None:
    """관리자용 로그 관리."""
    pass
