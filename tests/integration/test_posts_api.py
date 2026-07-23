"""게시글/댓글 통합 테스트 — 소유권 검증과 논리 삭제."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from tests.integration.conftest import API

pytestmark = pytest.mark.integration


@pytest.fixture
def author_headers(signup: Callable[..., dict[str, str]]) -> dict[str, str]:
    return signup("author@example.com", "작성자")


@pytest.fixture
def other_headers(signup: Callable[..., dict[str, str]]) -> dict[str, str]:
    return signup("other@example.com", "타인")


@pytest.fixture
def post_id(client: TestClient, author_headers: dict[str, str]) -> int:
    response = client.post(
        f"{API}/posts",
        headers=author_headers,
        json={"title": "테스트 게시글", "content": "본문"},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


class TestPostCrud:
    def test_create_requires_authentication(self, client: TestClient) -> None:
        response = client.post(f"{API}/posts", json={"title": "익명", "content": "본문"})

        assert response.status_code == 401

    def test_detail_includes_comments_and_author(
        self, client: TestClient, author_headers: dict[str, str], post_id: int
    ) -> None:
        client.post(
            f"{API}/posts/{post_id}/comments",
            headers=author_headers,
            json={"content": "댓글 본문"},
        )

        response = client.get(f"{API}/posts/{post_id}")

        assert response.status_code == 200
        body = response.json()
        # 관계가 lazy="raise" 이므로, eager loading 이 빠지면 여기서 예외가 난다.
        assert body["author"]["nickname"] == "작성자"
        assert [c["content"] for c in body["comments"]] == ["댓글 본문"]

    def test_list_returns_page_response(self, client: TestClient, post_id: int) -> None:
        response = client.get(f"{API}/posts", params={"page": 1, "size": 10})

        assert response.status_code == 200
        body = response.json()
        assert {"items", "total", "page", "size", "total_pages"} <= body.keys()
        assert body["total"] >= 1

    def test_page_size_upper_bound_is_enforced(self, client: TestClient) -> None:
        """상한이 없으면 size=100000 한 번으로 DB 를 밀어버릴 수 있다."""
        response = client.get(f"{API}/posts", params={"page": 1, "size": 10_000})

        assert response.status_code == 422

    def test_emoji_roundtrip(self, client: TestClient, author_headers: dict[str, str]) -> None:
        """utf8mb4 설정 확인. latin1/utf8 이면 여기서 깨진다."""
        created = client.post(
            f"{API}/posts",
            headers=author_headers,
            json={"title": "이모지 🎉🔥", "content": "본문 ✅"},
        )

        assert created.status_code == 201
        detail = client.get(f"{API}/posts/{created.json()['id']}").json()
        assert detail["title"] == "이모지 🎉🔥"


class TestPostOwnership:
    """PLAN.md 3-7: 가장 흔한 취약점인 "남의 글 수정/삭제"를 고정한다."""

    def test_other_user_cannot_update(
        self, client: TestClient, other_headers: dict[str, str], post_id: int
    ) -> None:
        response = client.patch(
            f"{API}/posts/{post_id}", headers=other_headers, json={"title": "탈취"}
        )

        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN"

    def test_other_user_cannot_delete(
        self, client: TestClient, other_headers: dict[str, str], post_id: int
    ) -> None:
        response = client.delete(f"{API}/posts/{post_id}", headers=other_headers)

        assert response.status_code == 403

    def test_author_can_update(
        self, client: TestClient, author_headers: dict[str, str], post_id: int
    ) -> None:
        response = client.patch(
            f"{API}/posts/{post_id}", headers=author_headers, json={"title": "수정됨"}
        )

        assert response.status_code == 200
        assert response.json()["title"] == "수정됨"

    def test_partial_update_keeps_unsent_fields(
        self, client: TestClient, author_headers: dict[str, str], post_id: int
    ) -> None:
        """보내지 않은 필드가 None 으로 덮어써지면 안 된다."""
        response = client.patch(
            f"{API}/posts/{post_id}", headers=author_headers, json={"title": "제목만 변경"}
        )

        assert response.status_code == 200
        assert response.json()["content"] == "본문"


class TestSoftDelete:
    def test_deleted_post_is_hidden(
        self, client: TestClient, author_headers: dict[str, str], post_id: int
    ) -> None:
        assert client.delete(f"{API}/posts/{post_id}", headers=author_headers).status_code == 204

        assert client.get(f"{API}/posts/{post_id}").status_code == 404

    def test_deleted_post_excluded_from_list(
        self, client: TestClient, author_headers: dict[str, str], post_id: int
    ) -> None:
        before = client.get(f"{API}/posts").json()["total"]
        client.delete(f"{API}/posts/{post_id}", headers=author_headers)

        after = client.get(f"{API}/posts").json()["total"]
        assert after == before - 1

    def test_cannot_comment_on_deleted_post(
        self, client: TestClient, author_headers: dict[str, str], post_id: int
    ) -> None:
        client.delete(f"{API}/posts/{post_id}", headers=author_headers)

        response = client.post(
            f"{API}/posts/{post_id}/comments",
            headers=author_headers,
            json={"content": "삭제된 글에 댓글"},
        )

        assert response.status_code == 404


class TestComments:
    def test_other_user_cannot_edit_comment(
        self,
        client: TestClient,
        author_headers: dict[str, str],
        other_headers: dict[str, str],
        post_id: int,
    ) -> None:
        comment_id = client.post(
            f"{API}/posts/{post_id}/comments",
            headers=author_headers,
            json={"content": "원본"},
        ).json()["id"]

        response = client.patch(
            f"{API}/comments/{comment_id}", headers=other_headers, json={"content": "탈취"}
        )

        assert response.status_code == 403

    def test_comment_list_is_paginated(
        self, client: TestClient, author_headers: dict[str, str], post_id: int
    ) -> None:
        for i in range(3):
            client.post(
                f"{API}/posts/{post_id}/comments",
                headers=author_headers,
                json={"content": f"댓글 {i}"},
            )

        response = client.get(f"{API}/posts/{post_id}/comments", params={"page": 1, "size": 2})

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 3
        assert len(body["items"]) == 2
        assert body["total_pages"] == 2
