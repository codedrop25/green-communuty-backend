"""모듈 간 공유 스키마.

PLAN.md 3-6: 성공 응답에는 공통 래퍼를 씌우지 않는다 (OpenAPI 스키마를 단순하게 유지).
**에러 응답만** 이 포맷으로 표준화한다.
"""

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """모든 실패 응답의 단일 포맷.

    클라이언트는 `code` 로 분기하고 `message` 를 사용자에게 보여준다.
    `message` 문구는 언제든 바뀔 수 있지만 `code` 는 계약이므로 유지된다.
    """

    code: str = Field(description="기계가 읽는 안정적인 오류 식별자", examples=["NOT_FOUND"])
    message: str = Field(description="사람이 읽는 오류 설명")
    detail: object | None = Field(
        default=None,
        description="구조화된 부가 정보 (예: 검증 실패 필드 목록)",
    )
    request_id: str | None = Field(
        default=None,
        description="서버 로그 추적용 요청 ID. 오류 신고 시 이 값을 전달하면 된다.",
    )
