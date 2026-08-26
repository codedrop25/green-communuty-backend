"""Menu DB 조회."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.menus.menu_model import Menu


class MenuRepository:
    def __init__(self, db: Session) -> None:
        # DB 연결
        self._db = db

    # 번호로 메뉴 하나 조회 (없으면 None)
    def get_by_id(self, menu_id: int) -> Menu | None:
        stmt = select(Menu).where(
            Menu.menu_id == menu_id,
            # 지워진 메뉴는 제외
            Menu.deleted_at.is_(None),
        )
        return self._db.execute(stmt).scalar_one_or_none()

    # 살아있는 메뉴 전체 조회
    # 트리 조립은 Service 가 하므로 여기서는 한 번에 다 읽기만 한다
    def list_all(self) -> list[Menu]:
        stmt = (
            select(Menu)
            .where(Menu.deleted_at.is_(None))
            .order_by(Menu.menu_parent_id, Menu.menu_id)
        )
        return list(self._db.execute(stmt).scalars().all())

    # 특정 메뉴의 바로 아래 자식들 조회 (삭제 가능 여부 판단용)
    def list_children(self, menu_parent_id: int | None) -> list[Menu]:
        stmt = select(Menu).where(
            Menu.menu_parent_id == menu_parent_id,
            Menu.deleted_at.is_(None),
        )
        return list(self._db.execute(stmt).scalars().all())

    # 같은 부모 아래 같은 이름의 메뉴 조회 (중복 확인용, 없으면 None)
    def get_by_parent_and_name(
        self,
        menu_parent_id: int | None,
        menu_name: str,
    ) -> Menu | None:
        stmt = select(Menu).where(
            Menu.menu_parent_id == menu_parent_id,
            Menu.menu_name == menu_name,
            Menu.deleted_at.is_(None),
        )
        return self._db.execute(stmt).scalar_one_or_none()

    # 새 메뉴를 세션에 올린다 (확정은 Service 의 commit 이 한다)
    def add(self, menu: Menu) -> Menu:
        self._db.add(menu)
        return menu

    # SQL 을 DB 로 보내되 확정하지 않는다
    # 자동 발급되는 menu_id 를 받아오기 위해 필요
    def flush(self) -> None:
        self._db.flush()
