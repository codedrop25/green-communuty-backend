"""PostImage ORM 모델."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import TimestampMixin


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

    image_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
