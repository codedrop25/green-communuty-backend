"""사용자 제재 이력 ORM 모델."""

from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import TimestampMixin


class UserSanction(Base, TimestampMixin):
    """신고 처리 결과로 사용자에게 적용된 제재 이력."""

    __tablename__ = "user_sanctions"

    # 사용자 제재 이력을 구분하는 고유 번호
    user_sanction_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # 제재를 받은 사용자의 ID
    reported_user_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    # 사용자에게 적용된 제재 종류
    user_sanction_type: Mapped[str] = mapped_column(
        Enum(
            "WARNING",  # 경고
            "SUSPENDED",  # 일정 기간 이용 정지
            "BANNED",  # 영구 이용 차단
            name="user_sanction_type",
        ),
        nullable=False,
        index=True,
    )

    # 제재를 적용한 사유
    user_sanction_reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # 제재의 근거가 된 신고 내역 ID
    # 외래키를 사용하지 않으므로 숫자만 저장한다.
    report_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    # 기간 정지가 끝나는 시각
    # 경고와 영구 차단은 종료 시간이 없으므로 None이다.
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
