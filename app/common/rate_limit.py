"""Redis 기반 고정 윈도우 Rate Limiter (PLAN.md 4-3).

적용 대상은 로그인 엔드포인트 하나뿐이다. 범용 Rate Limiting 은 범위 밖이므로
정교한 알고리즘(sliding window, token bucket) 대신 가장 단순한 고정 윈도우를 쓴다.

고정 윈도우는 경계 시점에 최대 2배까지 허용되는 약점이 있지만,
brute-force 를 "무제한"에서 "분당 몇 회"로 낮추는 목적에는 충분하다.
"""

from dataclasses import dataclass
from typing import cast

from redis import Redis


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    current: int
    retry_after: int
    """차단된 경우 재시도까지 남은 초. 허용된 경우 0."""


class RateLimiter:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def hit(self, key: str, *, max_attempts: int, window_seconds: int) -> RateLimitResult:
        """카운터를 1 증가시키고 허용 여부를 판정한다.

        INCR 와 EXPIRE 를 파이프라인으로 묶어 왕복을 한 번으로 줄인다.
        첫 요청에서만 TTL 을 걸어야 하므로 EXPIRE 에 `nx=True` 를 준다.
        이것이 없으면 매 요청마다 TTL 이 갱신되어 윈도우가 영원히 끝나지 않고,
        한 번 차단된 사용자가 영구 차단된다.
        """
        pipeline = self._redis.pipeline()
        pipeline.incr(key)
        pipeline.expire(key, window_seconds, nx=True)
        current = int(pipeline.execute()[0])

        if current <= max_attempts:
            return RateLimitResult(allowed=True, current=current, retry_after=0)

        # TTL 조회 실패(-1: TTL 없음, -2: 키 없음)에 대비해 윈도우 값으로 보정한다.
        # redis-py 의 타입 스텁은 sync/async 클라이언트를 하나의 반환 타입으로 합쳐 두어
        # sync 사용 시에도 Awaitable 이 섞인 것으로 보인다. 실제로는 int 이므로 cast 한다.
        ttl = cast(int, self._redis.ttl(key))
        retry_after = ttl if ttl > 0 else window_seconds
        return RateLimitResult(allowed=False, current=current, retry_after=retry_after)

    def reset(self, key: str) -> None:
        """카운터를 초기화한다 (예: 로그인 성공 시)."""
        self._redis.delete(key)
