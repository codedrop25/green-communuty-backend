"""PostImage ORM 모델."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import TimestampMixin


# 9.03) 수정: image_path 경로를 용도에 따라 3개로 변경
class PostImage(Base, TimestampMixin):
    __tablename__ = "posts_image"

    image_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    post_id: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )

    # 원본 이미지의 R2 객체 키
    image_original_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    # 게시글 본문에 들어갈 이미지의 R2 객체 키
    image_content_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    # 게시글 목록, 썸네일용 이미지 R2 객체 키
    image_thumbnail_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
