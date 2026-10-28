"""브라우저 연동 검증용 서버: python -m tests.manual_auth_server.

Docker의 임시 MySQL/Redis만 사용하고 종료 시 컨테이너를 정리한다.
개발 DB 동기화와 스케줄러를 실행하지 않는다.
Next 서버의 BACKEND_API_URL을 http://127.0.0.1:8001/api/v1 로 지정한다.
"""

from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager
from secrets import token_urlsafe

import uvicorn
from fastapi import FastAPI
from pydantic import SecretStr
from redis import Redis
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.mysql import MySqlContainer
from testcontainers.redis import RedisContainer

from app.core.config import settings
from app.infrastructure.cache.redis import get_redis
from app.infrastructure.database.model_registry import Base
from app.infrastructure.database.session import get_db
from app.main import create_app


@asynccontextmanager
async def test_lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    yield


def main() -> None:
    # Test tokens must never authenticate against a development/production database.
    settings.SECRET_KEY = SecretStr(token_urlsafe(48))
    with (
        MySqlContainer("mysql:8.0", dialect="pymysql") as mysql,
        RedisContainer("redis:7-alpine") as redis,
    ):
        engine = create_engine(f"{mysql.get_connection_url()}?charset=utf8mb4")
        Base.metadata.create_all(engine)
        sessions = sessionmaker(engine, expire_on_commit=False)
        cache: Redis = Redis(
            host=redis.get_container_host_ip(),
            port=int(redis.get_exposed_port(6379)),
            decode_responses=True,
        )

        def database() -> Generator[Session]:
            with sessions() as session:
                yield session

        app = create_app()
        app.router.lifespan_context = test_lifespan
        app.dependency_overrides[get_db] = database
        app.dependency_overrides[get_redis] = lambda: cache
        try:
            uvicorn.run(app, host="127.0.0.1", port=8001, access_log=False)
        finally:
            cache.close()
            engine.dispose()


if __name__ == "__main__":
    main()
