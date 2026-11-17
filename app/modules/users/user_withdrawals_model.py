"""UserWithdrawal ORM 모델."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import TimestampMixin
from app.modules.users.user_model import UserRole


class WithdrawalType(StrEnum):
    NORMAL = "NORMAL"
    BANNED = "BANNED"


class UserWithdrawal(Base, TimestampMixin):
    """회원 탈퇴 기록 테이블.
    1. 회원 탈퇴시 -> user.user_is_active 상태값 변경 후 탈퇴 테이블로 이동.
    2. users 테이블의 이메일, 닉네임, 비밀번호 값은 null 로 변경.
    3. 일반 탈퇴 회원 데이터는 5년간 보관 후 폐기."""

    __tablename__ = "user_withdrawals"

    user_withdrawal_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="탈퇴 회원 식별자(PK)"
    )

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.user_id"), nullable=False, comment="회원 식별자(FK)"
    )

    user_withdrawal_email: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="탈퇴 회원 이메일"
    )
    user_withdrawal_nickname: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="탈퇴 당시의 회원 닉네임"
    )

    user_role: Mapped[UserRole] = mapped_column(
        # native_enum=False 로 VARCHAR(20) 에 저장한다.
        # MySQL 네이티브 ENUM 은 값을 추가/변경할 때마다 테이블을 재작성해야 하기 때문이다.
        # 값의 유효성은 SQLAlchemy 의 Enum 타입이 읽기/쓰기 경계에서 검증한다
        # (DB CHECK 제약은 걸지 않는다 — 역할 추가마다 마이그레이션이 필요해지므로).
        Enum(UserRole, native_enum=False, length=20, validate_strings=True),
        nullable=False,
        default=UserRole.USER,
        server_default=UserRole.USER.value,
        comment="탈퇴 당시 회원 권한",
    )

    user_withdrawal_type: Mapped[WithdrawalType] = mapped_column(
        Enum(
            WithdrawalType,
            native_enum=False,
            length=20,
            validate_strings=True,
        ),
        nullable=False,
        default=WithdrawalType.NORMAL,
        comment="탈퇴 유형(NORMAL/BANNED)",
    )

    user_withdrawal_reason: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="탈퇴 사유"
    )

    retention_until: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="데이터 보관 만료 일시(UTC)"
    )

    rejoin_blocked_until: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="영구 재가입 제한 여부."
    )
