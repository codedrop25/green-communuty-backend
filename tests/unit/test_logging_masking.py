"""로그 마스킹 단위 테스트 (PLAN.md 8-2).

비밀번호/토큰이 로그로 새는 것은 조용히 일어나고 사후에 되돌릴 수 없다.
마스킹 규칙은 반드시 테스트로 고정한다.
"""

from app.core.logging_config import MASK, mask_sensitive_data


def mask(event: dict[str, object]) -> dict[str, object]:
    return dict(mask_sensitive_data(None, "info", event))  # type: ignore[arg-type]


class TestMasking:
    def test_masks_top_level_password(self) -> None:
        assert mask({"password": "secret123"})["password"] == MASK

    def test_masks_partial_key_matches(self) -> None:
        """`user_password`, `X-Refresh-Token` 같은 변형도 잡아야 한다."""
        result = mask(
            {
                "user_password": "x",
                "refresh_token": "y",
                "Authorization": "Bearer z",
                "api_key": "k",
            }
        )

        assert all(value == MASK for value in result.values())

    def test_masks_nested_dict(self) -> None:
        result = mask({"body": {"email": "a@b.com", "password": "secret"}})

        body = result["body"]
        assert isinstance(body, dict)
        assert body["password"] == MASK
        # 민감하지 않은 값은 그대로 유지되어야 디버깅이 가능하다.
        assert body["email"] == "a@b.com"

    def test_masks_inside_list(self) -> None:
        result = mask({"items": [{"token": "t1"}, {"token": "t2"}]})

        items = result["items"]
        assert isinstance(items, list)
        assert all(item["token"] == MASK for item in items)

    def test_keeps_non_sensitive_fields(self) -> None:
        result = mask({"event": "login", "user_id": 1, "status_code": 200})

        assert result == {"event": "login", "user_id": 1, "status_code": 200}

    def test_handles_deeply_nested_without_crashing(self) -> None:
        """깊이 제한이 걸려 있어도 예외 없이 처리되어야 한다."""
        nested: dict[str, object] = {"password": "leak"}
        for _ in range(20):
            nested = {"level": nested}

        assert mask(nested) is not None
