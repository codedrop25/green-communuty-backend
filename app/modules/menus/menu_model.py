"""Menu ORM 모델."""

from sqlalchemy import Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import SoftDeleteMixin, TimestampMixin


class Menu(Base, TimestampMixin, SoftDeleteMixin):
    """게시판 카테고리. 부모 번호로 트리를 만든다."""

    # 테이블 이름
    __tablename__ = "menus"

    __table_args__ = (
        # 같은 부모 아래 같은 이름 금지.
        # deleted_at 을 넣은 이유: soft delete 로 지운 행이 남아 있어서,
        # 빼면 지웠던 이름을 다시 만들 수 없다.
        UniqueConstraint(
            "menu_parent_id",
            "menu_name",
            "deleted_at",
            name="uq_menus_parent_name",
        ),
        # 모든 조회가 deleted_at IS NULL 조건을 쓰므로 인덱스를 건다.
        Index("ix_menus_deleted_at", "deleted_at"),
    )

    # 메뉴 고유 번호
    menu_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    # 메뉴 이름
    menu_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # 부모 메뉴 번호
    # 최상위 메뉴는 부모가 없어서 NULL
    # FK 는 팀 규칙상 걸지 않으므로 부모 존재 확인은 Service 에서 한다
    menu_parent_id: Mapped[int | None] = mapped_column(
        nullable=True,
        index=True,
    )

    # 메뉴 객체 확인용
    def __repr__(self) -> str:
        return f"<Menu menu_id={self.menu_id} menu_name={self.menu_name!r}>"
