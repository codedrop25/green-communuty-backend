"""요청 스코프 미들웨어.

`RequestContextMiddleware` 하나가 두 가지를 담당한다.
    1. 요청마다 `request_id` 를 부여하고 로그 컨텍스트에 바인딩 (분산 추적의 최소 단위)
    2. 요청 완료 로그 (메서드/경로/상태/소요시간)

`request_id` 는 응답 헤더 `X-Request-ID` 로도 돌려준다.
사용자가 오류를 신고할 때 이 값 하나로 서버 로그를 특정할 수 있게 하기 위함이다.
"""

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging_config import get_logger

REQUEST_ID_HEADER = "X-Request-ID"

logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # 게이트웨이/프론트가 이미 부여한 ID 가 있으면 이어받아 요청 흐름을 끊지 않는다.
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex

        # 이전 요청의 컨텍스트가 남아 있을 수 있으므로 비우고 시작한다.
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # 예외 핸들러가 응답 본문에 request_id 를 실을 수 있도록 state 에도 둔다.
        request.state.request_id = request_id

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # 여기서 로그만 남기고 다시 던진다.
            # 응답 변환은 전역 예외 핸들러의 책임이며, 이 미들웨어가 대신하지 않는다.
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration_ms, 2),
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
