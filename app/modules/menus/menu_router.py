"""Menu 엔드포인트."""

from fastapi import APIRouter, status

from app.common.dependencies import CurrentUser, DbSession
from app.modules.menus.menu_schemas import (
    MenuCreate,
    MenuResponse,
    MenuTreeResponse,
    MenuUpdate,
)
from app.modules.menus.menu_service import MenuService

router = APIRouter(prefix="/menus", tags=["menus"])


# 메뉴 트리 조회 API
# 게시판 목록은 비회원도 봐야 해서 로그인 없이 접근 가능
@router.get("", response_model=list[MenuTreeResponse], summary="메뉴 트리 조회")
def get_menu_tree(db: DbSession) -> list[MenuTreeResponse]:
    return MenuService(db).get_tree()


# 메뉴 단건 조회 API
@router.get("/{menu_id}", response_model=MenuResponse, summary="메뉴 단건 조회")
def get_menu(menu_id: int, db: DbSession) -> MenuResponse:
    menu = MenuService(db).get_detail(menu_id)
    return MenuResponse.model_validate(menu)


# 메뉴 생성 API
@router.post(
    "",
    response_model=MenuResponse,
    status_code=status.HTTP_201_CREATED,
    summary="메뉴 생성",
)
def create_menu(
    payload: MenuCreate,
    current_user: CurrentUser,  # 로그인 필수
    db: DbSession,
) -> MenuResponse:
    menu = MenuService(db).create(payload)
    return MenuResponse.model_validate(menu)


# 메뉴 수정 API (이름 변경, 위치 이동)
@router.patch("/{menu_id}", response_model=MenuResponse, summary="메뉴 수정")
def update_menu(
    menu_id: int,
    payload: MenuUpdate,
    current_user: CurrentUser,  # 로그인 필수
    db: DbSession,
) -> MenuResponse:
    menu = MenuService(db).update(menu_id, payload)
    return MenuResponse.model_validate(menu)


# 메뉴 삭제 API (soft delete)
@router.delete("/{menu_id}", status_code=status.HTTP_204_NO_CONTENT, summary="메뉴 삭제")
def delete_menu(
    menu_id: int,
    current_user: CurrentUser,  # 로그인 필수
    db: DbSession,
) -> None:
    MenuService(db).delete(menu_id)
