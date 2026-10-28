"""모든 서비스 경로의 인증 경계 회귀 테스트."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from tests.integration.conftest import API

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "path",
    [
        "/users/me",
        "/users",
        "/users/1",
        "/menus",
        "/menus/1",
        "/posts",
        "/posts/1",
        "/posts/1/share",
        "/posts/1/images",
        "/posts/1/comments",
        "/comments/1/replies",
    ],
)
def test_service_reads_require_login(client: TestClient, path: str) -> None:
    response = client.get(f"{API}{path}")
    assert response.status_code == 401


def test_authenticated_menu_and_comments_are_accessible(
    client: TestClient, signup: Callable[..., dict[str, str]]
) -> None:
    headers = signup("protected@example.com")
    assert client.get(f"{API}/menus", headers=headers).status_code == 200
    post = client.post(
        f"{API}/posts", headers=headers, json={"post_title": "인증", "post_content": "본문"}
    ).json()
    assert client.get(f"{API}/posts/{post['post_id']}/comments", headers=headers).status_code == 200


def test_deactivated_account_loses_session(
    client: TestClient, signup: Callable[..., dict[str, str]]
) -> None:
    headers = signup("inactive@example.com")
    assert client.delete(f"{API}/users/me", headers=headers).status_code == 204
    assert client.get(f"{API}/users/me", headers=headers).status_code == 401
    assert client.get(f"{API}/menus", headers=headers).status_code == 401
    assert client.post(f"{API}/auth/refresh").status_code == 401
