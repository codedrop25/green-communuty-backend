"""Post DB 접근.

두 가지 규칙이 이 파일 전체에 적용된다.
    1. 논리 삭제 필터(`deleted_at IS NULL`)를 **명시적으로** 건다 (PLAN.md 6-3).
       전역 훅으로 자동 주입하지 않는 이유는, 안 보이는 필터가 디버깅을 어렵게 하기 때문이다.
    2. 연관 엔티티는 **eager loading 을 명시**한다 (PLAN.md 3-5).
       모델의 `lazy="raise"` 때문에 빠뜨리면 예외가 나므로 N+1 이 숨을 곳이 없다.
"""

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.common.pagination import PageParams
from app.modules.comments.model import Comment
from app.modules.posts.model import Post


class PostRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    @staticmethod
    def _active() -> Select[tuple[Post]]:
        """삭제되지 않은 게시글만 대상으로 하는 기본 쿼리."""
        return select(Post).where(Post.deleted_at.is_(None))

    def get_by_id(self, post_id: int) -> Post | None:
        """수정/삭제 등 본문만 필요한 경우. 연관 엔티티는 로드하지 않는다."""
        stmt = self._active().where(Post.id == post_id)
        return self._db.scalars(stmt).one_or_none()

    def get_detail(self, post_id: int) -> Post | None:
        """상세 조회 — 작성자와 댓글(+댓글 작성자)까지 함께 로드한다.

        `selectinload` 는 관계마다 IN 절 쿼리를 한 번씩 더 보낸다.
        `joinedload` 와 달리 1:N 에서 부모 행이 중복되지 않아,
        댓글이 많아도 결과 집합이 곱해지지 않는다.

        총 쿼리 수: 게시글 1 + 작성자 1 + 댓글 1 + 댓글작성자 1 = 4 (댓글 수와 무관).
        """
        stmt = (
            self._active()
            .where(Post.id == post_id)
            .options(
                selectinload(Post.author),
                # 삭제된 댓글은 제외한다. 관계에 조건을 걸어야 하므로
                # selectinload 안에서 별도 필터를 적용한다.
                selectinload(Post.comments.and_(Comment.deleted_at.is_(None))).selectinload(
                    Comment.author
                ),
            )
        )
        return self._db.scalars(stmt).one_or_none()

    def list_paginated(self, params: PageParams) -> tuple[list[Post], int]:
        """목록 조회 — 작성자만 함께 로드한다.

        목록에 댓글 본문은 필요 없으므로 로드하지 않는다.
        필요 없는 데이터를 미리 가져오는 것도 N+1 만큼이나 흔한 성능 문제다.
        """
        total = (
            self._db.scalar(select(func.count()).select_from(Post).where(Post.deleted_at.is_(None)))
            or 0
        )
        stmt = (
            self._active()
            .options(selectinload(Post.author))
            .order_by(Post.id.desc())
            .offset(params.offset)
            .limit(params.limit)
        )
        return list(self._db.scalars(stmt).all()), total

    def count_comments(self, post_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(Comment)
            .where(Comment.post_id == post_id, Comment.deleted_at.is_(None))
        )
        return self._db.scalar(stmt) or 0

    def add(self, post: Post) -> Post:
        self._db.add(post)
        self._db.flush()
        self._db.refresh(post)
        return post

    def flush(self) -> None:
        self._db.flush()
