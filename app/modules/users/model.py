"""User ORM 모델."""

from enum import StrEnum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import TimestampMixin


class UserRole(StrEnum):
    """역할 기반 인가의 단위 (PLAN.md 3-7)."""

    USER = "USER"
    ADMIN = "ADMIN"


class User(Base, TimestampMixin):
    """서비스 사용자.

    PLAN.md 6-3: User 는 물리/논리 삭제 대신 `is_active=False` 로 비활성화한다.
    작성한 게시글의 작성자 표기와 FK 무결성을 유지해야 하기 때문이다.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        comment="로그인 ID 로 사용하는 이메일",
    )
    # 해시만 저장한다. 컬럼명에 `hash` 를 넣어 원문 저장을 코드 리뷰에서 바로 잡을 수 있게 한다.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    nickname: Mapped[str] = mapped_column(String(50), nullable=False, comment="표시 이름")

    role: Mapped[UserRole] = mapped_column(
        # native_enum=False 로 VARCHAR(20) 에 저장한다.
        # MySQL 네이티브 ENUM 은 값을 추가/변경할 때마다 테이블을 재작성해야 하기 때문이다.
        # 값의 유효성은 SQLAlchemy 의 Enum 타입이 읽기/쓰기 경계에서 검증한다
        # (DB CHECK 제약은 걸지 않는다 — 역할 추가마다 마이그레이션이 필요해지므로).
        SAEnum(UserRole, native_enum=False, length=20, validate_strings=True),
        nullable=False,
        default=UserRole.USER,
        server_default=UserRole.USER.value,
    )

    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        server_default="1",
        comment="False 면 로그인 및 인증이 거부된다",
    )

    def __repr__(self) -> str:
        # 비밀번호 해시가 로그에 섞이지 않도록 식별용 필드만 노출한다.
        return f"<User id={self.id} email={self.email!r}>"
