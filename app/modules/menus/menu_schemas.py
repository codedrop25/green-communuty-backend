"""메뉴 요청/응답 스키마.

model.py 가 DB 의 모양이라면, 이 파일은 바깥과 주고받는 데이터의 모양이다.
모델을 그대로 내보내지 않는 이유는, 내보낼 필드를 여기서 통제하기 위해서다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

# BaseModel  스키마 클래스의 부모
# ConfigDict 스키마 동작 설정
# Field      길이 제한 같은 검증 규칙
from pydantic import BaseModel, ConfigDict, Field

# 이름 규칙에 별명을 붙여 한곳에 모아둔다.
# 스키마마다 min/max 를 반복해 적으면 한쪽만 고쳐졌을 때
# 생성과 수정의 검증 기준이 조용히 갈라진다.
MenuNameStr = Annotated[str, Field(min_length=1, max_length=50)]


class MenuCreate(BaseModel):
    """메뉴 생성 요청 본문."""

    # 타입만 적어두면 Pydantic 이 자동으로 검증한다.
    # 1~50자를 벗어나면 우리 코드에 닿기도 전에 422 로 거부된다.
    # 자바의 @Valid + @NotBlank + @Size 를 합친 셈이다.
    menu_name: MenuNameStr

    # = None 은 "안 보내도 된다"는 뜻.
    # 안 보내거나 null 이면 최상위 메뉴로 만든다.
    menu_parent_id: int | None = None


class MenuUpdate(BaseModel):
    """메뉴 수정 요청 본문. 보낸 필드만 반영한다."""

    # 둘 다 선택이다. 이름만 바꾸거나 위치만 옮길 수 있어야 하기 때문.
    menu_name: MenuNameStr | None = None
    menu_parent_id: int | None = None


class MenuResponse(BaseModel):
    """메뉴 단건 응답."""

    # from_attributes=True 가 있어야 DB 에서 꺼낸 Menu 객체를
    # 이 형식으로 자동 변환할 수 있다. 없으면 딕셔너리만 받는다.
    model_config = ConfigDict(from_attributes=True)

    menu_id: int
    menu_name: str
    menu_parent_id: int | None
    created_at: datetime
    updated_at: datetime
    # deleted_at 은 일부러 뺐다. 살아 있는 메뉴만 응답에 나가므로
    # 클라이언트에게는 의미가 없는 내부 정보다.


class MenuTreeResponse(MenuResponse):
    """트리 응답. 자식 목록을 재귀적으로 포함한다."""

    # 자식의 타입이 자기 자신이다. 메뉴 안에 메뉴가 들어가는 구조라
    # 이렇게 자기를 참조해야 몇 단이든 표현할 수 있다.
    # 따옴표로 감싼 이유는 클래스 정의가 끝나기 전에 자기 이름을 쓰기 때문이다.
    children: list[MenuTreeResponse] = []
