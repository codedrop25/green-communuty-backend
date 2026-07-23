"""Post 비즈니스 로직.

**소유권 검증을 Router 가 아닌 여기서 하는 이유 (PLAN.md 3-7):**
    Router 에만 두면 배치 작업이나 다른 서비스에서 호출할 때 검증이 통째로 우회된다.
    "리소스를 바꾸는 모든 경로"가 반드시 지나는 지점은 Service 다.
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.common.pagination import PageParams
from app.core.exceptions import ForbiddenError, NotFoundError
from app.modules.posts.model import Post
from app.modules.posts.repository import PostRepository
from app.modules.posts.schemas import PostCreate, PostUpdate
from app.modules.users.model import User, UserRole


class PostService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repository = PostRepository(db)

    # ------------------------------------------------------------------ 조회

    def get_detail(self, post_id: int) -> Post:
        """상세 조회 (작성자 + 댓글 포함)."""
        post = self._repository.get_detail(post_id)
        if post is None:
            raise NotFoundError("게시글을 찾을 수 없습니다.")
        return post

    def list_posts(self, params: PageParams) -> tuple[list[Post], int]:
        return self._repository.list_paginated(params)

    # ------------------------------------------------------------------ 생성/수정/삭제

    def create(self, author: User, payload: PostCreate) -> Post:
        post = Post(
            title=payload.title,
            content=payload.content,
            author_id=author.id,
        )
        self._repository.add(post)
        self._db.commit()

        # 응답에 작성자 정보가 필요한데 관계는 lazy="raise" 다.
        # 이미 알고 있는 객체이므로 추가 쿼리 없이 직접 채운다.
        post.author = author
        return post

    def update(self, post_id: int, current_user: User, payload: PostUpdate) -> Post:
        post = self._get_owned(post_id, current_user)

        changes = payload.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(post, field, value)

        self._repository.flush()
        self._db.commit()

        # 수정 응답도 상세 포맷이므로 연관 엔티티가 로드된 객체를 다시 가져온다.
        return self.get_detail(post_id)

    def delete(self, post_id: int, current_user: User) -> None:
        """논리 삭제 (PLAN.md 6-3)."""
        post = self._get_owned(post_id, current_user)
        post.deleted_at = datetime.now(UTC).replace(tzinfo=None)
        self._repository.flush()
        self._db.commit()

    # ------------------------------------------------------------------ 인가

    def _get_owned(self, post_id: int, current_user: User) -> Post:
        """게시글을 가져오되, 수정 권한이 있는지 함께 확인한다.

        조회(404)와 권한(403)을 한 곳에서 처리해, 새 엔드포인트를 추가할 때
        권한 검사를 빠뜨리기 어렵게 만든다.
        """
        post = self._repository.get_by_id(post_id)
        if post is None:
            raise NotFoundError("게시글을 찾을 수 없습니다.")

        # 관리자는 신고 처리 등을 위해 타인의 글도 다룰 수 있다.
        if post.author_id != current_user.id and current_user.role != UserRole.ADMIN:
            raise ForbiddenError("본인이 작성한 게시글만 수정/삭제할 수 있습니다.")

        return post
