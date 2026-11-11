"""관리자 페이지의 서비스 영역."""

from sqlalchemy.orm import Session

from app.modules.admin.admin_repository import AdminRepository
from app.modules.users.user_model import User


class AdminService:
    def __init__(self, db: Session) -> None:
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
