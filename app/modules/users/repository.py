"""User DB 접근.

Repository 규칙 (PLAN.md 3-4):
    - 쿼리와 `flush()` 까지만 담당한다.
    - `commit()` / `rollback()` 은 호출하지 않는다. 트랜잭션 경계는 Service 의 책임이다.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.pagination import PageParams
from app.modules.users.model import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, user_id: int) -> User | None:
        return self._db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return self._db.scalars(stmt).one_or_none()

    def exists_by_email(self, email: str) -> bool:
        """존재 여부만 필요할 때 행 전체를 가져오지 않는다."""
        stmt = select(func.count()).select_from(User).where(User.email == email)
        return bool(self._db.scalar(stmt))

    def list_paginated(self, params: PageParams) -> tuple[list[User], int]:
        """목록과 전체 건수를 함께 돌려준다.

        `total` 은 페이지네이션 응답에 필요하므로 별도 COUNT 쿼리로 계산한다.
        """
        total = self._db.scalar(select(func.count()).select_from(User)) or 0
        stmt = select(User).order_by(User.id.desc()).offset(params.offset).limit(params.limit)
        return list(self._db.scalars(stmt).all()), total

    def add(self, user: User) -> User:
        """영속화하고 DB 가 채운 값(id, created_at)을 반영한다.

        `flush()` 는 INSERT 를 보내되 트랜잭션은 열어 둔다.
        덕분에 Service 가 이어지는 작업에서 `user.id` 를 쓸 수 있으면서도
        최종 commit 전까지는 롤백 가능한 상태가 유지된다.
        """
        self._db.add(user)
        self._db.flush()
        self._db.refresh(user)
        return user

    def flush(self) -> None:
        """수정된 엔티티의 변경사항을 DB 로 내보낸다 (commit 아님)."""
        self._db.flush()
