"""Post 비즈니스 로직.

**소유권 검증을 Router 가 아닌 여기서 하는 이유:**
    Router 에만 두면 배치 작업이나 다른 서비스에서 호출할 때 검증이 통째로 우회된다.
    "리소스를 바꾸는 모든 경로"가 반드시 지나는 지점은 Service 다.
"""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.common.dependencies import CurrentUser
from app.common.pagination import PageParams
from app.core.exceptions import ForbiddenError, NotFoundError
from app.modules.posts.post_model import Post
from app.modules.posts.post_repository import PostRepository
from app.modules.posts.post_schemas import (
    PostCreate,
    PostDetailResponse,
    PostImageResponse,
    PostShareResponse,
    PostSummaryResponse,
    PostUpdate,
)
from app.modules.users.user_model import User, UserRole
from tests.conftest import redis_client

UPLOAD_DIR = Path("uploads/posts")


class PostService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repository = PostRepository(db, redis_client)

    # ------------------------------------------------------------------ 조회

    # 게시글 상세 조회
    # 8.10) 조회수 증감 로직 추가
    def get_detail(self, post_id: int, current_user: CurrentUser) -> PostDetailResponse:
        """상세 조회 (작성자 + 댓글 포함)."""
        row = self._repository.get_detail(post_id)
        if row is None:
            raise NotFoundError("게시글을 찾을 수 없습니다.")

        # 현재 게시글 사용자 = 작성자 ?
        post, author = row
        is_author = post.author_id == current_user.user_id
        # 만약 작성자가 아니라면, 조회수 증가
        if not is_author:
            post.post_view_count += 1
            self._repository.flush()

        # 좋아요 조회
        post_like_count = self._repository.count_likes(post_id)
        is_liked = self._repository.get_like(post_id, current_user.user_id)

        return PostDetailResponse.from_entities(
            post,
            author,
            post.post_view_count,
            post_like_count,
            is_liked,
        )

    def list_posts(self, params: PageParams) -> tuple[list[tuple[Post, User]], int]:
        return self._repository.list_paginated(params)

    # ------------------------------------------------------------------ 생성/수정/삭제

    def create(self, author: User, payload: PostCreate) -> PostSummaryResponse:
        post = Post(
            post_title=payload.post_title,
            post_content=payload.post_content,
            author_id=author.user_id,
        )
        self._repository.add(post)
        self._db.commit()

        return PostSummaryResponse.from_entities(post, author)

    def update(self, post_id: int, current_user: User, payload: PostUpdate) -> PostDetailResponse:
        post = self._get_owned(post_id, current_user)

        changes = payload.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(post, field, value)

        self._repository.flush()
        self._db.commit()

        # 수정 응답도 상세 포맷이므로 연관 엔티티가 로드된 객체를 다시 가져온다.
        return self.get_detail(post_id, current_user)

    # 8.21) patch 요청으로 변경 (status=delete)
    def delete(self, post_id: int, current_user: User) -> None:
        """논리적 삭제 상태"""
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
        if post.author_id != current_user.user_id and current_user.user_role != UserRole.ADMIN:
            raise ForbiddenError("본인이 작성한 게시글만 수정/삭제할 수 있습니다.")

        return post

    # ------------------------------------------------------------------ 좋아요

    # 좋아요 누르기
    def like_post(
        self,
        post_id: int,
        current_user: CurrentUser,
    ) -> None:
        """게시글 좋아요."""

        # 1. 게시글 존재 여부 확인
        post = self._repository.get_by_id(post_id)
        if post is None:
            raise NotFoundError("게시글을 찾을 수 없습니다.")

        # 2. 이미 좋아요를 눌렀는지 확인
        existing_like = self._repository.get_like(
            post_id,
            current_user.user_id,
        )
        if existing_like:
            return

        # 3. Redis 에 좋아요 상태 임시 저장
        self._repository.add_like(
            post_id,
            current_user.user_id,
        )

    # 좋아요 취소
    def unlike_post(self, post_id: int, current_user: CurrentUser) -> None:
        """게시글 좋아요 취소."""

        # 1. 해당 게시글에 누른 좋아요 데이터를 조회
        like = self._repository.get_like(post_id, current_user.user_id)
        if not like:
            return

        # 2. Redis 에 좋아요 상태 임시 저장
        self._repository.delete_like(post_id, current_user.user_id)

    # ------------------------------------------------------------------ 공유

    # 공유 기능
    def get_share_url(self, post_id: int) -> PostShareResponse:
        post = self._repository.get_by_id(post_id)

        if post is None:
            raise NotFoundError("게시글을 찾을 수 없습니다.")
        share_url = f"http://localhost:5173/posts/{post_id}"

        return PostShareResponse(
            share_url=share_url,
        )

    # ------------------------------------------------------------------ 이미지

    # 이미지 업로드 기능
    def upload_image(
        self,
        post_id: int,
        current_user: CurrentUser,
        image: UploadFile,
    ) -> PostImageResponse:
        post = self._repository.get_by_id(post_id)

        if post is None:
            raise NotFoundError("게시글을 찾을 수 없습니다.")
        if post.author_id != current_user.user_id:
            raise ForbiddenError("본인이 작성한 게시글에만 이미지를 추가할 수 있습니다.")

        allowed_types = {
            "image/jpeg",
            "image/png",
            "image/webp",
        }
        if image.content_type not in allowed_types:
            raise ValueError("지원하지 않는 이미지 형식입니다.")

        UPLOAD_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )
        suffix = Path(image.filename or "").suffix.lower()
        filename = f"{uuid4()}{suffix}"
        file_path = UPLOAD_DIR / filename

        with file_path.open("wb") as buffer:
            buffer.write(image.file.read())

        post_image = self._repository.add_image(
            post_id=post_id,
            image_path=str(file_path),
        )
        self._db.commit()

        return PostImageResponse(
            image_id=post_image.image_id,
            post_id=post_image.post_id,
            image_url=f"/uploads/posts/{filename}",
        )
