"""메뉴 DB 조회.

이 파일은 SQL 만 담당한다. 판단이나 검증은 Service 의 몫이다.
commit() 도 하지 않는다(프로젝트 규칙). flush() 까지만 한다.
"""

from __future__ import annotations

# Select 반환 타입 표기용
# func   count() 같은 SQL 함수
# select SELECT 문을 파이썬 문법으로 쓰는 도구
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.modules.menus.menu_model import Menu


class MenuRepository:
    def __init__(self, db: Session) -> None:
        # 세션(DB 연결)을 받아서 들고 있는다.
        self._db = db

    @staticmethod
    def _active() -> Select[tuple[Menu]]:
        """모든 조회의 출발점. 논리 삭제된 행을 걸러낸다.

        필터를 한곳에 모아두면 새 조회를 추가할 때 조건을 빠뜨릴 여지가 줄어든다.
        자동으로 거는 방법도 있지만, 그러면 "왜 이 데이터가 안 나오지" 할 때
        원인을 찾기가 어려워져서 명시적으로 쓴다.
        """
        return select(Menu).where(Menu.deleted_at.is_(None))

    def get_by_id(self, menu_id: int) -> Menu | None:
        """번호로 메뉴 하나를 가져온다. 없으면 None."""
        stmt = self._active().where(Menu.menu_id == menu_id)
        # scalar_one_or_none : 결과가 하나면 그것, 없으면 None
        return self._db.execute(stmt).scalar_one_or_none()

    def list_all(self) -> list[Menu]:
        """살아 있는 메뉴 전체를 가져온다.

        트리는 Service 가 메모리에서 조립한다.
        부모를 따라 재귀적으로 조회하면 깊이만큼 쿼리가 늘어나지만,
        이렇게 하면 쿼리 한 번으로 끝난다.
        """
        stmt = self._active().order_by(Menu.menu_parent_id, Menu.menu_id)
        return list(self._db.execute(stmt).scalars().all())

    def list_children(self, menu_parent_id: int | None) -> list[Menu]:
        """특정 메뉴의 직속 자식들. 삭제 가능 여부 판단에 쓴다."""
        stmt = self._active().where(Menu.menu_parent_id == menu_parent_id)
        return list(self._db.execute(stmt).scalars().all())

    def exists_by_id(self, menu_id: int) -> bool:
        """존재 여부만 확인한다.

        FK 를 걸지 않으므로 부모가 실제로 있는지 코드로 검사해야 한다.
        행 전체를 가져올 필요가 없어서 개수만 센다.
        """
        stmt = (
            select(func.count())
            .select_from(Menu)
            .where(Menu.menu_id == menu_id, Menu.deleted_at.is_(None))
        )
        return bool(self._db.execute(stmt).scalar_one())

    def exists_by_parent_and_name(self, menu_parent_id: int | None, menu_name: str) -> bool:
        """같은 부모 아래 같은 이름이 이미 있는지 확인한다."""
        stmt = (
            select(func.count())
            .select_from(Menu)
            .where(
                Menu.menu_parent_id == menu_parent_id,
                Menu.menu_name == menu_name,
                Menu.deleted_at.is_(None),
            )
        )
        return bool(self._db.execute(stmt).scalar_one())

    def add(self, menu: Menu) -> Menu:
        """새 메뉴를 세션에 올린다. 아직 DB 에 확정되지는 않는다."""
        self._db.add(menu)
        return menu

    def flush(self) -> None:
        """SQL 을 DB 로 보내되 확정하지는 않는다.

        flush  : SQL 은 보내지만 되돌릴 수 있다. 자동 생성된 id 를 받아올 때 필요.
        commit : 확정. 되돌릴 수 없다. Service 에서만 호출한다.
        """
        self._db.flush()
