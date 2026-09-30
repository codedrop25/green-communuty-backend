"""신고 기능 Service."""

from datetime import UTC, datetime

from redis import Redis
from sqlalchemy.orm import Session

from app.common.dependencies import CurrentUser
from app.common.pagination import PageParams, PageResponse
from app.core.exceptions import NotFoundError
from app.modules.comments.comment_repository import CommentRepository
from app.modules.posts.post_repository import PostRepository
from app.modules.reports.report_model import Report
from app.modules.reports.report_repository import ReportRepository
from app.modules.reports.report_schemas import (
    ReportCreateRequest,
    ReportProcessRequest,
    ReportSummaryResponse,
)
from app.modules.users.user_sanctions_repository import (
    UserSanctionRepository,
)


class ReportService:
    """신고 접수 및 관리자의 신고 처리를 담당한다."""

    def __init__(self, redis: Redis, db: Session) -> None:
        """신고 처리에 필요한 Repository를 준비한다."""
        self._db = db
        self._report_repository = ReportRepository(db)
        self._post_repository = PostRepository(db, redis)
        self._comment_repository = CommentRepository(db)
        self._user_sanctions_repository = UserSanctionRepository(db)

    # ---------------------------------------------------------------------

    def _validate_report(
        self,
        report_content_type: str,
        post_id: int | None,
        comment_id: int | None,
        reported_user_id: int | None,
        report_status: str | None = None,
    ) -> tuple[
        int,
        str | None,
        str | None,
        str | None,
    ]:
        """신고 대상을 검사하고 작성자와 콘텐츠를 반환한다.
        반환 순서:
        reported_user_id,
        post_title,
        post_content,
        comment_content
        """

        # 기존 신고를 처리하는 경우에만 PENDING인지 확인한다.
        # 새로운 신고 등록에서는 report_status가 None이다.
        if report_status is not None and report_status != "PENDING":
            raise ValueError("이미 처리된 신고입니다.")

        # 게시글 신고
        if report_content_type == "POST":
            # 게시글 신고에는 post_id만 있어야 한다.
            if post_id is None or comment_id is not None:
                raise ValueError("게시글 신고 대상 정보가 올바르지 않습니다.")

            # 삭제 또는 숨김 상태를 포함해 게시글을 조회한다.
            post = self._post_repository.get_any_by_id(post_id)

            if post is None:
                raise NotFoundError("신고 대상 게시글을 찾을 수 없습니다.")

            # 신고 대상 사용자 ID는 실제 게시글 작성자 ID다.
            return (
                post.author_id,
                post.post_title,
                post.post_content,
                None,
            )

        # 댓글 또는 대댓글 신고
        if report_content_type == "COMMENT":
            # 댓글 신고에는 post_id와 comment_id가 필요하다.
            if post_id is None or comment_id is None:
                raise ValueError("댓글 신고 대상 정보가 올바르지 않습니다.")

            # 현재는 삭제되지 않은 댓글만 조회한다.
            # 삭제·숨김 댓글까지 조회하려면
            # CommentRepository에 get_any_by_id()가 필요하다.
            comment = self._comment_repository.get_by_id(comment_id)

            # 댓글 객체를 사용하기 전에 None부터 검사한다.
            if comment is None:
                raise NotFoundError("신고 대상 댓글을 찾을 수 없습니다.")

            # 요청한 게시글과 실제 댓글의 게시글을 비교한다.
            if comment.post_id != post_id:
                raise ValueError("댓글이 해당 게시글에 속하지 않습니다.")

            # 댓글이 속한 게시글을 상태와 관계없이 조회한다.
            post = self._post_repository.get_any_by_id(comment.post_id)

            if post is None:
                raise NotFoundError("댓글이 작성된 게시글을 찾을 수 없습니다.")

            # 댓글 작성자가 신고 대상 사용자다.
            return (
                comment.author_id,
                post.post_title,
                None,
                comment.comment_content,
            )

        # 사용자 자체 신고
        if report_content_type == "USER":
            # 사용자 신고에는 게시글과 댓글 ID가 없어야 한다.
            if post_id is not None or comment_id is not None:
                raise ValueError("사용자 신고 대상 정보가 올바르지 않습니다.")

            if reported_user_id is None:
                raise ValueError("신고 대상 사용자 정보가 필요합니다.")

            # 사용자 신고에는 콘텐츠 정보가 없다.
            return (
                reported_user_id,
                None,
                None,
                None,
            )

        raise ValueError("지원하지 않는 신고 대상입니다.")

    # ---------------------------------------------------------------------

    def add_report(
        self,
        request: ReportCreateRequest,
        current_user: CurrentUser,
    ) -> ReportSummaryResponse:
        """신고 대상을 검사하고 새로운 신고를 등록한다."""

        # 실제 콘텐츠를 조회해 작성자와 내용을 가져온다.
        (
            reported_user_id,
            post_title,
            post_content,
            comment_content,
        ) = self._validate_report(
            report_content_type=request.report_content_type,
            post_id=request.post_id,
            comment_id=request.comment_id,
            reported_user_id=request.reported_user_id,
        )

        try:
            # 신고 당시 콘텐츠 정보를 함께 저장한다.
            report = self._report_repository.add_report(
                reporter_user_id=current_user.user_id,
                report_content_type=request.report_content_type,
                post_id=request.post_id,
                post_title=post_title,
                post_content=post_content,
                comment_id=request.comment_id,
                comment_content=comment_content,
                # 요청값이 아니라 실제 작성자 ID를 저장한다.
                reported_user_id=reported_user_id,
                report_category=request.report_category,
                report_reason=request.report_reason,
            )
            self._db.commit()

        except Exception:
            self._db.rollback()
            raise

        return ReportSummaryResponse.model_validate(report)

    # ---------------------------------------------------------------------

    def list_reports(
        self,
        params: PageParams,
        current_user: CurrentUser,
    ) -> PageResponse[ReportSummaryResponse]:
        """관리자가 처리 대기 중인 신고 목록을 조회한다."""

        # TODO: 관리자 권한 검사 추가 필요함
        _ = current_user

        reports = self._report_repository.list_reports(
            offset=params.offset,
            limit=params.size,
        )

        total = self._report_repository.count_by_total_reports()

        items = [ReportSummaryResponse.model_validate(report) for report in reports]

        return PageResponse[ReportSummaryResponse].create(
            items=items,
            total=total,
            params=params,
        )

    # ---------------------------------------------------------------------

    def _hide_reported_content(
        self,
        report: Report,
    ) -> None:
        """신고 대상 게시글 또는 댓글을 HIDDEN 상태로 변경한다."""

        # 게시글 숨김 처리
        if report.report_content_type == "POST":
            if report.post_id is None:
                raise ValueError("신고 대상 게시글 ID가 없습니다.")

            # PUBLISHED 게시글만 HIDDEN으로 변경한다.
            # 이미 DELETED라면 삭제 상태를 유지한다.
            self._post_repository.hide_if_published(post_id=report.post_id)
            return

        # # 댓글 또는 대댓글 숨김 처리
        # if report.report_content_type == "COMMENT":
        #     if report.comment_id is None:
        #         raise ValueError(
        #             "신고 대상 댓글 ID가 없습니다."
        #         )

        #     # PUBLISHED 댓글만 HIDDEN으로 변경한다.
        #     # 이미 DELETED라면 삭제 상태를 유지한다.
        #     self._comment_repository.hide_if_published(
        #         comment_id=report.comment_id
        #     )
        #     return

        # TODO: 아래 코드 comment_repository.py 에 붙인 후 위 코드 주석 풀어서 사용
        # def hide_if_published(self, comment_id: int,) -> None:
        #     """공개 상태인 댓글을 숨김 상태로 변경한다."""
        #     comment = self.get_any_by_id(comment_id)
        #     if comment is None:
        #         raise ValueError("댓글을 찾을 수 없습니다.")
        #     # 이미 삭제되거나 숨겨졌다면 상태를 변경하지 않는다.
        #     if comment.comment_status != "PUBLISHED":
        #         return
        #     comment.comment_status = "HIDDEN"
        #     self._db.flush()
        #     # 사용자 자체 신고에는 숨길 콘텐츠가 없다.
        #     if report.report_content_type == "USER":
        #         return

        raise ValueError("지원하지 않는 신고 대상입니다.")

    # ---------------------------------------------------------------------

    def _add_user_sanction(
        self,
        report: Report,
        user_sanction_type: str,
        expires_at: datetime | None,
    ) -> None:
        """신고 대상 사용자의 제재 이력을 저장한다."""

        # 기간 정지라면 종료 시각이 반드시 필요하다.
        if user_sanction_type == "SUSPENDED" and expires_at is None:
            raise ValueError("기간 정지에는 종료 시각이 필요합니다.")

        # 경고와 영구 차단에는 종료 시각을 지정할 수 없다.
        if user_sanction_type != "SUSPENDED" and expires_at is not None:
            raise ValueError("기간 정지에만 종료 시각을 설정할 수 있습니다.")

        self._user_sanctions_repository.add_user_sanction(
            reported_user_id=report.reported_user_id,
            user_sanction_type=user_sanction_type,
            # 상세 사유가 있으면 사용하고,
            # 없으면 신고 분류를 제재 사유로 사용한다.
            user_sanction_reason=(report.report_reason or report.report_category),
            report_id=report.report_id,
            expires_at=expires_at,
        )

    # ---------------------------------------------------------------------

    def process_report(
        self,
        report_id: int,
        reviewer_user_id: int,
        request: ReportProcessRequest,
    ) -> None:
        """동일 신고 대상의 PENDING 신고를 일괄 처리한다."""

        # report_id로 대표 신고를 조회한다.
        report = self._report_repository.get_by_id(report_id)

        if report is None:
            raise NotFoundError("신고 내역을 찾을 수 없습니다.")

        # 신고 대상과 기존 처리 상태를 검사한다.
        self._validate_report(
            report_content_type=report.report_content_type,
            post_id=report.post_id,
            comment_id=report.comment_id,
            reported_user_id=report.reported_user_id,
            report_status=report.report_status,
        )

        # 신고 반려에는 사용자 제재가 적용될 수 없다.
        if request.report_status == "REJECTED" and request.user_sanction_type is not None:
            raise ValueError("반려된 신고에는 사용자 제재를 적용할 수 없습니다.")

        try:
            # 같은 대상의 모든 PENDING 신고를 일괄 변경한다.
            self._report_repository.update_report(
                report=report,
                report_status=request.report_status,
                user_sanction_type=request.user_sanction_type,
                reviewer_user_id=reviewer_user_id,
                processed_at=datetime.now(UTC),
            )

            # 기간 정지 또는 영구 차단이라면 콘텐츠를 숨긴다.
            if request.report_status == "ACCEPTED" and request.user_sanction_type in {
                "SUSPENDED",
                "BANNED",
            }:
                self._hide_reported_content(report)

            # 승인됐고 제재 종류가 있다면 이력을 저장한다.
            if request.report_status == "ACCEPTED" and request.user_sanction_type is not None:
                self._add_user_sanction(
                    report=report,
                    user_sanction_type=(request.user_sanction_type),
                    expires_at=request.expires_at,
                )

            # 신고 변경, 콘텐츠 숨김, 사용자 제재를
            # 하나의 트랜잭션으로 확정한다.
            self._db.commit()

        except Exception:
            # 하나라도 실패하면 모든 DB 변경을 취소한다.
            self._db.rollback()
            raise
