"""보안 프리미티브 단위 테스트.

PLAN.md 10-1: 단위 테스트는 **순수 로직**만 다룬다.
Repository 를 mock 한 Service 테스트는 SQL/FK/트랜잭션 오류를 mock 뒤에 가려
실제 버그를 거의 잡지 못하므로 만들지 않는다.
"""

import pytest

from app.core.exceptions import UnauthorizedError
from app.core.security import (
    BCRYPT_MAX_PASSWORD_BYTES,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
    verify_token_hash,
)


class TestPassword:
    def test_hash_is_not_reversible(self) -> None:
        hashed = hash_password("my-secret-password")

        assert hashed != "my-secret-password"
        assert hashed.startswith("$2b$")

    def test_same_password_produces_different_hashes(self) -> None:
        """salt 가 매번 달라야 레인보우 테이블 공격이 무력화된다."""
        assert hash_password("same") != hash_password("same")

    def test_verify_accepts_correct_password(self) -> None:
        assert verify_password("correct", hash_password("correct")) is True

    def test_verify_rejects_wrong_password(self) -> None:
        assert verify_password("wrong", hash_password("correct")) is False

    def test_verify_returns_false_for_corrupted_hash(self) -> None:
        """깨진 해시가 500 으로 새어 나가면 계정 상태를 추론당한다."""
        assert verify_password("any", "not-a-bcrypt-hash") is False

    def test_rejects_password_over_bcrypt_limit(self) -> None:
        """bcrypt 는 72바이트 초과분을 조용히 버리므로 미리 막는다."""
        too_long = "a" * (BCRYPT_MAX_PASSWORD_BYTES + 1)

        with pytest.raises(ValueError, match="바이트"):
            hash_password(too_long)


class TestJwt:
    def test_access_token_roundtrip(self) -> None:
        payload = decode_token(create_access_token(42), TokenType.ACCESS)

        assert payload.user_id == 42
        assert payload.token_type is TokenType.ACCESS

    def test_refresh_token_carries_jti(self) -> None:
        token, jti = create_refresh_token(7)

        assert decode_token(token, TokenType.REFRESH).jti == jti

    def test_each_token_gets_unique_jti(self) -> None:
        """jti 가 겹치면 한 기기의 로그아웃이 다른 기기를 끊는다."""
        _, first = create_refresh_token(1)
        _, second = create_refresh_token(1)

        assert first != second

    def test_access_token_rejected_as_refresh(self) -> None:
        """토큰 용도 혼동 공격 차단."""
        with pytest.raises(UnauthorizedError):
            decode_token(create_access_token(1), TokenType.REFRESH)

    def test_tampered_token_is_rejected(self) -> None:
        token = create_access_token(1)
        tampered = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")

        with pytest.raises(UnauthorizedError):
            decode_token(tampered, TokenType.ACCESS)

    def test_garbage_token_is_rejected(self) -> None:
        with pytest.raises(UnauthorizedError):
            decode_token("not.a.jwt", TokenType.ACCESS)


class TestTokenHash:
    def test_hash_matches_original(self) -> None:
        token, _ = create_refresh_token(1)

        assert verify_token_hash(token, hash_token(token)) is True

    def test_hash_rejects_different_token(self) -> None:
        token, _ = create_refresh_token(1)
        other, _ = create_refresh_token(2)

        assert verify_token_hash(other, hash_token(token)) is False
