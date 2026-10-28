"""프런트 연동 중 확인한 실제 DB/Redis 동작의 회귀 테스트."""

from collections.abc import Callable
from io import BytesIO
from typing import BinaryIO

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from redis import Redis
from sqlalchemy.orm import Session

from app.infrastructure.storage.base import Storage
from app.infrastructure.storage.s3 import get_storage
from app.modules.posts.post_like_model import PostLike
from app.modules.posts.post_model import Post
from app.modules.posts.post_repository import PostRepository
from tests.integration.conftest import API

pytestmark = pytest.mark.integration


@pytest.fixture
def headers(signup: Callable[..., dict[str, str]]) -> dict[str, str]:
    return signup("integration@example.com", "연동검증")


@pytest.fixture
def post_id(client: TestClient, headers: dict[str, str]) -> int:
    response = client.post(
        f"{API}/posts", headers=headers, json={"post_title": "연동", "post_content": "본문"}
    )
    assert response.status_code == 201
    return int(response.json()["post_id"])


def test_pagination_is_newest_first_across_pages(
    client: TestClient, headers: dict[str, str]
) -> None:
    ids = []
    for i in range(5):
        created = client.post(
            f"{API}/posts", headers=headers, json={"post_title": str(i), "post_content": "본문"}
        )
        ids.append(created.json()["post_id"])
    pages = [
        client.get(f"{API}/posts?page={page}&size=2", headers=headers).json()
        for page in range(1, 4)
    ]
    assert [item["post_id"] for page in pages for item in page["items"]] == ids[::-1]
    assert all(page["total"] == 5 and page["total_pages"] == 3 for page in pages)


def test_view_count_persists_for_reader_only(
    client: TestClient,
    headers: dict[str, str],
    post_id: int,
    signup: Callable[..., dict[str, str]],
    db_session: Session,
) -> None:
    reader = signup("reader@example.com", "독자")
    assert client.get(f"{API}/posts/{post_id}", headers=headers).json()["post_view_count"] == 0
    for expected in (1, 2):
        response = client.get(f"{API}/posts/{post_id}", headers=reader)
        assert response.json()["post_view_count"] == expected
    db_session.expire_all()
    post = db_session.get(Post, post_id)
    assert post is not None and post.post_view_count == 2


def test_likes_survive_refresh_before_and_after_sync(
    client: TestClient,
    headers: dict[str, str],
    post_id: int,
    db_session: Session,
    redis_client: Redis,
) -> None:
    user_id = client.get(f"{API}/users/me", headers=headers).json()["user_id"]
    repo = PostRepository(db_session, redis_client)
    assert client.post(f"{API}/posts/{post_id}/likes", headers=headers).status_code == 201
    detail = client.get(f"{API}/posts/{post_id}", headers=headers).json()
    assert detail["is_liked"] is True and detail["post_like_count"] == 1

    # Simulate the persisted snapshot while its Redis entry has not yet been cleared.
    db_session.add(PostLike(post_id=post_id, user_id=user_id))
    db_session.flush()
    assert repo.count_likes(post_id) == 1
    assert client.put(f"{API}/posts/{post_id}/likes", headers=headers).status_code == 204
    detail = client.get(f"{API}/posts/{post_id}", headers=headers).json()
    assert detail["is_liked"] is False and detail["post_like_count"] == 0
    repo.scan_like_to_db()
    assert repo.count_likes(post_id) == 0


def test_replies_do_not_inflate_parent_pagination(
    client: TestClient,
    headers: dict[str, str],
    post_id: int,
) -> None:
    parent = client.post(
        f"{API}/posts/{post_id}/comments", headers=headers, json={"comment_content": "댓글"}
    ).json()["comment_id"]
    response = client.post(
        f"{API}/posts/{post_id}/comments",
        headers=headers,
        json={"comment_content": "답글", "parent_comment_id": parent},
    )
    assert response.status_code == 201
    page = client.get(f"{API}/posts/{post_id}/comments?size=1").json()
    assert page["total"] == 1 and page["total_pages"] == 1
    assert page["items"][0]["reply_count"] == 1
    replies = client.get(f"{API}/comments/{parent}/replies").json()
    assert replies[0]["comment_content"] == "답글"


class MemoryStorage(Storage):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def upload(self, key: str, fileobj: BinaryIO, content_type: str | None = None) -> str:
        self.objects[key] = fileobj.read()
        return key

    def generate_presigned_url(self, key: str, expires_in: int) -> str:
        assert key in self.objects
        return f"https://images.example.com/{key}?expires={expires_in}"


def test_image_upload_and_reload(
    app: FastAPI,
    client: TestClient,
    headers: dict[str, str],
    post_id: int,
    signup: Callable[..., dict[str, str]],
) -> None:
    storage = MemoryStorage()
    app.dependency_overrides[get_storage] = lambda: storage
    image = BytesIO()
    Image.new("RGB", (20, 20), "green").save(image, "PNG")
    files = {"image": ("sample.png", image.getvalue(), "image/png")}
    other = signup("image-reader@example.com", "독자")
    assert (
        client.post(f"{API}/posts/{post_id}/images", headers=other, files=files).status_code == 403
    )
    response = client.post(f"{API}/posts/{post_id}/images", headers=headers, files=files)
    assert response.status_code == 201, response.text
    assert len(storage.objects) == 3
    assert client.get(f"{API}/posts/{post_id}", headers=headers).json()["has_images"] is True
    images = client.get(f"{API}/posts/{post_id}/images", headers=headers)
    assert images.status_code == 200
    assert images.json() == [response.json()]
    invalid = client.post(
        f"{API}/posts/{post_id}/images",
        headers=headers,
        files={"image": ("bad.png", b"invalid", "image/png")},
    )
    assert invalid.status_code == 400
