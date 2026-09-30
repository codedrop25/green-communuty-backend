"""Post 엔드포인트."""

from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile, status

from app.common.dependencies import (
    CurrentUser,
    DbSession,
    RedisClient,
)
from app.common.pagination import PageParams, PageResponse
from app.infrastructure.storage.base import Storage
from app.infrastructure.storage.s3 import get_storage
from app.modules.posts.post_schemas import (
    PostCreate,
    PostDetailResponse,
    PostImageResponse,
    PostShareResponse,
    PostSummaryResponse,
    PostUpdate,
)
from app.modules.posts.post_service import PostService

# get_storage()가 반환하는 S3Storage 또는 R2Storage를
# FastAPI가 자동으로 주입하도록 만든 자료형이다.
StorageClient = Annotated[Storage, Depends(get_storage)]


router = APIRouter(
    prefix="/posts",
    tags=["posts"],
)


# ------------------------------------------------------------------ 조회


@router.get(
    "",
    response_model=PageResponse[PostSummaryResponse],
    summary="게시글 목록",
)
def list_posts(
    params: Annotated[PageParams, Depends()],
    current_user: CurrentUser,
    db: DbSession,
    redis: RedisClient,
    storage: StorageClient,
) -> PageResponse[PostSummaryResponse]:
    """게시글 목록을 조회한다."""

    posts, total = PostService(
        db,
        redis,
        storage,
    ).list_posts(
        params,
        current_user,
    )

    return PageResponse.create(
        items=[PostSummaryResponse.from_entities(post, author) for post, author in posts],
        total=total,
        params=params,
    )


@router.get(
    "/{post_id}",
    response_model=PostDetailResponse,
    summary="게시글 상세 (댓글 포함)",
)
def get_post(
    post_id: int,
    current_user: CurrentUser,
    db: DbSession,
    redis: RedisClient,
    storage: StorageClient,
) -> PostDetailResponse:
    """게시글 상세 정보를 조회한다."""

    return PostService(
        db,
        redis,
        storage,
    ).get_detail(
        post_id,
        current_user,
    )


# ---------------------------------------------------------- 생성/수정/삭제


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
    redis: RedisClient,
    storage: StorageClient,
) -> PostSummaryResponse:
    """새로운 게시글을 작성한다."""

    return PostService(
        db,
        redis,
        storage,
    ).create(
        current_user,
        payload,
    )


@router.patch(
    "/{post_id}",
    response_model=PostDetailResponse,
    summary="게시글 수정",
)
def update_post(
    post_id: int,
    payload: PostUpdate,
    current_user: CurrentUser,
    db: DbSession,
    redis: RedisClient,
    storage: StorageClient,
) -> PostDetailResponse:
    """작성자가 게시글을 수정한다."""

    return PostService(
        db,
        redis,
        storage,
    ).update(
        post_id,
        current_user,
        payload,
    )


@router.patch(
    "/{post_id}/delete",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="게시글 삭제 (논리적 삭제 상태)",
)
def delete_post(
    post_id: int,
    current_user: CurrentUser,
    db: DbSession,
    redis: RedisClient,
    storage: StorageClient,
) -> None:
    """게시글을 논리적으로 삭제한다."""

    PostService(
        db,
        redis,
        storage,
    ).delete(
        post_id,
        current_user,
    )


# ------------------------------------------------------------------ 좋아요


@router.post(
    "/{post_id}/likes",
    status_code=status.HTTP_201_CREATED,
    summary="게시글 좋아요",
)
def like_post(
    post_id: int,
    current_user: CurrentUser,
    db: DbSession,
    redis: RedisClient,
    storage: StorageClient,
) -> None:
    """게시글에 좋아요를 등록한다."""

    PostService(
        db,
        redis,
        storage,
    ).like_post(
        post_id,
        current_user,
    )


@router.put(
    "/{post_id}/likes",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="게시글 좋아요 취소",
)
def unlike_post(
    post_id: int,
    current_user: CurrentUser,
    db: DbSession,
    redis: RedisClient,
    storage: StorageClient,
) -> None:
    """게시글 좋아요를 취소한다."""

    PostService(
        db,
        redis,
        storage,
    ).unlike_post(
        post_id,
        current_user,
    )


# ------------------------------------------------------------------ 공유


@router.get(
    "/{post_id}/share",
    response_model=PostShareResponse,
    summary="게시글 공유 URL 조회",
)
def share_post(
    post_id: int,
    db: DbSession,
    redis: RedisClient,
    storage: StorageClient,
) -> PostShareResponse:
    """게시글 공유 URL을 조회한다."""

    return PostService(
        db,
        redis,
        storage,
    ).get_share_url(post_id)


# ------------------------------------------------------------------ 이미지


@router.post(
    "/{post_id}/images",
    response_model=PostImageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="게시글 이미지 업로드",
)
def upload_post_image(
    post_id: int,
    image: UploadFile,
    current_user: CurrentUser,
    db: DbSession,
    redis: RedisClient,
    storage: StorageClient,
) -> PostImageResponse:
    """게시글 이미지를 업로드한다."""

    return PostService(
        db,
        redis,
        storage,
    ).upload_image(
        post_id,
        current_user,
        image,
    )
