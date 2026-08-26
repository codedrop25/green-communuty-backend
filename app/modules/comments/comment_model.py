"""Comment ORM 모델."""

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import SoftDeleteMixin, TimestampMixin


class Comment(Base, TimestampMixin, SoftDeleteMixin):
    """게시글 댓글."""

    # DB 테이블명
    __tablename__ = "comments"

    # 댓글 고유 번호
    comment_id: Mapped[int] = mapped_column(
        # 기본키(PK)
        primary_key=True,
        # 번호 자동 증가
        autoincrement=True,
    )

    # 댓글 내용
    comment_content: Mapped[str] = mapped_column(
        # 긴 문자열 저장
        Text,
        # 필수값
        nullable=False,
    )

    # 댓글이 작성된 게시글 번호
    post_id: Mapped[int] = mapped_column(
        # 게시글 번호 필수
        nullable=False,
        # 게시글 번호로 조회할 때 사용
        index=True,
    )

    # 댓글 작성자 번호
    author_id: Mapped[int] = mapped_column(
        # 작성자 번호 필수
        nullable=False,
        # 작성자 번호로 조회할 때 사용
        index=True,
    )

    # 부모 댓글 번호
    # 일반 댓글은 NULL, 답글이면 부모 댓글 번호 저장
    parent_comment_id: Mapped[int | None] = mapped_column(
        # 일반 댓글은 부모 댓글이 없어서 NULL 허용
        nullable=True,
        # 부모 댓글 번호로 답글 조회할 때 사용
        index=True,
    )

    # 댓글 객체 확인용
    def __repr__(self) -> str:
        return f"<Comment comment_id={self.comment_id} post_id={self.post_id}>"
