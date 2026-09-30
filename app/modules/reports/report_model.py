"""게시글 및 댓글 신고 ORM 모델."""

from datetime import datetime

from sqlalchemy import DateTime, Enum, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import TimestampMixin


class Report(Base, TimestampMixin):
    """사용자가 게시글 또는 댓글을 신고한 내역."""

    # 테이블 이름
    __tablename__ = "reports"

    # 인덱스 설정
    __table_args__ = (
        Index(
            "ix_reports_status_created_at",
            "report_status",
            "created_at",
        ),
    )

    # 신고 내역을 구분하는 고유 번호
    report_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # 신고한 사용자의 ID / 관리자가 직접 조치를 취하는 경우 NULL 일 수 있음
    reporter_user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    # 신고 대상의 종류
    report_content_type: Mapped[str] = mapped_column(
        Enum(
            "POST",  # 게시글 신고
            "COMMENT",  # 댓글 또는 대댓글 신고
            "USER",  # 사용자 자체 신고 또는 관리자 직접 제재
            name="report_content_type",
        ),
        nullable=False,
        index=True,
    )

    # 신고당한 게시글의 ID / 사용자 자체를 신고한 경우 None 일 수 있음
    # 댓글 신고일 때도 댓글이 속한 게시글 ID를 함께 저장한다.
    post_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    post_title: Mapped[str | None] = mapped_column(String(200), nullable=False)
    post_content: Mapped[str | None] = mapped_column(Text, nullable=False)

    # 신고당한 댓글 또는 대댓글의 ID
    # 게시글/사용자 신고의 경우에는 값이 없으므로 None을 허용한다.
    comment_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    comment_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=False,
    )

    # 신고당한 게시글 또는 댓글 작성자의 사용자 ID
    reported_user_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    # 신고 사유의 분류
    # 예: SPAM, ABUSE, HATE, ILLEGAL, OTHER
    report_category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # 신고자가 직접 작성하는 상세 설명
    report_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # 신고 처리 상태
    report_status: Mapped[str] = mapped_column(
        Enum(
            "PENDING",  # 관리자 확인 전
            "ACCEPTED",  # 신고 승인 및 조치 완료
            "REJECTED",  # 신고 반려
            name="report_status",
        ),
        nullable=False,
        default="PENDING",
        server_default="PENDING",
        index=True,
    )

    # 신고 처리 결과로 사용자에게 적용한 제재
    # 처리 전이거나 신고가 반려된 경우에는 None이다.
    user_sanction_type: Mapped[str | None] = mapped_column(
        Enum(
            "WARNING",  # 경고
            "SUSPENDED",  # 서비스 이용 일정 기간동안 불가
            "BANNED",  # 서비스 이용 영구 차단
            name="user_sanction_type",
        ),
        nullable=True,
        index=True,
    )

    # 신고를 처리한 관리자의 사용자 ID
    # 아직 처리되지 않았다면 None이다.
    reviewer_user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    # 관리자가 신고 처리를 완료한 시각
    # 신고 접수 시에는 아직 처리되지 않았으므로 None이다.
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
