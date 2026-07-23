"""User 비즈니스 로직.

트랜잭션 경계 (PLAN.md 3-4):
    쓰기 작업은 이 계층에서 `commit()` 한다.
    `get_db` 의존성이 아니라 여기서 commit 해야, 실패가 응답 전송 **전에** 드러나
    전역 예외 핸들러가 정상적으로 오류 응답을 만들 수 있다.
"""

from sqlalchemy.orm import Session

from app.common.pagination import PageParams
from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.modules.users.model import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate, UserUpdate


class UserService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repository = UserRepository(db)

    # ------------------------------------------------------------------ 조회

    def get(self, user_id: int) -> User:
        user = self._repository.get_by_id(user_id)
        if user is None:
            raise NotFoundError("사용자를 찾을 수 없습니다.")
        return user

    def list_users(self, params: PageParams) -> tuple[list[User], int]:
        return self._repository.list_paginated(params)

    # ------------------------------------------------------------------ 생성/수정

    def create(self, payload: UserCreate) -> User:
        """회원가입.

        이메일 중복은 사전 조회로 걸러 사용자에게 친절한 409 를 준다.
        동시 요청으로 사전 조회를 통과하더라도 DB 의 UNIQUE 제약이 최종 방어선이 되며,
        그 경우 IntegrityError 가 전역 핸들러에서 처리된다.
        """
        if self._repository.exists_by_email(payload.email):
            raise ConflictError("이미 사용 중인 이메일입니다.")

        user = User(
            email=payload.email,
            password_hash=hash_password(payload.password),
            nickname=payload.nickname,
        )
        self._repository.add(user)
        self._db.commit()
        return user

    def update(self, user: User, payload: UserUpdate) -> User:
        """프로필 수정.

        `exclude_unset` 으로 "명시적으로 보낸 필드"만 반영한다.
        이것이 없으면 클라이언트가 보내지 않은 필드가 None 으로 덮어써진다.
        """
        changes = payload.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(user, field, value)

        self._repository.flush()
        self._db.commit()
        return user

    def deactivate(self, user: User) -> None:
        """계정 비활성화 (PLAN.md 6-3: User 는 삭제하지 않는다)."""
        user.is_active = False
        self._repository.flush()
        self._db.commit()
