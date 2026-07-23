"""구조화 로깅 설정 (structlog).

목표:
    - 운영에서는 **JSON 한 줄 = 이벤트 하나**. 로그 수집기가 그대로 파싱할 수 있어야 한다.
    - 로컬에서는 사람이 읽을 수 있는 컬러 출력.
    - 모든 로그에 `request_id` 가 붙어 하나의 요청을 추적할 수 있어야 한다.
    - **비밀번호/토큰이 절대 로그에 남지 않아야 한다** (PLAN.md 8-2).
    - uvicorn / SQLAlchemy 등 표준 logging 사용 라이브러리의 출력도 같은 포맷으로 나와야 한다.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from app.core.config import settings

# 값이 마스킹되어야 하는 키 (소문자 비교).
# 부분 일치로 검사하므로 `user_password`, `X-Refresh-Token` 같은 변형도 함께 잡힌다.
SENSITIVE_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "authorization",
    "cookie",
    "api_key",
    "apikey",
)

MASK = "***"

# 마스킹 값이 무한 재귀에 빠지지 않도록 중첩 깊이를 제한한다.
_MAX_MASK_DEPTH = 6


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def _mask_value(value: Any, depth: int = 0) -> Any:
    """중첩된 dict/list 안의 민감 키까지 재귀적으로 마스킹한다."""
    if depth >= _MAX_MASK_DEPTH:
        return value
    if isinstance(value, dict):
        return {
            k: (MASK if _is_sensitive(str(k)) else _mask_value(v, depth + 1))
            for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return [_mask_value(item, depth + 1) for item in value]
    return value


def mask_sensitive_data(_logger: object, _method_name: str, event_dict: EventDict) -> EventDict:
    """민감 정보 마스킹 프로세서.

    로그를 남기는 쪽에서 매번 신경 쓰게 하면 언젠가 반드시 새어 나간다.
    파이프라인 마지막 단계에서 일괄 처리해 실수의 여지를 없앤다.
    """
    return {
        key: (MASK if _is_sensitive(str(key)) else _mask_value(value))
        for key, value in event_dict.items()
    }


def _build_processors() -> list[Processor]:
    """공유 프로세서 체인.

    `merge_contextvars` 가 미들웨어에서 바인딩한 `request_id` 를 모든 로그에 주입한다.
    """
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        mask_sensitive_data,
    ]


def configure_logging() -> None:
    """앱 기동 시 1회 호출한다 (`main.py`).

    structlog 과 표준 logging 을 하나의 파이프라인으로 합쳐,
    uvicorn/SQLAlchemy 로그도 동일한 포맷·마스킹 규칙을 따르게 한다.
    """
    shared_processors = _build_processors()

    renderer: Processor = (
        structlog.processors.JSONRenderer(ensure_ascii=False)
        if settings.is_production
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )

    structlog.configure(
        processors=[
            *shared_processors,
            # stdlib 핸들러로 넘기기 위한 어댑터. 반드시 체인의 마지막이어야 한다.
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 표준 logging 으로 들어온 레코드(uvicorn 등)도 같은 프로세서를 태운다.
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    # 로그에 한글이 포함되므로 출력 스트림 인코딩을 UTF-8 로 고정한다.
    # Windows 콘솔 기본값(cp949)에서는 한글 로그가 깨지거나 UnicodeEncodeError 가 난다.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    # 재설정 시 핸들러가 중복 등록되어 로그가 두 번 찍히는 것을 막는다.
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if settings.DB_ECHO else logging.INFO)

    # uvicorn 은 자체 핸들러를 달아 두므로 제거하고 루트로 위임시킨다.
    # 그대로 두면 같은 로그가 평문과 JSON 으로 두 번 출력된다.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    # 접근 로그는 자체 미들웨어에서 request_id 와 함께 남기므로 중복을 끈다.
    logging.getLogger("uvicorn.access").disabled = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
