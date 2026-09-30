"""신고 데이터 접근 Repository."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.modules.reports.report_model import Report


class ReportRepository:
    """신고 데이터의 추가, 조회, 수정을 담당한다."""

    def __init__(self, db: Session) -> None:
        """DB 세션을 Repository 내부에 저장한다."""

        self._db = db

    # ---------------------------------------------------------------------

    @staticmethod
    def _same_reports(
        report: Report,
    ) -> list[ColumnElement[bool]]:
        """대표 신고와 동일한 대상을 찾는 조회 조건을 만든다."""

        # 같은 게시글을 대상으로 한 신고
        if report.report_content_type == "POST":
            if report.post_id is None:
                raise ValueError("게시글 신고에 post_id가 없습니다.")

            return [
                Report.report_content_type == "POST",
                Report.post_id == report.post_id,
                Report.comment_id.is_(None),
            ]

        # 같은 댓글 또는 대댓글을 대상으로 한 신고
        if report.report_content_type == "COMMENT":
            if report.post_id is None or report.comment_id is None:
                raise ValueError("댓글 신고 대상 정보가 올바르지 않습니다.")

            return [
                Report.report_content_type == "COMMENT",
                Report.post_id == report.post_id,
                Report.comment_id == report.comment_id,
            ]

        # 같은 사용자를 대상으로 한 신고
        if report.report_content_type == "USER":
            return [
                Report.report_content_type == "USER",
                (Report.reported_user_id == report.reported_user_id),
                Report.post_id.is_(None),
                Report.comment_id.is_(None),
            ]

        raise ValueError("지원하지 않는 신고 대상입니다.")

    # ---------------------------------------------------------------------

    def add_report(
        self,
        reporter_user_id: int | None,
        report_content_type: str,
        reported_user_id: int,
        report_category: str,
        post_id: int | None = None,
        post_title: str | None = None,
        post_content: str | None = None,
        comment_id: int | None = None,
        comment_content: str | None = None,
        report_reason: str | None = None,
    ) -> Report:
        """reports 테이블에 새로운 신고 내역을 저장한다."""

        # 전달받은 신고 정보로 Report 객체를 생성한다.
        report = Report(
            reporter_user_id=reporter_user_id,
            report_content_type=report_content_type,
            reported_user_id=reported_user_id,
            report_category=report_category,
            post_id=post_id,
            post_title=post_title,
            post_content=post_content,
            comment_id=comment_id,
            comment_content=comment_content,
            report_reason=report_reason,
        )

        # 생성한 객체를 DB 저장 대상으로 등록한다.
        self._db.add(report)

        # INSERT를 실행해 report_id를 발급받는다.
        # 아직 commit은 하지 않는다.
        self._db.flush()

        # DB에 저장된 최신 값을 객체에 다시 불러온다.
        self._db.refresh(report)

        return report

    # ---------------------------------------------------------------------

    def get_by_id(
        self,
        report_id: int,
    ) -> Report | None:
        """report_id로 신고 내역 한 건을 조회한다.

        신고 대상 게시글이나 댓글의 상태는 검사하지 않는다.
        """

        statement = select(Report).where(Report.report_id == report_id)

        # 한 건이면 Report를 반환하고 없으면 None을 반환한다.
        return self._db.scalars(statement).one_or_none()

    # ---------------------------------------------------------------------

    def list_reports(
        self,
        offset: int,
        limit: int,
    ) -> list[Report]:
        """처리 대기 중인 신고를 최근 접수 순서로 조회한다."""

        statement = (
            select(Report)
            # 아직 처리되지 않은 신고만 조회한다.
            .where(Report.report_status == "PENDING")
            # 최근 접수된 신고부터 정렬한다.
            .order_by(Report.created_at.desc())
            # 앞에서 offset개를 건너뛴다.
            .offset(offset)
            # 최대 limit개까지만 가져온다.
            .limit(limit)
        )

        return list(self._db.scalars(statement).all())

    # ---------------------------------------------------------------------

    def count_by_total_reports(self) -> int:
        """처리 대기 중인 전체 신고 개수를 반환한다."""

        statement = select(func.count(Report.report_id)).where(Report.report_status == "PENDING")

        return self._db.scalar(statement) or 0

    # ---------------------------------------------------------------------

    def count_by_report(
        self,
        report: Report,
    ) -> int:
        """대표 신고와 같은 대상을 신고한 전체 횟수를 계산한다."""

        # 동일 대상의 신고 건을 검색하여 누적 반영한다.
        conditions = self._same_reports(report)

        statement = select(func.count(Report.report_id)).where(*conditions)

        return self._db.scalar(statement) or 0

    # ---------------------------------------------------------------------

    def update_report(
        self,
        report: Report,
        report_status: str,
        user_sanction_type: str | None,
        reviewer_user_id: int,
        processed_at: datetime,
    ) -> int:
        """동일 대상의 PENDING 신고를 같은 결과로 일괄 변경한다."""

        # 대표 신고와 동일한 대상을 찾는 조건을 가져온다.
        conditions = self._same_reports(report)

        # 같은 대상이면서 아직 처리되지 않은 신고만 조회한다.
        statement = select(Report).where(
            Report.report_status == "PENDING",
            *conditions,
        )

        pending_reports = list(self._db.scalars(statement).all())

        # 모든 신고에 동일한 처리 결과를 적용한다.
        for pending_report in pending_reports:
            pending_report.report_status = report_status
            pending_report.user_sanction_type = user_sanction_type
            pending_report.reviewer_user_id = reviewer_user_id
            pending_report.processed_at = processed_at

        # 변경 내용을 DB에 전달한다.
        # commit은 Service에서 실행한다.
        self._db.flush()

        return len(pending_reports)
