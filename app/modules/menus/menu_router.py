"""메뉴 API 라우터.

이 파일은 URL 을 함수에 연결하는 역할만 한다.
판단이나 검증은 전부 Service 가 하고, 여기서는 받아서 넘기기만 한다.
학원에서 쓰던 Controller 와 같은 자리다.
"""

from __future__ import annotations

# APIRouter : URL 묶음을 만드는 도구
# status    : 200, 201, 204 같은 응답 코드를 이름으로 쓰기 위한 것
from fastapi import APIRouter, status

# CurrentUser : 매개변수에 적기만 하면 로그인 검사 + 유저 정보 주입
# DbSession   : 매개변수에 적기만 하면 DB 연결 주입
from app.common.dependencies import CurrentUser, DbSession
from app.modules.menus.menu_schemas import (
    MenuCreate,  # 생성 요청에 담겨 오는 형식
    MenuResponse,  # 단건 응답 형식
    MenuTreeResponse,  # 트리 응답 형식 (자식 포함)
    MenuUpdate,  # 수정 요청에 담겨 오는 형식
)
from app.modules.menus.menu_service import MenuService

# prefix : 이 파일의 모든 URL 앞에 /menus 가 붙는다.
#          나중에 api/v1/router.py 가 /api/v1 을 한 번 더 붙이므로
#          최종 주소는 /api/v1/menus 가 된다.
# tags   : /docs 화면에서 묶이는 그룹 이름
router = APIRouter(prefix="/menus", tags=["menus"])


# GET /api/v1/menus
# 로그인 없이 접근 가능하다. 게시판 목록은 비회원도 봐야 하기 때문.
@router.get("", response_model=list[MenuTreeResponse], summary="메뉴 트리 조회")
def get_menu_tree(db: DbSession) -> list[MenuTreeResponse]:
    # Service 가 이미 트리 형태로 조립해서 돌려주므로 그대로 반환한다.
    return MenuService(db).get_tree()


# GET /api/v1/menus/3
# {menu_id} 부분이 함수의 menu_id 매개변수로 자동으로 들어온다.
@router.get("/{menu_id}", response_model=MenuResponse, summary="메뉴 단건 조회")
def get_menu(menu_id: int, db: DbSession) -> MenuResponse:
    menu = MenuService(db).get_detail(menu_id)
    # DB 에서 꺼낸 Menu 객체를 응답 형식으로 변환한다.
    # 모델을 그대로 반환하지 않는 이유는 내보낼 필드를 스키마가 통제하기 때문.
    return MenuResponse.model_validate(menu)


# POST /api/v1/menus
# status_code=201 : 새로 만들었다는 뜻. 조회 성공(200)과 구분한다.
@router.post(
    "",
    response_model=MenuResponse,
    status_code=status.HTTP_201_CREATED,
    summary="메뉴 생성",
)
def create_menu(
    payload: MenuCreate,  # 요청 본문(JSON)이 자동 검증되어 들어온다
    current_user: CurrentUser,  # 이 줄이 있으면 로그인 필수가 된다
    db: DbSession,
) -> MenuResponse:
    menu = MenuService(db).create(payload)
    return MenuResponse.model_validate(menu)


# PATCH /api/v1/menus/3
# PUT 이 아니라 PATCH 인 이유: 보낸 필드만 수정하기 위해서다.
# PUT 은 통째로 교체라서 안 보낸 필드가 null 로 덮어써진다.
@router.patch("/{menu_id}", response_model=MenuResponse, summary="메뉴 수정")
def update_menu(
    menu_id: int,
    payload: MenuUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> MenuResponse:
    menu = MenuService(db).update(menu_id, payload)
    return MenuResponse.model_validate(menu)


# DELETE /api/v1/menus/3
# status_code=204 : 성공했지만 돌려줄 내용이 없다는 뜻.
# 그래서 반환 타입이 None 이다.
@router.delete("/{menu_id}", status_code=status.HTTP_204_NO_CONTENT, summary="메뉴 삭제")
def delete_menu(menu_id: int, current_user: CurrentUser, db: DbSession) -> None:
    # 실제로 행을 지우지 않고 deleted_at 에 시각만 기록한다(논리 삭제).
    MenuService(db).delete(menu_id)
