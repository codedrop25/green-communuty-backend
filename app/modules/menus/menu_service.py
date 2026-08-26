"""Menu 비즈니스 로직."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.modules.menus.menu_model import Menu
from app.modules.menus.menu_repository import MenuRepository
from app.modules.menus.menu_schemas import MenuCreate, MenuTreeResponse, MenuUpdate


class MenuService:
    def __init__(self, db: Session) -> None:
        # DB 연결
        self._db = db

        # 메뉴 Repository 사용
        self._repository = MenuRepository(db)

    # ------------------------------------------------------------------ 조회

    # 메뉴 전체를 트리 모양으로 조회
    def get_tree(self) -> list[MenuTreeResponse]:
        # 1. 전체 메뉴를 한 번에 다 읽는다
        #    부모를 따라 한 단계씩 조회하면 깊이만큼 쿼리가 늘어나서,
        #    한 번에 읽고 코드에서 조립한다
        menus = self._repository.list_all()

        # 2. 메뉴 번호로 바로 찾을 수 있게 {번호: 응답객체} 사전을 만든다
        nodes = {menu.menu_id: MenuTreeResponse.model_validate(menu) for menu in menus}

        # 3. 각 메뉴를 자기 부모의 children 목록에 넣는다
        roots: list[MenuTreeResponse] = []
        for menu in menus:
            node = nodes[menu.menu_id]

            # 부모가 있으면 부모의 children 에 추가
            if menu.menu_parent_id is not None and menu.menu_parent_id in nodes:
                nodes[menu.menu_parent_id].children.append(node)
            # 부모가 없으면(최상위) 맨 바깥 목록에 추가
            else:
                roots.append(node)

        return roots

    # 메뉴 하나 조회
    def get_detail(self, menu_id: int) -> Menu:
        menu = self._repository.get_by_id(menu_id)

        # 없으면 404
        if menu is None:
            raise NotFoundError("메뉴를 찾을 수 없습니다.")

        return menu

    # ------------------------------------------------------------------ 생성/수정/삭제

    # 메뉴 생성
    def create(self, payload: MenuCreate) -> Menu:
        # 1. 부모 메뉴 존재 확인 (최상위 메뉴면 건너뜀)
        #    FK 를 안 걸어서 DB 가 안 막아주므로 코드로 확인한다
        if payload.menu_parent_id is not None:
            parent = self._repository.get_by_id(payload.menu_parent_id)
            if parent is None:
                raise NotFoundError("부모 메뉴를 찾을 수 없습니다.")

        # 2. 같은 부모 아래 같은 이름이 있는지 확인
        #    DB 유니크 제약만 믿으면 사용자가 500 을 받으니 미리 409 로 알려준다
        duplicate = self._repository.get_by_parent_and_name(
            payload.menu_parent_id,
            payload.menu_name,
        )
        if duplicate is not None:
            raise ConflictError("같은 위치에 동일한 이름의 메뉴가 이미 있습니다.")

        # 3. 저장
        menu = Menu(
            menu_name=payload.menu_name,
            menu_parent_id=payload.menu_parent_id,
        )
        self._repository.add(menu)
        self._repository.flush()
        self._db.commit()

        return menu

    # 메뉴 수정 (이름 변경, 위치 이동)
    def update(self, menu_id: int, payload: MenuUpdate) -> Menu:
        # 1. 수정할 메뉴 조회
        menu = self.get_detail(menu_id)

        # 2. 요청에 실제로 담겨 온 필드만 뽑는다
        #    이걸 안 하면 안 보낸 필드가 None 으로 덮어써진다
        changes = payload.model_dump(exclude_unset=True)

        # 바뀐 후의 값 (안 보낸 필드는 기존 값 유지)
        new_parent_id = changes.get("menu_parent_id", menu.menu_parent_id)
        new_name = changes.get("menu_name", menu.menu_name)

        # 3. 부모를 바꾸는 요청이면 부모 확인
        if "menu_parent_id" in changes and new_parent_id is not None:
            # 새 부모가 실제로 있는지
            parent = self._repository.get_by_id(new_parent_id)
            if parent is None:
                raise NotFoundError("부모 메뉴를 찾을 수 없습니다.")

            # 자기 자신이나 자기 하위로 옮기는 건 아닌지
            self._check_no_cycle(menu_id, new_parent_id)

        # 4. 위치나 이름이 실제로 바뀔 때만 중복 확인
        #    (안 바뀌었는데 검사하면 자기 자신과 중복이라며 막힌다)
        if new_parent_id != menu.menu_parent_id or new_name != menu.menu_name:
            duplicate = self._repository.get_by_parent_and_name(new_parent_id, new_name)
            if duplicate is not None:
                raise ConflictError("같은 위치에 동일한 이름의 메뉴가 이미 있습니다.")

        # 5. 검증을 다 통과했으면 값 반영
        for field, value in changes.items():
            setattr(menu, field, value)

        self._repository.flush()
        self._db.commit()

        return menu

    # 메뉴 삭제 (soft delete)
    def delete(self, menu_id: int) -> None:
        # 1. 삭제할 메뉴 조회
        menu = self.get_detail(menu_id)

        # 2. 자식 메뉴가 있으면 삭제 불가
        #    같이 지우면 하위 게시판 글까지 한 번에 사라지므로
        #    아래부터 정리하도록 막는다
        children = self._repository.list_children(menu_id)
        if children:
            raise BadRequestError("하위 메뉴가 있어 삭제할 수 없습니다.")

        # 3. 행을 지우지 않고 삭제 시각만 기록한다
        #    조회 쿼리들이 deleted_at IS NULL 로 걸러내므로 화면에서는 사라진다
        menu.deleted_at = datetime.now(UTC)
        self._repository.flush()
        self._db.commit()

    # ------------------------------------------------------------------ 검증

    # 메뉴를 자기 자신이나 자기 하위로 옮기는 것을 막는다
    # 예: "자동차"를 그 아래 "전기차" 밑으로 옮기면 둘이 서로를 가리키는
    #     고리가 생기고, 트리 조립이 무한 반복에 빠진다
    def _check_no_cycle(self, menu_id: int, new_parent_id: int) -> None:
        # 자기 자신을 부모로 지정한 경우
        if menu_id == new_parent_id:
            raise BadRequestError("자기 자신을 부모로 지정할 수 없습니다.")

        # 새 부모에서 출발해 부모의 부모를 계속 따라 올라간다
        # 올라가는 길에 자기 자신이 나오면 = 자기 하위로 들어가려는 것
        current_id: int | None = new_parent_id
        while current_id is not None:
            if current_id == menu_id:
                raise BadRequestError("하위 메뉴를 부모로 지정할 수 없습니다.")

            parent = self._repository.get_by_id(current_id)

            # 더 올라갈 부모가 없으면 고리가 아니다
            if parent is None:
                return

            current_id = parent.menu_parent_id
