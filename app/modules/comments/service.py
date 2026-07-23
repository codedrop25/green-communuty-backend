"""Comment 비즈니스 로직. posts 와 동일한 소유권 검증 패턴을 따른다."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.common.pagination import PageParams
from app.core.exceptions import ForbiddenError, NotFoundError
from app.modules.comments.model import Comment
from app.modules.comments.repository import CommentRepository
from app.modules.comments.schemas import CommentCreate, CommentUpdate
from app.modules.posts.repository import PostRepository
from app.modules.users.model import User, UserRole


class CommentService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repository = CommentRepository(db)
        # 댓글을 달기 전에 게시글이 살아 있는지 확인해야 하므로 함께 쓴다.
        # 모듈 간 결합이지만 Repository 단위이므로 영향 범위가 좁다.
        self._posts = PostRepository(db)

    # ------------------------------------------------------------------ 조회

    def list_by_post(self, post_id: int, params: PageParams) -> tuple[list[Comment], int]:
        self._ensure_post_exists(post_id)
        return self._repository.list_by_post(post_id, params)

    # ------------------------------------------------------------------ 생성/수정/삭제

    def create(self, post_id: int, author: User, payload: CommentCreate) -> Comment:
        self._ensure_post_exists(post_id)

        comment = Comment(
            content=payload.content,
            post_id=post_id,
            author_id=author.id,
        )
        self._repository.add(comment)
        self._db.commit()

        # 응답에 필요한 작성자를 추가 쿼리 없이 채운다 (관계는 lazy="raise").
        comment.author = author
        return comment

    def update(self, comment_id: int, current_user: User, payload: CommentUpdate) -> Comment:
        comment = self._get_owned(comment_id, current_user)
        comment.content = payload.content
        self._repository.flush()
        self._db.commit()

        comment.author = current_user
        return comment

    def delete(self, comment_id: int, current_user: User) -> None:
        comment = self._get_owned(comment_id, current_user)
        comment.deleted_at = datetime.now(UTC).replace(tzinfo=None)
        self._repository.flush()
        self._db.commit()

    # ------------------------------------------------------------------ 내부

    def _ensure_post_exists(self, post_id: int) -> None:
        if self._posts.get_by_id(post_id) is None:
            raise NotFoundError("게시글을 찾을 수 없습니다.")

    def _get_owned(self, comment_id: int, current_user: User) -> Comment:
        comment = self._repository.get_by_id(comment_id)
        if comment is None:
            raise NotFoundError("댓글을 찾을 수 없습니다.")

        if comment.author_id != current_user.id and current_user.role != UserRole.ADMIN:
            raise ForbiddenError("본인이 작성한 댓글만 수정/삭제할 수 있습니다.")

        return comment
