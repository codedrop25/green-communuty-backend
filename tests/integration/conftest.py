"""통합 테스트 헬퍼."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings

API = settings.API_V1_PREFIX

DEFAULT_PASSWORD = "password123"


@pytest.fixture
def signup(client: TestClient) -> Callable[..., dict[str, str]]:
    """회원가입 후 인증 헤더를 돌려주는 헬퍼."""

    def _signup(email: str, nickname: str = "tester") -> dict[str, str]:
        response = client.post(
            f"{API}/auth/signup",
            json={"email": email, "password": DEFAULT_PASSWORD, "nickname": nickname},
        )
        assert response.status_code == 201, response.text

        login = client.post(
            f"{API}/auth/login",
            json={"email": email, "password": DEFAULT_PASSWORD},
        )
        assert login.status_code == 200, login.text
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    return _signup
