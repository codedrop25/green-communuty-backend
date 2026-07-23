"""Post 엔드포인트."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.common.dependencies import CurrentUser, DbSession
from app.common.pagination import PageParams, PageResponse
from app.modules.posts.schemas import (
    PostCreate,
    PostDetailResponse,
    PostSummaryResponse,
    PostUpdate,
)
from app.modules.posts.service import PostService

router = APIRouter(prefix="/posts", tags=["posts"])


@router.get("", response_model=PageResponse[PostSummaryResponse], summary="게시글 목록")
def list_posts(
    params: Annotated[PageParams, Depends()],
    db: DbSession,
) -> PageResponse[PostSummaryResponse]:
    posts, total = PostService(db).list_posts(params)
    return PageResponse.create(
        items=[PostSummaryResponse.model_validate(post) for post in posts],
        total=total,
        params=params,
    )


@router.get("/{post_id}", response_model=PostDetailResponse, summary="게시글 상세 (댓글 포함)")
def get_post(post_id: int, db: DbSession) -> PostDetailResponse:
    post = PostService(db).get_detail(post_id)
    return PostDetailResponse.model_validate(post)


@router.post(
    "",
    response_model=PostSummaryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="게시글 작성",
)
def create_post(
    payload: PostCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> PostSummaryResponse:
    post = PostService(db).create(current_user, payload)
    return PostSummaryResponse.model_validate(post)


@router.patch("/{post_id}", response_model=PostDetailResponse, summary="게시글 수정")
def update_post(
    post_id: int,
    payload: PostUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> PostDetailResponse:
    post = PostService(db).update(post_id, current_user, payload)
    return PostDetailResponse.model_validate(post)


@router.delete(
    "/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="게시글 삭제 (논리 삭제)",
)
def delete_post(post_id: int, current_user: CurrentUser, db: DbSession) -> None:
    PostService(db).delete(post_id, current_user)
