"""DB 엔진 / 세션 / 요청 스코프 의존성.

트랜잭션 경계 설계 (PLAN.md 3-4) — 이 파일에서 가장 중요한 결정:

    `get_db` 는 commit 하지 않는다. commit 은 **Service 계층**의 책임이다.

    FastAPI 0.106 이후 `yield` 의존성의 teardown 코드는 **응답이 클라이언트로 전송된 뒤**
    실행된다. 따라서 여기서 commit 하면 아래 순서가 된다.

        라우터 return → 직렬화 → 200 응답 전송 → commit() 실행
                                                  └─ 여기서 실패하면 이미 늦었다

    클라이언트는 200 과 정상 데이터를 받았는데 DB 는 롤백된 상태가 되고,
    전역 예외 핸들러도 개입할 수 없다. 그래서 commit 을 라우터 도달 전으로 끌어올린다.

    여기서는 세션 수명(생성/반납)과 미처리 예외에 대한 **안전망 rollback** 만 담당한다.
"""

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# MySQL 의 기본 wait_timeout 은 8시간이다. 그보다 짧게 잡아 커넥션을 선제 재생성한다.
POOL_RECYCLE_SECONDS = 3600

engine: Engine = create_engine(
    settings.database_url,
    # --- 커넥션 풀 (PLAN.md 7-2) ---
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    # 빌려주기 직전에 SELECT 1 로 살아있는지 확인한다.
    # 없으면 트래픽이 없던 새벽 이후 첫 요청이 "MySQL server has gone away" 로 실패한다.
    pool_pre_ping=True,
    pool_recycle=POOL_RECYCLE_SECONDS,
    echo=settings.DB_ECHO,
)


@event.listens_for(engine, "connect")
def _set_session_timezone(dbapi_connection: Any, connection_record: Any) -> None:
    """커넥션마다 세션 타임존을 UTC 로 고정한다.

    `server_default=func.now()` 는 MySQL 의 CURRENT_TIMESTAMP 로 변환되는데,
    이 값은 **세션 타임존**을 따른다. 서버/컨테이너마다 타임존이 다르면
    같은 테이블에 서로 다른 기준의 시각이 섞여 들어가 추적이 불가능해진다.
    """
    with dbapi_connection.cursor() as cursor:
        cursor.execute("SET SESSION time_zone = '+00:00'")


SessionLocal = sessionmaker(
    bind=engine,
    # autoflush=True,
    # autocommit=True,          # 8.25) SQLAlchemy 2.x 부터는 지원하지 않는 코드
    # commit 이후에도 로드된 속성을 그대로 쓰기 위해 만료시키지 않는다.
    # 기본값(True)이면 Service 의 commit 직후 응답 직렬화 시점에 재조회가 발생하고,
    # 세션이 이미 닫혔다면 DetachedInstanceError 로 터진다.
    expire_on_commit=False,
)


def get_db() -> Generator[Session]:
    """요청 스코프 DB 세션 의존성.

    commit 은 하지 않는다 (모듈 상단 주석 참고).
    Service 가 commit 하지 않은 변경은 `close()` 시점에 자동으로 롤백되므로,
    "commit 을 빠뜨리면 저장되지 않는다"가 기본 동작이 된다.
    """
    session = SessionLocal()
    try:
        yield session
    except Exception:
        # 예외가 전역 핸들러로 빠져나가기 전에 트랜잭션을 정리한다.
        # 이것이 없으면 커넥션이 실패한 트랜잭션을 물고 풀로 반납될 수 있다.
        session.rollback()
        raise
    finally:
        session.close()
