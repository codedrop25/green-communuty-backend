"""신고 요청 및 응답 스키마."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ReportSummaryResponse(BaseModel):
    """신고 목록에서 사용하는 요약 응답."""

    # SQLAlchemy의 Report 객체를 Pydantic 응답으로 변환하도록 허용
    model_config = ConfigDict(from_attributes=True)

    # 신고 고유 식별자
    report_id: int

    # 신고한 사용자 ID, 관리자 직접 조치라면 None
    reporter_user_id: int | None

    # 신고 대상 종류 / 신고당한 게시글 또는 댓글,대댓글 ID
    report_content_type: Literal[
        "POST",
        "COMMENT",
        "USER",
    ]
    post_id: int | None
    comment_id: int | None = None

    # 신고당한 사용자 ID / 신고 카테고리 / 상세 사유
    reported_user_id: int
    report_category: str
    report_reason: str | None = None

    # 신고 처리 상태 [처리중 / 처리완료 / 신고반려]
    report_status: Literal[
        "PENDING",
        "ACCEPTED",
        "REJECTED",
    ]

    # 신고 처리 결과로 적용된 사용자 제재 [경고 / 기간제재 / 영구차단]
    user_sanction_type: (
        Literal[
            "WARNING",
            "SUSPENDED",
            "BANNED",
        ]
        | None
    ) = None

    created_at: datetime


class ReportCreateRequest(BaseModel):
    """새로운 신고 등록 요청"""

    # 신규 객체 등록 요청이므로, report_id 는 아직 생성되지 않음
    # reporter_user_id 는 임의의 data 전송을 방지하기 위해 current_user 로 확인
    report_content_type: Literal[
        "POST",
        "COMMENT",
        "USER",
    ]
    post_id: int | None
    comment_id: int | None = None

    # 사용자를 직접 신고인 경우를 제외, 컨텐츠를 신고인 경우엔
    # 해당 id 로 DB 를 조회하여 user_id 를 찾는 것이 좋다. (거짓 data 방지)
    reported_user_id: int | None = None
    report_category: str
    report_reason: str | None = None


class ReportProcessRequest(BaseModel):
    """관리자의 신고 처리 요청."""

    # 신고 승인 또는 반려
    report_status: Literal[
        "ACCEPTED",
        "REJECTED",
    ]

    # 사용자에게 적용할 제재 / 신고 반려라면 None
    user_sanction_type: (
        Literal[
            "WARNING",
            "SUSPENDED",
            "BANNED",
        ]
        | None
    ) = None

    # 기간 정지 종료 시각 - SUSPENDED일 때만 값 전달
    expires_at: datetime | None = None
