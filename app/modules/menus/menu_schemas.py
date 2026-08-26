"""Menu 요청/응답 스키마."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MenuCreate(BaseModel):
    """메뉴 생성 요청."""

    # 메뉴 이름 (1~50자)
    menu_name: str = Field(min_length=1, max_length=50)

    # 부모 메뉴 번호. 안 보내면 최상위 메뉴로 만든다
    menu_parent_id: int | None = None


class MenuUpdate(BaseModel):
    """메뉴 수정 요청. 보낸 필드만 반영한다."""

    # 바꿀 이름 (안 보내면 유지)
    menu_name: str | None = Field(default=None, min_length=1, max_length=50)

    # 옮길 부모 번호 (안 보내면 유지)
    menu_parent_id: int | None = None


class MenuResponse(BaseModel):
    """메뉴 단건 응답."""

    # DB 에서 꺼낸 Menu 객체를 이 형식으로 바로 변환하기 위한 설정
    model_config = ConfigDict(from_attributes=True)

    menu_id: int
    menu_name: str
    menu_parent_id: int | None
    created_at: datetime
    updated_at: datetime


class MenuTreeResponse(MenuResponse):
    """트리 응답. 자식 메뉴 목록을 안에 품는다."""

    # 자식의 타입이 자기 자신이라 몇 단이든 담을 수 있다
    children: list["MenuTreeResponse"] = []
