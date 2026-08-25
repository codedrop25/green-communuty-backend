"""페이지네이션 계산 단위 테스트."""

import pytest

from app.common.pagination import PageParams, PageResponse


class TestPageParams:
    @pytest.mark.parametrize(
        ("page", "size", "expected_offset"),
        [(1, 20, 0), (2, 20, 20), (3, 10, 20)],
    )
    def test_offset_calculation(self, page: int, size: int, expected_offset: int) -> None:
        assert PageParams(page=page, size=size).offset == expected_offset


class TestPageResponse:
    @pytest.mark.parametrize(
        ("total", "size", "expected_pages"),
        [
            (0, 20, 0),
            (1, 20, 1),
            (20, 20, 1),
            # 나머지가 있으면 올림 — 여기서 내림하면 마지막 페이지가 사라진다.
            (21, 20, 2),
            (39, 20, 2),
            (40, 20, 2),
        ],
    )
    def test_total_pages_rounds_up(self, total: int, size: int, expected_pages: int) -> None:
        response: PageResponse[str] = PageResponse.create(
            items=[], total=total, params=PageParams(page=1, size=size)
        )

        assert response.total_pages == expected_pages

    def test_echoes_request_params(self) -> None:
        response = PageResponse.create(items=["a", "b"], total=2, params=PageParams(page=3, size=5))

        assert response.page == 3
        assert response.size == 5
        assert response.items == ["a", "b"]
