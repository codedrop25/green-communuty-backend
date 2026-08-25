"""FastAPI 애플리케이션 생성.

조립 순서와 그 이유를 한 곳에서 볼 수 있도록, 설정은 전부 함수로 분리해 두었다.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from anyio import to_thread
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging_config import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware
from app.modules.posts.post_like_sync import post_like_sync

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """앱 시작/종료 훅."""
    configure_logging()

    # PLAN.md 3-3: `def` 라우터가 실행되는 threadpool 크기를 설정에 맞춘다.
    # AnyIO 기본값은 40 이며, DB 커넥션 총량과의 정합성은 Settings 가 이미 검증했다.
    to_thread.current_default_thread_limiter().total_tokens = settings.THREADPOOL_MAX_WORKERS

    logger.info(
        "application_started",
        environment=settings.ENVIRONMENT,
        threadpool_workers=settings.THREADPOOL_MAX_WORKERS,
        db_pool_capacity=settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW,
    )

    # 8.25) 추가: 좋아요 5분 동기화 작업 시작
    post_like_sync_task = asyncio.create_task(post_like_sync())

    # 8.25) 변경: yield 를 try 로 감쌈
    try:
        yield
    finally:
        post_like_sync_task.cancel()

        with suppress(asyncio.CancelledError):  # 코드 안에서 해당 에러가 일어날 경우 무시해라
            await post_like_sync_task

        logger.info("application_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        lifespan=lifespan,
        # PLAN.md 8-1: 운영에서는 API 문서를 노출하지 않는다.
        # 엔드포인트/스키마 전체가 공격자에게 정찰 자료가 되기 때문이다.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    _register_middleware(app)
    register_exception_handlers(app)
    _register_routers(app)

    return app


def _register_middleware(app: FastAPI) -> None:
    """미들웨어는 **등록의 역순**으로 실행된다.

    따라서 `RequestContextMiddleware` 를 나중에 등록해 가장 바깥에 두면,
    CORS 처리까지 포함한 모든 요청이 request_id 를 갖게 된다.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        # Refresh Token 쿠키를 주고받으려면 필수다 (PLAN.md 4-4).
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # 클라이언트가 오류 신고 시 참조할 수 있도록 노출한다.
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)


def _register_routers(app: FastAPI) -> None:
    # 헬스체크는 버전 prefix 없이 노출한다 (오케스트레이터가 참조하는 고정 경로).
    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)


app = create_app()
