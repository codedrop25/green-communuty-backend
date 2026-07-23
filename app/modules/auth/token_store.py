"""Refresh Token 저장소 (Redis).

키 구조 (PLAN.md 4-1):

    refresh:{user_id}:{jti}        -> sha256(refresh_token)   TTL = REFRESH_TOKEN_EXPIRE_DAYS
    refresh_index:{user_id}        -> SET { jti, ... }        TTL = 동일
    refresh_used:{user_id}:{jti}   -> "1"                     TTL = 해당 토큰의 잔여 수명

**인덱스 Set 을 따로 두는 이유:**
    "모든 기기에서 로그아웃" 을 구현하려면 한 유저의 모든 토큰 키를 찾아야 한다.
    `KEYS refresh:{uid}:*` 는 O(N) 블로킹 명령이라 운영 Redis 전체를 멈춘다.
    유저별 jti 목록을 Set 으로 들고 있으면 SMEMBERS 한 번으로 정확히 필요한 키만 얻는다.

**`refresh_used` 를 따로 두는 이유 (중요):**
    재사용 탐지는 "이미 회전에 사용된 토큰이 다시 왔다"를 근거로 삼는다.
    그런데 활성 키가 없다는 사실만으로 탈취라고 판단하면,
    **정상적으로 로그아웃한 토큰을 다시 제출한 경우**까지 탈취로 오인해
    그 유저의 다른 기기 세션까지 전부 끊어버린다
    (사용자가 뒤로가기를 누르거나 탭이 여러 개면 흔히 발생한다).

    그래서 "회전으로 소비됨"을 명시적으로 기록하고, 이 표식이 있을 때만 탈취로 본다.
    로그아웃은 이 표식을 남기지 않으므로 다른 세션에 영향을 주지 않는다.

원문 토큰이 아닌 **해시**를 저장한다. Redis 가 유출되어도 토큰 자체는 노출되지 않는다.
"""

from enum import StrEnum, auto
from typing import cast

from redis import Redis

from app.core.config import settings
from app.core.security import verify_token_hash


class TokenState(StrEnum):
    """제출된 Refresh Token 의 판정 결과."""

    ACTIVE = auto()
    """유효한 활성 토큰. 정상 회전 대상."""

    REUSED = auto()
    """이미 회전에 사용된 토큰이 다시 제출됨. 탈취 정황 → 전체 세션 무효화."""

    FORGED = auto()
    """활성 토큰은 있으나 해시가 불일치. 위조 → 전체 세션 무효화."""

    UNKNOWN = auto()
    """만료 또는 로그아웃된 토큰. 정상적인 상황이므로 해당 요청만 거부한다."""


class RefreshTokenStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._ttl_seconds = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

    # ------------------------------------------------------------------ 키

    @staticmethod
    def _token_key(user_id: int, jti: str) -> str:
        return f"refresh:{user_id}:{jti}"

    @staticmethod
    def _index_key(user_id: int) -> str:
        return f"refresh_index:{user_id}"

    @staticmethod
    def _used_key(user_id: int, jti: str) -> str:
        return f"refresh_used:{user_id}:{jti}"

    # ------------------------------------------------------------------ 저장

    def save(self, user_id: int, jti: str, token_hash: str) -> None:
        """발급된 Refresh Token 을 저장하고 인덱스에 등록한다.

        두 명령을 파이프라인으로 묶어 왕복을 줄인다.
        인덱스 TTL 도 함께 연장해, 활성 세션이 있는 동안은 인덱스가 살아 있게 한다.
        """
        pipeline = self._redis.pipeline()
        pipeline.set(self._token_key(user_id, jti), token_hash, ex=self._ttl_seconds)
        pipeline.sadd(self._index_key(user_id), jti)
        pipeline.expire(self._index_key(user_id), self._ttl_seconds)
        pipeline.execute()

    # ------------------------------------------------------------------ 검증

    def verify(self, user_id: int, jti: str, token: str) -> TokenState:
        """제출된 토큰의 상태를 판정한다.

        세 상태를 **구분해서** 돌려주는 것이 핵심이다.
        하나로 뭉뚱그리면 정상 로그아웃과 탈취를 구별할 수 없다 (모듈 상단 주석 참고).
        """
        stored = self._redis.get(self._token_key(user_id, jti))

        if stored is not None:
            if verify_token_hash(token, str(stored)):
                return TokenState.ACTIVE
            # 활성 토큰이 있는데 해시가 다르다 = 위조된 토큰.
            return TokenState.FORGED

        if bool(self._redis.exists(self._used_key(user_id, jti))):
            # 회전으로 이미 소비된 토큰이 다시 왔다 = 탈취 정황.
            return TokenState.REUSED

        # 만료되었거나 로그아웃된 토큰. 흔한 일이므로 다른 세션을 건드리지 않는다.
        return TokenState.UNKNOWN

    def rotate(self, user_id: int, jti: str, remaining_ttl_seconds: int) -> None:
        """회전 시 기존 토큰을 소비 처리한다.

        `remaining_ttl_seconds` 는 그 토큰의 원래 만료까지 남은 시간이다.
        어차피 만료된 뒤에는 재사용 탐지가 무의미하므로 표식도 함께 사라지게 해
        Redis 에 쓰레기가 쌓이지 않도록 한다.
        """
        pipeline = self._redis.pipeline()
        pipeline.delete(self._token_key(user_id, jti))
        pipeline.srem(self._index_key(user_id), jti)
        pipeline.set(self._used_key(user_id, jti), "1", ex=max(remaining_ttl_seconds, 1))
        pipeline.execute()

    # ------------------------------------------------------------------ 폐기

    def revoke(self, user_id: int, jti: str) -> None:
        """토큰 하나를 폐기한다 (로그아웃, 회전 시 기존 토큰 제거)."""
        pipeline = self._redis.pipeline()
        pipeline.delete(self._token_key(user_id, jti))
        pipeline.srem(self._index_key(user_id), jti)
        pipeline.execute()

    def revoke_all(self, user_id: int) -> int:
        """해당 유저의 모든 Refresh Token 을 폐기한다.

        "모든 기기에서 로그아웃" 과 재사용 탐지 시 세션 전체 무효화에 쓰인다.
        인덱스에는 TTL 로 이미 사라진 jti 가 남아 있을 수 있으나,
        존재하지 않는 키에 대한 DEL 은 무해하므로 그대로 일괄 삭제한다.
        """
        index_key = self._index_key(user_id)
        # redis-py 스텁은 sync/async 반환 타입을 합쳐 두어 Awaitable 이 섞여 보인다.
        # sync 클라이언트이므로 실제로는 set 이다 (rate_limit.py 와 동일한 이유).
        jtis = cast(set[str], self._redis.smembers(index_key))

        pipeline = self._redis.pipeline()
        for jti in jtis:
            pipeline.delete(self._token_key(user_id, str(jti)))
        pipeline.delete(index_key)
        pipeline.execute()

        return len(set(jtis))
