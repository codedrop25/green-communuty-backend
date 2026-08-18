"""PostLike ORM 모델."""

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import TimestampMixin


class PostLike(Base, TimestampMixin):
    __tablename__ = "posts_like"

    __table_args__ = (
        UniqueConstraint(
            "post_id",
            "user_id",
            name="uq_posts_like_post_id_user_id",
        ),
    )

    like_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    post_id: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )
