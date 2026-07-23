"""Comment DB 접근. posts 와 동일한 규칙(명시적 삭제 필터 + eager loading)을 따른다."""

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.common.pagination import PageParams
from app.modules.comments.model import Comment


class CommentRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    @staticmethod
    def _active() -> Select[tuple[Comment]]:
        return select(Comment).where(Comment.deleted_at.is_(None))

    def get_by_id(self, comment_id: int) -> Comment | None:
        stmt = self._active().where(Comment.id == comment_id)
        return self._db.scalars(stmt).one_or_none()

    def list_by_post(self, post_id: int, params: PageParams) -> tuple[list[Comment], int]:
        """게시글의 댓글을 페이지네이션해 조회한다.

        게시글 상세 응답에는 댓글이 이미 포함되지만, 댓글이 많은 글에서는
        별도 페이지네이션 조회가 필요하므로 이 엔드포인트를 따로 둔다.
        """
        total = (
            self._db.scalar(
                select(func.count())
                .select_from(Comment)
                .where(Comment.post_id == post_id, Comment.deleted_at.is_(None))
            )
            or 0
        )
        stmt = (
            self._active()
            .where(Comment.post_id == post_id)
            .options(selectinload(Comment.author))
            .order_by(Comment.id)
            .offset(params.offset)
            .limit(params.limit)
        )
        return list(self._db.scalars(stmt).all()), total

    def add(self, comment: Comment) -> Comment:
        self._db.add(comment)
        self._db.flush()
        self._db.refresh(comment)
        return comment

    def flush(self) -> None:
        self._db.flush()
