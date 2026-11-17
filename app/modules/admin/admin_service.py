"""관리자 페이지의 서비스 영역."""

from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError
from app.modules.admin.admin_repository import AdminRepository
from app.modules.users.user_model import User


# --------------------------------------------------------------- 회원 관리
class AdminService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repository = AdminRepository(db)

    def list_users(
        self,
        page: int = 1,
        size: int = 20,
        keyword: str | None = None,
    ) -> list[User]:
        """관리자용 전체 회원 목록 조회."""

        return self._repository.list_users(page=page, size=size, keyword=keyword)

    def count_users(self, keyword: str | None = None) -> int:
        """검색 조건에 해당하는, 전체 회원 수 조회."""
        return self._repository.count_users(keyword=keyword)

    def get_user(self, user_id: int) -> User:
        """관리자용 회원 상세 조회."""
        return self._get_user_id(user_id)

    def update_user_status(
        self,
        user_id: int,
        user_is_active: bool,
    ) -> User:
        """관리자용 회원 상태(active/inactive) 변경.
        회원 탈퇴용, 소프트 딜리트 역할을 대신한다."""

        user = self._get_user_id(user_id)
        user.user_is_active = user_is_active

        try:
            self._db.commit()
            self._db.refresh(user)

        except Exception as exc:
            self._db.rollback()
            raise AppError("회원 상태 변경 중 오류가 발생했습니다.") from exc

        return user

    # --------------------------------------------------------------- 제재 관리
    def get_sanctions(self, user_id: int) -> None:
        """관리자용 회원 제재이력 조회."""
        pass

    def add_sanction(self, user_id: int) -> None:
        """관리자용 회원 제재 등록."""
        pass

    def revoke_sanction(self, user_sanction_id: int) -> None:
        """관리자용 회원 제재 해제."""
        pass

    # --------------------------------------------------------------- 신고 관리
    def list_reports(self) -> None:
        """관리자용 신고 목록 조회."""
        pass

    def get_report(self, report_id: int) -> None:
        """관리자용 신고 상세 조회."""
        pass

    def resolve_report(self, report_id: int) -> None:
        """관리자용 신고 처리."""
        pass

    # --------------------------------------------------------------- 게시글 관리
    def list_posts(self) -> None:
        """관리자용 게시글 조회(숨김, 삭제까지 조회)."""
        pass

    def update_post(self, post_id: int) -> None:
        """관리자용 게시글 삭제, 복구 관리."""
        pass

    def update_post_category(self, post_id: int) -> None:
        """관리자용 카테고리 변경, 공지 관리."""
        pass

    # --------------------------------------------------------------- 공지 관리
    def list_notices(self) -> None:
        """관리자용 공지 목록 조회."""
        pass

    def add_notice(self) -> None:
        """관리자용 신규 공지 작성."""
        pass

    def update_notice(self, post_id: int) -> None:
        """관리자용 공지 수정, 삭제."""
        pass

    # --------------------------------------------------------------- 로그 관리
    def list_logs(self) -> None:
        """관리자용 로그 관리."""
        pass

    # --------------------------------------------------------------- 내부 메서드
    def _get_user_id(
        self,
        user_id: int,
    ) -> User:
        """회원 조회용 공통 내부 메서드."""

        # DB에서 회원 조회
        user = self._repository.get_user(user_id)

        # 해당 회원이 존재하지 않다면 오류 출력
        if user is None:
            raise NotFoundError("회원을 찾을 수 없습니다.")

        return user
