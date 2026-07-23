"""유저 API 통합 테스트 — 인증/인가 경계."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.users.model import User, UserRole
from tests.integration.conftest import API, DEFAULT_PASSWORD

pytestmark = pytest.mark.integration


class TestMe:
    def test_requires_authentication(self, client: TestClient) -> None:
        assert client.get(f"{API}/users/me").status_code == 401

    def test_rejects_malformed_token(self, client: TestClient) -> None:
        response = client.get(
            f"{API}/users/me", headers={"Authorization": "Bearer not-a-real-token"}
        )

        assert response.status_code == 401

    def test_returns_current_user(
        self, client: TestClient, signup: Callable[..., dict[str, str]]
    ) -> None:
        headers = signup("me@example.com", "본인")

        response = client.get(f"{API}/users/me", headers=headers)

        assert response.status_code == 200
        assert response.json()["email"] == "me@example.com"

    def test_update_nickname(
        self, client: TestClient, signup: Callable[..., dict[str, str]]
    ) -> None:
        headers = signup("update@example.com")

        response = client.patch(f"{API}/users/me", headers=headers, json={"nickname": "변경됨"})

        assert response.status_code == 200
        assert response.json()["nickname"] == "변경됨"

    def test_deactivated_user_is_blocked(
        self, client: TestClient, signup: Callable[..., dict[str, str]]
    ) -> None:
        """탈퇴(비활성화) 후에는 남아 있는 Access Token 으로도 접근할 수 없어야 한다."""
        headers = signup("bye@example.com")
        assert client.delete(f"{API}/users/me", headers=headers).status_code == 204

        assert client.get(f"{API}/users/me", headers=headers).status_code == 403

    def test_deactivated_user_cannot_login(
        self, client: TestClient, signup: Callable[..., dict[str, str]]
    ) -> None:
        headers = signup("nologin@example.com")
        client.delete(f"{API}/users/me", headers=headers)

        response = client.post(
            f"{API}/auth/login",
            json={"email": "nologin@example.com", "password": DEFAULT_PASSWORD},
        )

        assert response.status_code == 401


class TestAdminOnlyList:
    def test_regular_user_is_forbidden(
        self, client: TestClient, signup: Callable[..., dict[str, str]]
    ) -> None:
        headers = signup("regular@example.com")

        response = client.get(f"{API}/users", headers=headers)

        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN"

    def test_admin_can_list(
        self,
        client: TestClient,
        db_session: Session,
        signup: Callable[..., dict[str, str]],
    ) -> None:
        signup("admin@example.com", "관리자")
        user = db_session.query(User).filter(User.email == "admin@example.com").one()
        user.role = UserRole.ADMIN
        db_session.commit()

        # 역할 변경이 반영된 토큰을 다시 받는다.
        login = client.post(
            f"{API}/auth/login",
            json={"email": "admin@example.com", "password": DEFAULT_PASSWORD},
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        response = client.get(f"{API}/users", headers=headers)

        assert response.status_code == 200
        assert response.json()["total"] >= 1


class TestHealth:
    def test_liveness(self, client: TestClient) -> None:
        response = client.get("/health/live")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_readiness_checks_dependencies(self, client: TestClient) -> None:
        response = client.get("/health/ready")

        assert response.status_code == 200
        body = response.json()
        assert body["database"] == "ok"
        assert body["redis"] == "ok"
