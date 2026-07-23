"""Post ORM 모델."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.modules.comments.model import Comment
    from app.modules.users.model import User


class Post(Base, TimestampMixin, SoftDeleteMixin):
    """게시글."""

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    author_id: Mapped[int] = mapped_column(
        # 유저는 삭제하지 않고 비활성화하므로(PLAN.md 6-3) CASCADE 를 두지 않는다.
        # 작성자 정보는 게시글이 살아 있는 한 유지되어야 한다.
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    # --- 관계 ---
    # lazy="raise" 로 지연 로딩을 금지한다 (PLAN.md 3-5).
    # 명시적으로 eager loading 하지 않은 채 접근하면 조용한 N+1 대신 즉시 예외가 나므로,
    # 실수를 운영이 아니라 개발/테스트 단계에서 발견하게 된다.
    author: Mapped["User"] = relationship(lazy="raise")

    comments: Mapped[list["Comment"]] = relationship(
        back_populates="post",
        lazy="raise",
        # 게시글이 지워지면 댓글도 함께 정리한다 (논리 삭제는 Service 에서 처리).
        cascade="all, delete-orphan",
        order_by="Comment.id",
    )

    def __repr__(self) -> str:
        return f"<Post id={self.id} title={self.title!r}>"
