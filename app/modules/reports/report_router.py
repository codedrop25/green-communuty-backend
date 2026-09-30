"""신고 API Router."""

from fastapi import APIRouter, status

from app.common.dependencies import (
    CurrentUser,
    DbSession,
    RedisClient,
)
from app.common.pagination import PageParams, PageResponse
from app.modules.reports.report_schemas import (
    ReportCreateRequest,
    ReportProcessRequest,
    ReportSummaryResponse,
)
from app.modules.reports.report_service import ReportService

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
)


@router.get(
    "",
    response_model=PageResponse[ReportSummaryResponse],
    summary="처리 대기 신고 목록",
)
def list_reports(
    params: PageParams,
    current_user: CurrentUser,
    db: DbSession,
    redis: RedisClient,
) -> PageResponse[ReportSummaryResponse]:
    """관리자가 처리 대기 중인 신고 목록을 조회한다."""

    return ReportService(
        db=db,
        redis=redis,
    ).list_reports(
        params=params,
        current_user=current_user,
    )


@router.post(
    "",
    response_model=ReportSummaryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="신고 등록",
)
def add_report(
    request: ReportCreateRequest,
    current_user: CurrentUser,
    db: DbSession,
    redis: RedisClient,
) -> ReportSummaryResponse:
    """새로운 신고를 등록한다."""

    return ReportService(
        db=db,
        redis=redis,
    ).add_report(
        request=request,
        current_user=current_user,
    )


@router.patch(
    "/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="신고 처리",
)
def process_report(
    report_id: int,
    request: ReportProcessRequest,
    current_user: CurrentUser,
    db: DbSession,
    redis: RedisClient,
) -> None:
    """관리자가 신고를 승인하거나 반려한다."""

    ReportService(
        db=db,
        redis=redis,
    ).process_report(
        report_id=report_id,
        reviewer_user_id=current_user.user_id,
        request=request,
    )
