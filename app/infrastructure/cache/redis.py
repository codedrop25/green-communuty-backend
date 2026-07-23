"""Redis 연결.

용도 (PLAN.md): Refresh Token 저장/회전, 로그인 Rate Limit.

`Redis` 클라이언트는 스레드 안전하며 내부 커넥션 풀에서 커넥션을 빌려 쓴다.
따라서 요청마다 새로 만들지 않고 모듈 단위 싱글턴으로 공유한다.
"""

from redis import ConnectionPool, Redis

from app.core.config import settings

# `def` 라우터는 threadpool worker 위에서 실행되고, worker 하나가
# 커넥션 하나를 점유할 수 있다. DB 풀과 같은 이유로 worker 수에 맞춰 잡는다.
# (PLAN.md 3-3 의 정합성 규칙을 Redis 에도 동일하게 적용)
_pool = ConnectionPool.from_url(
    settings.redis_url,
    max_connections=settings.THREADPOOL_MAX_WORKERS,
    # 토큰 해시·카운터 등 이 앱이 다루는 값은 전부 문자열이다.
    # bytes 로 받으면 호출부마다 decode 가 흩어지므로 클라이언트에서 한 번에 처리한다.
    decode_responses=True,
    # 서버 장애 시 요청이 무한정 매달리지 않도록 상한을 둔다.
    socket_connect_timeout=3,
    socket_timeout=3,
    # 유휴 커넥션이 방화벽/로드밸런서에 의해 조용히 끊기는 것을 방지한다.
    health_check_interval=30,
)

redis_client: Redis = Redis(connection_pool=_pool)


def get_redis() -> Redis:
    """Redis 클라이언트 의존성.

    싱글턴을 그대로 돌려준다. 함수로 감싸는 이유는 테스트에서
    `app.dependency_overrides` 로 교체할 수 있는 지점을 만들기 위함이다.
    """
    return redis_client
