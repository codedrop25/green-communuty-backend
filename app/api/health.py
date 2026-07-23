"""헬스체크.

`modules/` 가 아니라 `api/` 에 있는 이유: 헬스체크는 비즈니스 도메인이 아니고
API 버전과도 무관하다. 그래서 `/api/v1` prefix 없이 `/health` 로 노출한다.

**liveness 와 readiness 를 구분하는 이유:**
    - `/health/live` : 프로세스가 살아 있는가. 실패하면 오케스트레이터가 **재시작**한다.
      따라서 DB/Redis 를 확인하면 안 된다. DB 장애로 모든 앱이 재시작 루프에 빠진다.
    - `/health/ready`: 트래픽을 받을 준비가 됐는가. 실패하면 **로드밸런서에서 제외**된다.
      의존 시스템을 확인하는 것은 이쪽이다.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from redis import Redis, RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.infrastructure.cache.redis import get_redis
from app.infrastructure.database.session import get_db

router = APIRouter(prefix="/health", tags=["health"])

logger = get_logger(__name__)


class LivenessResponse(BaseModel):
    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    status: Literal["ok", "error"]
    database: Literal["ok", "error"]
    redis: Literal["ok", "error"]


@router.get("/live", response_model=LivenessResponse, summary="Liveness (프로세스 생존)")
def liveness() -> LivenessResponse:
    """의존 시스템을 확인하지 않는다 (모듈 상단 주석 참고)."""
    return LivenessResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse, summary="Readiness (DB/Redis 연결)")
def readiness(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ReadinessResponse:
    """DB 와 Redis 에 실제 질의를 보내 확인한다.

    커넥션 객체의 존재만 보면 "풀에는 있지만 실제로는 끊긴" 상태를 놓친다.
    하나라도 실패하면 503 을 반환해 로드밸런서가 이 인스턴스를 제외하게 한다.
    """
    database_ok = _check_database(db)
    redis_ok = _check_redis(redis)
    healthy = database_ok and redis_ok

    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ok" if healthy else "error",
        database="ok" if database_ok else "error",
        redis="ok" if redis_ok else "error",
    )


def _check_database(db: Session) -> bool:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.warning("healthcheck_database_failed", exc_info=True)
        return False
    return True


def _check_redis(redis: Redis) -> bool:
    try:
        redis.ping()
    except RedisError:
        logger.warning("healthcheck_redis_failed", exc_info=True)
        return False
    return True
