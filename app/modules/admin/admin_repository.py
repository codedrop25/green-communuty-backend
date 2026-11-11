"""관리자 페이지 레포지토리 영역."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.users.user_model import User


class AdminRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_users(
        self,
        page: int = 1,
        size: int = 20,
        keyword: str | None = None,  # 회원 검색용
    ) -> list[User]:
        """전체 회원 목록을 페이지별로 조회."""

        offset = (page - 1) * size

        statement = select(User)

        if keyword:
            statement = statement.where(
                # .contains(): SQL 의 LIKE 연산 사용.
                User.user_nickname.contains(keyword)
            )

        statement = statement.order_by(User.user_id.desc()).offset(offset).limit(size)
        return list(self._db.scalars(statement).all())

    def count_users(self, keyword: str | None = None) -> int:
        """검색 조건에 해당하는, 전체 회원 수 조회."""

        statement = select(func.count()).select_from(User)

        if keyword:
            statement = statement.where(User.user_nickname.contains(keyword))

        return self._db.scalar(statement) or 0
