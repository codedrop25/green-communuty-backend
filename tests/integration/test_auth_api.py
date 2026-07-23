"""인증 통합 테스트 (PLAN.md 10-3).

핵심은 **Refresh Token 회전과 재사용 탐지**다.
회전이 깨지면 탈취된 토큰이 만료까지 살아 있으므로 반드시 회귀 테스트로 고정한다.
"""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from tests.integration.conftest import API, DEFAULT_PASSWORD

pytestmark = pytest.mark.integration


def _login(client: TestClient, email: str) -> str:
    """로그인 후 Refresh Token 쿠키 값을 돌려준다."""
    # TestClient 는 응답 쿠키를 클라이언트에 계속 보관한다.
    # 여러 기기를 흉내 내는 테스트에서 이전 세션의 쿠키가 함께 전송되면
    # 무엇을 검증하는지 알 수 없게 되므로, 매번 비우고 시작한다.
    client.cookies.clear()
    response = client.post(f"{API}/auth/login", json={"email": email, "password": DEFAULT_PASSWORD})
    assert response.status_code == 200, response.text
    return response.cookies["refresh_token"]


def _post_with_refresh(client: TestClient, path: str, token: str) -> Response:
    """지정한 Refresh Token **하나만** 실어 요청한다."""
    client.cookies.clear()
    client.cookies.set("refresh_token", token)
    response = client.post(f"{API}{path}")
    client.cookies.clear()
    return response


class TestSignupLogin:
    def test_signup_returns_user_without_password(self, client: TestClient) -> None:
        response = client.post(
            f"{API}/auth/signup",
            json={"email": "new@example.com", "password": DEFAULT_PASSWORD, "nickname": "신규"},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "new@example.com"
        # 해시가 응답에 새어 나가면 안 된다.
        assert "password" not in body
        assert "password_hash" not in body

    def test_duplicate_email_returns_409(self, client: TestClient) -> None:
        payload = {"email": "dup@example.com", "password": DEFAULT_PASSWORD, "nickname": "중복"}
        client.post(f"{API}/auth/signup", json=payload)

        response = client.post(f"{API}/auth/signup", json=payload)

        assert response.status_code == 409
        assert response.json()["code"] == "CONFLICT"

    def test_login_puts_refresh_token_in_httponly_cookie(
        self, client: TestClient, signup: Callable[..., dict[str, str]]
    ) -> None:
        signup("cookie@example.com")

        response = client.post(
            f"{API}/auth/login",
            json={"email": "cookie@example.com", "password": DEFAULT_PASSWORD},
        )

        # 본문에는 Access Token 만, Refresh 는 쿠키로만 (PLAN.md 4-4).
        assert "refresh_token" not in response.json()
        assert "refresh_token" in response.cookies
        set_cookie = response.headers["set-cookie"]
        assert "HttpOnly" in set_cookie
        assert "Path=/api/v1/auth" in set_cookie

    def test_wrong_password_returns_401(
        self, client: TestClient, signup: Callable[..., dict[str, str]]
    ) -> None:
        signup("wrong@example.com")

        response = client.post(
            f"{API}/auth/login",
            json={"email": "wrong@example.com", "password": "totally-wrong-password"},
        )

        assert response.status_code == 401

    def test_unknown_email_returns_same_error_as_wrong_password(self, client: TestClient) -> None:
        """계정 존재 여부가 응답으로 드러나면 가입 이메일을 수집당한다."""
        response = client.post(
            f"{API}/auth/login",
            json={"email": "nobody@example.com", "password": DEFAULT_PASSWORD},
        )

        assert response.status_code == 401
        assert response.json()["code"] == "UNAUTHORIZED"


class TestRefreshRotation:
    def test_refresh_rotates_token(
        self, client: TestClient, signup: Callable[..., dict[str, str]]
    ) -> None:
        signup("rotate@example.com")
        original = _login(client, "rotate@example.com")

        response = _post_with_refresh(client, "/auth/refresh", original)

        assert response.status_code == 200
        assert response.cookies["refresh_token"] != original

    def test_reused_token_is_rejected(
        self, client: TestClient, signup: Callable[..., dict[str, str]]
    ) -> None:
        signup("reuse@example.com")
        original = _login(client, "reuse@example.com")
        _post_with_refresh(client, "/auth/refresh", original)

        # 이미 회전된 토큰을 다시 제출 = 탈취 신호.
        response = _post_with_refresh(client, "/auth/refresh", original)

        assert response.status_code == 401

    def test_reuse_detection_revokes_all_sessions(
        self, client: TestClient, signup: Callable[..., dict[str, str]]
    ) -> None:
        """재사용이 탐지되면 누가 진짜 주인인지 알 수 없으므로 전부 끊는다."""
        signup("revoke@example.com")
        original = _login(client, "revoke@example.com")
        other_device = _login(client, "revoke@example.com")

        rotated = _post_with_refresh(client, "/auth/refresh", original).cookies["refresh_token"]
        # 탈취 신호 발생.
        _post_with_refresh(client, "/auth/refresh", original)

        # 회전으로 받은 정상 토큰도, 다른 기기 토큰도 모두 무효여야 한다.
        assert _post_with_refresh(client, "/auth/refresh", rotated).status_code == 401
        assert _post_with_refresh(client, "/auth/refresh", other_device).status_code == 401

    def test_logged_out_token_does_not_trigger_mass_revocation(
        self, client: TestClient, signup: Callable[..., dict[str, str]]
    ) -> None:
        """정상 로그아웃한 토큰의 재제출은 탈취가 아니다.

        사용자가 뒤로가기를 누르거나 탭이 여러 개면 흔히 발생하는 상황이다.
        이것을 재사용 탐지로 오인하면 다른 기기까지 전부 로그아웃된다.
        """
        signup("logout-reuse@example.com")
        device1 = _login(client, "logout-reuse@example.com")
        device2 = _login(client, "logout-reuse@example.com")

        _post_with_refresh(client, "/auth/logout", device1)
        # 로그아웃된 토큰을 다시 제출 — 거부되지만 다른 세션은 살아 있어야 한다.
        assert _post_with_refresh(client, "/auth/refresh", device1).status_code == 401

        assert _post_with_refresh(client, "/auth/refresh", device2).status_code == 200

    def test_access_token_cannot_be_used_as_refresh(
        self, client: TestClient, signup: Callable[..., dict[str, str]]
    ) -> None:
        """토큰 용도 혼동 차단 (payload 의 type 검증)."""
        headers = signup("confuse@example.com")
        access_token = headers["Authorization"].removeprefix("Bearer ")

        response = _post_with_refresh(client, "/auth/refresh", access_token)

        assert response.status_code == 401


class TestMultiDevice:
    def test_logout_affects_only_current_device(
        self, client: TestClient, signup: Callable[..., dict[str, str]]
    ) -> None:
        signup("multi@example.com")
        device1 = _login(client, "multi@example.com")
        device2 = _login(client, "multi@example.com")
        assert device1 != device2

        _post_with_refresh(client, "/auth/logout", device1)

        assert _post_with_refresh(client, "/auth/refresh", device1).status_code == 401
        assert _post_with_refresh(client, "/auth/refresh", device2).status_code == 200

    def test_logout_all_revokes_every_session(
        self, client: TestClient, signup: Callable[..., dict[str, str]]
    ) -> None:
        headers = signup("all@example.com")
        device1 = _login(client, "all@example.com")
        device2 = _login(client, "all@example.com")

        response = client.post(f"{API}/auth/logout-all", headers=headers)
        assert response.status_code == 200

        for token in (device1, device2):
            assert _post_with_refresh(client, "/auth/refresh", token).status_code == 401

    def test_logout_is_idempotent(self, client: TestClient) -> None:
        """유효하지 않은 토큰으로 로그아웃해도 실패시키지 않는다."""
        response = _post_with_refresh(client, "/auth/logout", "garbage")

        assert response.status_code == 200


class TestLoginRateLimit:
    def test_blocks_after_threshold(
        self, client: TestClient, signup: Callable[..., dict[str, str]]
    ) -> None:
        signup("brute@example.com")
        payload = {"email": "brute@example.com", "password": "wrong-password"}

        codes = [client.post(f"{API}/auth/login", json=payload).status_code for _ in range(7)]

        assert 429 in codes, f"Rate Limit 이 동작하지 않음: {codes}"

    def test_sets_retry_after_header(
        self, client: TestClient, signup: Callable[..., dict[str, str]]
    ) -> None:
        signup("retry@example.com")
        payload = {"email": "retry@example.com", "password": "wrong-password"}

        response = None
        for _ in range(8):
            response = client.post(f"{API}/auth/login", json=payload)
            if response.status_code == 429:
                break

        assert response is not None
        assert response.status_code == 429
        assert int(response.headers["Retry-After"]) > 0

    def test_successful_login_resets_counter(
        self, client: TestClient, signup: Callable[..., dict[str, str]]
    ) -> None:
        """오타 몇 번으로 정상 사용자가 잠기면 안 된다."""
        signup("reset@example.com")
        for _ in range(3):
            client.post(
                f"{API}/auth/login",
                json={"email": "reset@example.com", "password": "wrong-password"},
            )

        ok = client.post(
            f"{API}/auth/login",
            json={"email": "reset@example.com", "password": DEFAULT_PASSWORD},
        )
        assert ok.status_code == 200

        # 카운터가 비워졌으므로 다시 여러 번 시도할 수 있어야 한다.
        codes = [
            client.post(
                f"{API}/auth/login",
                json={"email": "reset@example.com", "password": "wrong-password"},
            ).status_code
            for _ in range(3)
        ]
        assert 429 not in codes
