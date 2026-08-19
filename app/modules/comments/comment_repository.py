"""Comment DB 접근."""

from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.common.pagination import PageParams
from app.modules.comments.comment_model import Comment
from app.modules.users.model import User


class CommentRepository:
    """댓글 데이터 조회 및 저장을 담당하는 Repository."""

    def __init__(self, db: Session) -> None:
        # DB 연결 객체 저장
        self._db = db

    # 삭제 상태가 아닌 댓글 조회
    @staticmethod
    def _active() -> Select[tuple[Comment]]:
        return select(Comment).where(Comment.deleted_at.is_(None))

    # 댓글 정렬 기준
    @staticmethod
    def _comment_sort_key(
        comment: Comment,
    ) -> tuple[datetime, int]:
        return (
            comment.created_at,
            comment.comment_id,
        )

    # 댓글 번호로 댓글 1개 조회
    def get_by_id(
        self,
        comment_id: int,
    ) -> Comment | None:
        stmt = self._active().where(Comment.comment_id == comment_id)

        # 댓글이 있으면 반환, 없으면 None
        return self._db.scalars(stmt).one_or_none()

    # 게시글 댓글 목록 조회
    def list_by_post(
        self,
        post_id: int,
        params: PageParams,
    ) -> tuple[list[Comment], int, dict[int, int]]:
        """게시글의 댓글을 페이지네이션해 조회한다."""

        # 해당 게시글의 전체 댓글 개수 조회
        total = (
            # 댓글 개수 조회
            self._db.scalar(
                # 댓글 개수 세기
                select(func.count())
                # Comment 테이블에서 조회
                .select_from(Comment)
                # 해당 게시글의 댓글만 조회
                .where(
                    Comment.post_id == post_id,
                    # 삭제 상태가 아닌 댓글만 조회
                    Comment.deleted_at.is_(None),
                )
            )
            # 댓글이 없으면 0
            or 0
        )

        # 해당 게시글의 댓글 목록 조회
        stmt = self._active().where(
            # 해당 게시글의 일반 댓글만 조회
            Comment.post_id == post_id,
            Comment.parent_comment_id.is_(None),
        )

        # 댓글 목록 가져오기
        comments = list(self._db.scalars(stmt).all())

        # 댓글 등록 시간 순서로 정렬
        # 작성 시간이 같으면 댓글 번호 순서대로 정렬
        # order by, desc 연산이 많이 되어서 가지고 와서 로직으로 풀어라 효율 많이 떨어짐
        # 데이터가 많지 않으니까 서버 내에서 정렬 로직 돌려도 아무 문제 없음
        # DB마다 정렬 기본 설정 값이 있음 데이터를 미리 desc를 한 후에 조회 처리
        comments.sort(
            # 댓글 정렬 기준 함수 사용
            key=self._comment_sort_key,
            # 최신 댓글부터 나오게 정렬
            reverse=True,
        )

        # 현재 페이지에서 보여줄 댓글 목록 가져오기
        # 한 페이지에 보여줄 댓글 개수만큼 목록 노출
        comments = comments[params.offset : params.offset + params.limit]

        # 현재 페이지의 댓글 번호 목록
        comment_ids: list[int] = []

        for comment in comments:
            # 댓글 번호 목록에 추가
            comment_ids.append(comment.comment_id)

        # 각 댓글에 달린 답글 개수 조회
        reply_counts = self.count_replies_by_parents(comment_ids)

        # 댓글 목록, 전체 댓글 개수, 답글 개수 반환
        return (
            comments,
            total,
            reply_counts,
        )

    # 게시글 댓글들의 답글 개수 조회
    def count_replies_by_parents(
        self,
        parent_comment_ids: list[int],
    ) -> dict[int, int]:
        # 조회할 댓글이 없으면 빈 값 반환
        if not parent_comment_ids:
            return {}

        # 댓글별 답글 개수 조회
        stmt = (
            select(
                Comment.parent_comment_id,
                func.count(Comment.comment_id),
            )
            .where(
                # 현재 페이지의 댓글에 달린 답글만 조회
                Comment.parent_comment_id.in_(parent_comment_ids),
                # 삭제 상태가 아닌 답글만 조회
                Comment.deleted_at.is_(None),
            )
            # 댓글 번호별로 답글 개수 묶기
            .group_by(Comment.parent_comment_id)
        )

        # 답글 개수 조회
        rows = self._db.execute(stmt).all()

        # 댓글 번호와 답글 개수 저장
        reply_counts: dict[int, int] = {}

        for parent_comment_id, reply_count in rows:
            # 부모 댓글 번호가 있는 경우 저장
            if parent_comment_id is not None:
                reply_counts[parent_comment_id] = reply_count

        # 댓글별 답글 개수 반환
        return reply_counts

    # 답글 작성 시 기존 댓글 조회
    def get_parent_comment(
        self,
        parent_comment_id: int,
    ) -> Comment | None:
        stmt = self._active().where(Comment.comment_id == parent_comment_id)

        # 기존 댓글이 있으면 반환, 없으면 None
        return self._db.scalars(stmt).one_or_none()

    # 댓글에 달린 답글 목록 조회
    def list_by_parent(
        self,
        parent_comment_id: int,
    ) -> list[Comment]:
        stmt = self._active().where(Comment.parent_comment_id == parent_comment_id)

        # 답글 목록 반환
        return list(self._db.scalars(stmt).all())

    # 멘션 사용자 검색
    # @ 입력 시 댓글 참여자 추천
    # 최근 멘션 사용자 추천은 Redis 적용 시 추가해야한다고함(질문하기)
    # 닉네임 입력 시 비슷한 닉네임 목록 추천
    def search_mention_users(
        self,
        post_id: int,
        nickname: str,
    ) -> list[User]:
        # 닉네임을 입력하지 않은 경우
        if not nickname:
            stmt = (
                select(User)
                # 댓글 작성한 사용자 조회
                .join(
                    Comment,
                    Comment.author_id == User.id,
                )
                .where(
                    # 현재 게시글에 댓글을 작성한 사용자 조회
                    Comment.post_id == post_id,
                    # 삭제 상태가 아닌 댓글만 조회
                    Comment.deleted_at.is_(None),
                )
                # 같은 사용자가 여러 댓글을 작성해도 한 번만 조회
                .distinct()
                # 추천 사용자 수 제한
                .limit(5)
            )

            # 추천 사용자 목록 반환
            return list(self._db.scalars(stmt).all())

        # 닉네임을 입력한 경우 비슷한 닉네임 검색
        stmt = (
            select(User)
            .where(
                # 입력한 글자가 포함된 닉네임 검색
                User.nickname.contains(nickname)
            )
            # 추천 사용자 수 제한
            .limit(5)
        )

        # 추천 사용자 목록 반환
        return list(self._db.scalars(stmt).all())

    # 댓글 등록
    def add(
        self,
        comment: Comment,
    ) -> Comment:
        # 새 댓글을 DB 저장 대상으로 등록
        self._db.add(comment)

        # 현재 변경 내용을 DB에 먼저 반영
        self._db.flush()

        # DB에 저장된 최신 댓글 정보 다시 조회
        self._db.refresh(comment)

        # 저장된 댓글 반환
        return comment

    # 변경 내용 DB 반영
    def flush(self) -> None:
        self._db.flush()
