"""Post ORM 모델."""

# from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

# * SQLAlchemy 에게 이 파일은 ORM 모델이라고 알려주는 코드, SpringBoot 의 @Entity 와 비슷한 역할
from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import SoftDeleteMixin, TimestampMixin


class Post(Base, TimestampMixin, SoftDeleteMixin):
    """게시글."""

    # table 이름
    __tablename__ = "posts"

    # 게시글 번호, 게시글 제목, 게시글 내용
    post_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    post_title: Mapped[str] = mapped_column(String(200), nullable=False)
    post_content: Mapped[str] = mapped_column(Text, nullable=False)

    # * 유저는 삭제하지 않고 비활성화하므로 CASCADE 를 두지 않는다.
    # * 작성자 정보는 게시글이 살아 있는 한 유지되어야 한다.
    author_id: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )

    # 조회수 컬럼
    post_view_count: Mapped[int] = mapped_column(nullable=False, default=0)

    # # 게시글 상태 [active, delete]
    # post_status: Mapped[str] = mapped_column(String(30), nullable=True)

    # * representation, 객체를 개발자가 확인하기 좋은 문자열 형태로 표현하는 특수 메서드
    def __repr__(self) -> str:
        return f"<Post id={self.post_id} title={self.post_title!r}>"
