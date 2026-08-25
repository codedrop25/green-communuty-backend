"""메뉴 비즈니스 로직.

판단과 검증은 전부 이 파일에서 한다.
Router 에 검증을 두면 다른 경로로 호출될 때 통째로 우회되기 때문에,
데이터를 바꾸는 모든 길목인 Service 에 모아둔다.

commit() 도 이 파일에서만 호출한다(프로젝트 규칙).
"""

from __future__ import annotations

# UTC, datetime : 삭제 시각을 기록할 때 쓴다.
#                 서버마다 시간대가 다르면 값이 뒤섞이므로 UTC 로 고정한다.
from datetime import UTC, datetime

from sqlalchemy.orm import Session

# 우리 프로젝트 전용 예외들.
# HTTPException 을 직접 던지지 않는 이유: 비즈니스 로직이 HTTP 를 몰라야
# 나중에 배치 작업 등 HTTP 가 아닌 곳에서도 그대로 쓸 수 있다.
#   BadRequestError → 400  요청 자체가 말이 안 됨
#   ConflictError   → 409  중복
#   NotFoundError   → 404  없음
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.modules.menus.menu_model import Menu
from app.modules.menus.menu_repository import MenuRepository
from app.modules.menus.menu_schemas import MenuCreate, MenuTreeResponse, MenuUpdate


class MenuService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repository = MenuRepository(db)

    # ------------------------------------------------------------------
    # 검증 함수들. 앞에 _ 가 붙은 것은 이 클래스 안에서만 쓴다는 표시다.
    # ------------------------------------------------------------------

    def _get_or_404(self, menu_id: int) -> Menu:
        """메뉴를 가져오되, 없으면 404 로 끝낸다."""
        menu = self._repository.get_by_id(menu_id)
        if menu is None:
            raise NotFoundError("메뉴를 찾을 수 없습니다.")
        return menu

    def _ensure_parent_exists(self, menu_parent_id: int | None) -> None:
        """부모로 지정한 메뉴가 실제로 있는지 확인한다.

        FK 를 걸지 않기로 했으므로 존재하지 않는 번호를 넣어도 DB 는 통과시킨다.
        방치하면 어느 트리에도 속하지 않는 메뉴가 생긴다.
        """
        # None 이면 최상위 메뉴라는 뜻이므로 검사할 부모가 없다.
        if menu_parent_id is None:
            return
        if not self._repository.exists_by_id(menu_parent_id):
            raise NotFoundError("부모 메뉴를 찾을 수 없습니다.")

    def _ensure_name_available(self, menu_parent_id: int | None, menu_name: str) -> None:
        """같은 부모 아래 같은 이름이 이미 있는지 확인한다.

        DB 의 유니크 제약이 최종 방어선이지만 그것만 두면 사용자는 500 을 받는다.
        여기서 미리 걸러 409(중복)로 알려주기 위한 것이다.
        """
        if self._repository.exists_by_parent_and_name(menu_parent_id, menu_name):
            raise ConflictError("같은 위치에 동일한 이름의 메뉴가 이미 있습니다.")

    def _ensure_not_own_descendant(self, menu_id: int, new_parent_id: int) -> None:
        """메뉴를 자기 자신이나 자기 하위로 옮기는 것을 막는다.

        예) '개발' 을 그 아래에 있는 '파이썬' 의 자식으로 옮기면
            둘이 서로를 부모로 가리키게 되어 고리가 생긴다.
            그 상태로 트리를 조립하면 무한 루프에 빠진다.
        """
        if menu_id == new_parent_id:
            raise BadRequestError("자기 자신을 부모로 지정할 수 없습니다.")

        # 새 부모에서 출발해 위로 계속 거슬러 올라간다.
        # 올라가는 길에 자기 자신이 나오면 = 자기 하위로 들어가려는 것.
        cursor: int | None = new_parent_id
        while cursor is not None:
            if cursor == menu_id:
                raise BadRequestError("하위 메뉴를 부모로 지정할 수 없습니다.")
            parent = self._repository.get_by_id(cursor)
            if parent is None:
                # 위로 가다가 끊기면 고리가 아니다.
                return
            cursor = parent.menu_parent_id  # 한 칸 위로

    # ------------------------------------------------------------------
    # 조회
    # ------------------------------------------------------------------

    def get_tree(self) -> list[MenuTreeResponse]:
        """전체 메뉴를 트리 형태로 조립해서 돌려준다."""
        # 전체를 한 번에 읽는다. 부모를 따라 재귀 조회하면
        # 깊이만큼 쿼리가 늘어나므로 조립은 메모리에서 한다.
        menus = self._repository.list_all()

        # 1단계: 모든 메뉴를 응답 객체로 바꿔 번호를 열쇠로 하는 사전에 담는다.
        #        나중에 부모를 찾을 때 번호로 바로 꺼내 쓰기 위함이다.
        nodes = {menu.menu_id: MenuTreeResponse.model_validate(menu) for menu in menus}

        # 2단계: 각 메뉴를 자기 부모의 children 목록에 밀어 넣는다.
        roots: list[MenuTreeResponse] = []
        for menu in menus:
            node = nodes[menu.menu_id]
            parent_id = menu.menu_parent_id

            if parent_id is not None and parent_id in nodes:
                # 부모가 있으면 그 부모의 자식 목록에 넣는다.
                nodes[parent_id].children.append(node)
            else:
                # 부모가 없거나(최상위), 부모가 이미 삭제되어 목록에 없는 경우.
                # 후자를 최상위로 올리지 않으면 그 가지 전체가 응답에서 사라진다.
                roots.append(node)

        return roots

    def get_detail(self, menu_id: int) -> Menu:
        return self._get_or_404(menu_id)

    # ------------------------------------------------------------------
    # 생성 / 수정 / 삭제
    # ------------------------------------------------------------------

    def create(self, payload: MenuCreate) -> Menu:
        # 검증 먼저, 저장은 나중에. 순서가 바뀌면 잘못된 데이터가 들어간다.
        self._ensure_parent_exists(payload.menu_parent_id)
        self._ensure_name_available(payload.menu_parent_id, payload.menu_name)

        menu = Menu(
            menu_name=payload.menu_name,
            menu_parent_id=payload.menu_parent_id,
        )
        self._repository.add(menu)
        self._repository.flush()  # SQL 을 보내서 menu_id 를 받아온다
        self._db.commit()  # 확정
        return menu

    def update(self, menu_id: int, payload: MenuUpdate) -> Menu:
        menu = self._get_or_404(menu_id)

        # exclude_unset=True : 요청에 실제로 담겨 온 필드만 뽑는다.
        # 이걸 빼면 안 보낸 필드가 None 으로 덮어써져 내용이 지워진다.
        data = payload.model_dump(exclude_unset=True)

        # 보내지 않은 필드는 기존 값을 그대로 쓴다.
        new_parent_id = data.get("menu_parent_id", menu.menu_parent_id)
        new_name = data.get("menu_name", menu.menu_name)

        # 부모를 바꾸는 요청일 때만 부모 관련 검증을 한다.
        if "menu_parent_id" in data and new_parent_id is not None:
            self._ensure_parent_exists(new_parent_id)
            self._ensure_not_own_descendant(menu_id, new_parent_id)

        # 위치나 이름이 실제로 바뀔 때만 중복을 확인한다.
        # 안 그러면 아무것도 안 바꾸는 요청조차 자기 자신과 중복이라며 막힌다.
        if new_parent_id != menu.menu_parent_id or new_name != menu.menu_name:
            self._ensure_name_available(new_parent_id, new_name)

        # 검증을 다 통과한 뒤에 실제 값을 반영한다.
        for field, value in data.items():
            setattr(menu, field, value)

        self._repository.flush()
        self._db.commit()
        return menu

    def delete(self, menu_id: int) -> None:
        menu = self._get_or_404(menu_id)

        # 자식이 남아 있으면 삭제를 막는다.
        # 함께 지우면 하위 게시판의 글까지 한 번에 사라지므로,
        # 아래부터 정리하도록 유도하는 편이 안전하다.
        if self._repository.list_children(menu_id):
            raise BadRequestError("하위 메뉴가 있어 삭제할 수 없습니다.")

        # 행을 지우지 않고 삭제 시각만 기록한다(논리 삭제).
        # 조회 쿼리들이 deleted_at IS NULL 로 걸러내므로 사용자에게는 사라진다.
        menu.deleted_at = datetime.now(UTC)
        self._repository.flush()
        self._db.commit()
