"""Comment ORM 모델."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.modules.posts.model import Post
    from app.modules.users.model import User


class Comment(Base, TimestampMixin, SoftDeleteMixin):
    """게시글 댓글 (Post 와 1:N)."""

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    content: Mapped[str] = mapped_column(Text, nullable=False)

    post_id: Mapped[int] = mapped_column(
        # 게시글이 물리 삭제되면 댓글도 함께 사라져야 고아 행이 남지 않는다.
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    # PLAN.md 3-5: 지연 로딩 금지. 필요한 곳에서 명시적으로 eager loading 한다.
    post: Mapped["Post"] = relationship(back_populates="comments", lazy="raise")
    author: Mapped["User"] = relationship(lazy="raise")

    def __repr__(self) -> str:
        return f"<Comment id={self.id} post_id={self.post_id}>"
