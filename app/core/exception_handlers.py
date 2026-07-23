"""전역 예외 → 표준 응답 변환.

모든 실패 응답이 `ErrorResponse` 한 가지 모양을 갖도록 이 파일에서 수렴시킨다.
클라이언트가 "성공은 제각각, 실패는 하나"라는 단순한 규칙으로 처리할 수 있게 된다.

로그 레벨 원칙:
    - 4xx (클라이언트 잘못)  → WARNING. 정상 운영 중에도 발생하는 이벤트다.
    - 5xx (서버 잘못)        → ERROR + 스택트레이스. 알림을 걸어야 하는 이벤트다.
"""

from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.common.schemas import ErrorResponse
from app.core.config import settings
from app.core.exceptions import AppError, RateLimitedError
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def _request_id(request: Request) -> str | None:
    """미들웨어가 넣어둔 요청 ID. 미들웨어보다 앞단에서 실패하면 없을 수 있다."""
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else None


def _build_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    detail: object | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        code=code,
        message=message,
        detail=detail,
        request_id=_request_id(request),
    )
    return JSONResponse(
        status_code=status_code,
        # `exclude_none` 없이 내보내 응답 형태를 항상 동일하게 유지한다.
        content=payload.model_dump(mode="json"),
        headers=headers,
    )


async def app_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """애플리케이션이 의도적으로 발생시킨 예외."""
    assert isinstance(exc, AppError)

    headers: dict[str, str] | None = None
    if isinstance(exc, RateLimitedError):
        # 클라이언트가 언제 재시도해야 하는지 알 수 있도록 표준 헤더로 알린다.
        headers = {"Retry-After": str(exc.retry_after)}

    log = logger.bind(
        code=exc.code,
        status_code=exc.status_code,
        path=request.url.path,
        method=request.method,
    )
    if exc.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
        log.error("app_error", exc_info=exc)
    else:
        log.warning("app_error", message=exc.message)

    return _build_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        detail=exc.detail,
        headers=headers,
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Pydantic 요청 검증 실패 (422).

    FastAPI 기본 응답은 `{"detail": [...]}` 형태라 다른 오류와 모양이 다르다.
    어떤 필드가 왜 틀렸는지는 유지하면서 포맷만 통일한다.
    """
    assert isinstance(exc, RequestValidationError)

    errors: list[dict[str, Any]] = [
        {
            # loc 은 ("body", "email") 같은 튜플이다. 앞의 위치 구분자를 떼고 필드명만 남긴다.
            "field": ".".join(str(part) for part in error["loc"][1:]) or str(error["loc"][0]),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]

    logger.warning(
        "validation_error",
        path=request.url.path,
        method=request.method,
        errors=errors,
    )
    return _build_response(
        request,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        code="VALIDATION_ERROR",
        message="요청 값이 올바르지 않습니다.",
        detail=errors,
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """프레임워크가 발생시킨 HTTPException (404 라우트 없음, 405 등).

    앱 코드는 `AppError` 을 쓰지만, Starlette 내부에서 나는 것들은 이 경로를 탄다.
    """
    assert isinstance(exc, StarletteHTTPException)

    status = HTTPStatus(exc.status_code)
    return _build_response(
        request,
        status_code=exc.status_code,
        code=status.name,
        message=str(exc.detail),
        headers=dict(exc.headers) if exc.headers else None,
    )


async def sqlalchemy_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """처리되지 않은 DB 오류.

    별도로 잡는 이유는 두 가지다.
      1. 스택트레이스에 SQL 과 파라미터가 섞여 있어 그대로 클라이언트에 노출하면 안 된다.
      2. DB 오류는 일반 500 과 구분해서 알림을 걸 수 있어야 한다.
    """
    logger.error(
        "database_error",
        path=request.url.path,
        method=request.method,
        exc_info=exc,
    )
    return _build_response(
        request,
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        code="DATABASE_ERROR",
        message="데이터 처리 중 오류가 발생했습니다.",
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """최후의 안전망.

    내부 예외 메시지를 그대로 내보내면 경로·쿼리·라이브러리 버전 같은
    정보가 새어 나가므로, 운영에서는 고정 문구만 반환하고 상세는 로그에만 남긴다.
    """
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        exc_info=exc,
    )
    return _build_response(
        request,
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        code="INTERNAL_ERROR",
        message="서버 내부 오류가 발생했습니다.",
        # 로컬/개발에서만 원인을 노출해 디버깅을 돕는다.
        detail=None if settings.is_production else repr(exc),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """`main.py` 에서 호출한다.

    등록 순서가 아니라 **예외 클래스의 구체성**으로 매칭되므로,
    `Exception` 을 함께 등록해도 구체적인 핸들러가 우선한다.
    """
    app.add_exception_handler(AppError, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
