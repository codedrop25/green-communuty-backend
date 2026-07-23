"""페이지네이션 표준 (PLAN.md 3-6).

목록 응답은 전부 `PageResponse[T]` 로 통일한다.
"""

from collections.abc import Sequence
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, Field

# 상한을 두지 않으면 `size=100000` 한 방으로 DB 와 메모리를 모두 밀어버릴 수 있다.
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


class PageParams(BaseModel):
    """목록 조회 공통 쿼리 파라미터.

    라우터에서 `params: Annotated[PageParams, Depends()]` 로 받는다.
    """

    page: Annotated[int, Query(ge=1, description="1부터 시작하는 페이지 번호")] = 1
    size: Annotated[
        int,
        Query(ge=1, le=MAX_PAGE_SIZE, description=f"페이지 크기 (최대 {MAX_PAGE_SIZE})"),
    ] = DEFAULT_PAGE_SIZE

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size

    @property
    def limit(self) -> int:
        return self.size


class PageResponse[T](BaseModel):
    """목록 응답 표준 포맷."""

    items: list[T]
    total: int = Field(description="필터 조건에 해당하는 전체 건수")
    page: int
    size: int
    total_pages: int = Field(description="전체 페이지 수")

    @classmethod
    def create(cls, items: Sequence[T], total: int, params: PageParams) -> "PageResponse[T]":
        """조회 결과를 응답 포맷으로 감싼다.

        `total_pages` 를 서버가 계산해 내려주는 이유는, 클라이언트마다
        올림 처리를 제각각 구현하다 마지막 페이지에서 어긋나는 일을 막기 위함이다.
        """
        total_pages = (total + params.size - 1) // params.size if total else 0
        return cls(
            items=list(items),
            total=total,
            page=params.page,
            size=params.size,
            total_pages=total_pages,
        )
