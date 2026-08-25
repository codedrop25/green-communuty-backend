"""테스트 공통 픽스처 (PLAN.md 10-2).

세 가지 원칙:

1. **컨테이너는 세션당 1회만** 띄운다.
   테스트마다 MySQL 컨테이너를 만들면 전체 실행이 수 분 단위로 늘어난다.

2. 테스트 격리는 컨테이너 재생성이 아니라 **트랜잭션 롤백**으로 한다.
   각 테스트는 자기 트랜잭션 안에서 돌고 끝나면 되감기므로 서로 간섭하지 않는다.

3. 앱에는 `settings` 를 바꾸는 대신 **의존성 오버라이드**로 연결한다.
   `app.core.config.settings` 는 모듈 import 시점에 만들어지는 싱글턴이라,
   픽스처에서 환경 변수를 바꿔봐야 이미 늦다. 대신 `get_db` / `get_redis` 를
   컨테이너에 연결된 것으로 교체한다. 엔진 생성은 지연 연결이므로
   기본 설정의 접속 정보가 유효하지 않아도 import 자체는 문제없다.

SQLite 로 대체하지 않는 이유: 타입/FK/트랜잭션 동작이 MySQL 과 달라
"테스트는 통과하는데 운영에서 깨지는" 상황을 만든다.
"""

from collections.abc import Callable, Generator
from typing import Any, TypeVar, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis import Redis
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.mysql import MySqlContainer
from testcontainers.redis import RedisContainer

F = TypeVar("F", bound=Callable[..., Any])

fixture = cast(
    Callable[[F], F],
    pytest.fixture(),
)

session_fixture = cast(
    Callable[[F], F],
    pytest.fixture(scope="session"),
)


@session_fixture
def mysql_container() -> Generator[MySqlContainer]:
    """세션 전체에서 공유하는 MySQL 컨테이너.

    이모지 저장을 검증해야 하므로 서버 기본 문자셋을 utf8mb4 로 띄운다.
    """
    # dialect 를 지정하지 않으면 `mysql://` (MySQLdb 드라이버) URL 이 나온다.
    # 운영과 다른 드라이버로 테스트하면 의미가 없으므로 앱과 동일하게 PyMySQL 을 쓴다.
    container = MySqlContainer("mysql:8.0", dialect="pymysql").with_command(
        "--character-set-server=utf8mb4 "
        "--collation-server=utf8mb4_0900_ai_ci "
        "--default-time-zone=+00:00"
    )
    with container as started:
        yield started


@fixture
def redis_container() -> Generator[RedisContainer]:
    with RedisContainer("redis:7-alpine") as container:
        yield container


@fixture
def engine(mysql_container: MySqlContainer) -> Generator[Engine]:
    """테이블이 생성된 테스트 엔진.

    스키마는 Alembic 이 아니라 `Base.metadata.create_all` 로 만든다.
    마이그레이션 이력 재생은 느리고, 여기서 검증하려는 것은 마이그레이션이 아니라
    애플리케이션 동작이기 때문이다.
    (마이그레이션과 모델의 일치 여부는 `alembic check` 로 따로 검증한다)
    """
    from app.infrastructure.database.model_registry import Base

    url = f"{mysql_container.get_connection_url()}?charset=utf8mb4"
    test_engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(test_engine)

    yield test_engine

    test_engine.dispose()


@fixture
def db_session(engine: Engine) -> Generator[Session]:
    """테스트 하나당 트랜잭션 하나.

    바깥 트랜잭션을 열어 두고 그 위에서 세션을 돌린 뒤 통째로 롤백한다.
    서비스 코드가 `commit()` 을 호출해도(우리 설계상 반드시 호출한다)
    그것은 SAVEPOINT 커밋이 되므로, 바깥 트랜잭션을 롤백하면 전부 사라진다.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, expire_on_commit=False)()
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess: Session, _trans: object) -> None:
        # 서비스의 commit() 으로 SAVEPOINT 가 닫히면 즉시 새로 연다.
        # 이것이 없으면 첫 commit 이후의 쿼리가 바깥 트랜잭션에 직접 쓰여
        # 롤백으로 되돌릴 수 없게 된다.
        if not sess.in_nested_transaction() and connection.in_transaction():
            sess.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@fixture
def redis_client(redis_container: RedisContainer) -> Generator[Redis]:
    """테스트마다 비워지는 Redis 클라이언트.

    컨테이너는 재사용하고 데이터만 비운다 (재생성은 느리다).
    """
    client: Redis = Redis(
        host=redis_container.get_container_host_ip(),
        port=int(redis_container.get_exposed_port(6379)),
        decode_responses=True,
    )
    client.flushdb()

    yield client

    client.flushdb()
    client.close()


@fixture
def app(db_session: Session, redis_client: Redis) -> Generator[FastAPI]:
    """DB/Redis 의존성이 테스트용으로 교체된 앱."""
    from app.infrastructure.cache.redis import get_redis
    from app.infrastructure.database.session import get_db
    from app.main import create_app

    fastapi_app = create_app()

    def _override_get_db() -> Generator[Session]:
        # 롤백 경계를 픽스처가 쥐고 있어야 하므로 여기서 close 하지 않는다.
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    fastapi_app.dependency_overrides[get_redis] = lambda: redis_client

    yield fastapi_app

    fastapi_app.dependency_overrides.clear()


@fixture
def client(app: FastAPI) -> Generator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
