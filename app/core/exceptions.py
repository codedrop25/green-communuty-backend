"""애플리케이션 예외 계층.

설계 (PLAN.md 3-1):
    - 서비스/도메인 코드는 `HTTPException` 을 직접 쓰지 않고 이 예외들만 발생시킨다.
      HTTP 는 전달 계층의 관심사이므로, 도메인 로직이 그것을 알 필요가 없다.
    - HTTP 상태 코드로의 변환은 `exception_handlers.py` 가 전담한다.
    - `code` 는 클라이언트가 분기에 사용할 **안정적인 식별자**다.
      `message` 는 사람이 읽는 문구이므로 자유롭게 바꿔도 되지만, `code` 는 계약이다.
"""

from http import HTTPStatus


class AppError(Exception):
    """모든 애플리케이션 예외의 루트.

    하위 클래스는 `status_code` 와 `code` 를 클래스 속성으로 고정한다.
    """

    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    code: str = "INTERNAL_ERROR"
    message: str = "서버 내부 오류가 발생했습니다."

    def __init__(self, message: str | None = None, *, detail: object | None = None) -> None:
        self.message = message or self.message
        # HTTPStatus 는 IntEnum 이라 로그에 `<HTTPStatus.NOT_FOUND: 404>` 로 찍힌다.
        # 순수 int 로 정규화해 로그와 응답 모두 숫자만 남게 한다.
        self.status_code = int(self.status_code)
        # 구조화된 부가 정보 (예: 어떤 필드가 왜 틀렸는지). 응답과 로그에 함께 실린다.
        self.detail = detail
        super().__init__(self.message)


# --------------------------------------------------------------------- 400 계열


class BadRequestError(AppError):
    status_code = HTTPStatus.BAD_REQUEST
    code = "BAD_REQUEST"
    message = "잘못된 요청입니다."


class UnauthorizedError(AppError):
    """인증 실패 — 신원을 확인할 수 없음."""

    status_code = HTTPStatus.UNAUTHORIZED
    code = "UNAUTHORIZED"
    message = "인증이 필요합니다."


class ForbiddenError(AppError):
    """인가 실패 — 신원은 확인됐으나 권한이 없음.

    401 과 403 을 섞어 쓰면 클라이언트가 "재로그인하면 되는지"를 판단할 수 없다.
    """

    status_code = HTTPStatus.FORBIDDEN
    code = "FORBIDDEN"
    message = "접근 권한이 없습니다."


class NotFoundError(AppError):
    status_code = HTTPStatus.NOT_FOUND
    code = "NOT_FOUND"
    message = "요청한 리소스를 찾을 수 없습니다."


class ConflictError(AppError):
    """중복 등 현재 상태와 충돌하는 요청 (예: 이미 존재하는 이메일)."""

    status_code = HTTPStatus.CONFLICT
    code = "CONFLICT"
    message = "요청이 현재 상태와 충돌합니다."


class RateLimitedError(AppError):
    """요청 한도 초과 (PLAN.md 4-3).

    `retry_after` 는 `Retry-After` 헤더로도 내려간다.
    """

    status_code = HTTPStatus.TOO_MANY_REQUESTS
    code = "RATE_LIMITED"
    message = "요청이 너무 많습니다. 잠시 후 다시 시도해주세요."

    def __init__(
        self,
        message: str | None = None,
        *,
        retry_after: int,
        detail: object | None = None,
    ) -> None:
        super().__init__(message, detail=detail)
        self.retry_after = retry_after


# --------------------------------------------------------------------- 500 계열


class ServiceUnavailableError(AppError):
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    code = "SERVICE_UNAVAILABLE"
    message = "서비스를 일시적으로 사용할 수 없습니다."


class StorageNotConfiguredError(ServiceUnavailableError):
    """S3 설정 없이 스토리지 기능을 호출한 경우.

    설정 누락은 서버 문제이므로 4xx 가 아니라 503 으로 다룬다.
    """

    code = "STORAGE_NOT_CONFIGURED"
    message = "오브젝트 스토리지가 설정되지 않았습니다."
