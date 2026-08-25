"""Post 엔드포인트."""

from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile, status

from app.common.dependencies import CurrentUser, DbSession
from app.common.pagination import PageParams, PageResponse
from app.modules.posts.post_schemas import (
    PostCreate,
    PostDetailResponse,
    PostImageResponse,
    PostShareResponse,
    PostSummaryResponse,
    PostUpdate,
)
from app.modules.posts.post_service import PostService

router = APIRouter(prefix="/posts", tags=["posts"])


# 게시글 전체 조회 API
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


# 게시글 상세 조회 API
@router.get("/{post_id}", response_model=PostDetailResponse, summary="게시글 상세 (댓글 포함)")
def get_post(
    post_id: int,
    db: DbSession,
    current_user: CurrentUser,  # 조회수 증감 기능에서 작성자의 조회인지를 구분하기 위해 사용
) -> PostDetailResponse:
    post = PostService(db).get_detail(post_id, current_user)  # service 호출
    return post


# 게시글 생성 API
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


# 게시글 수정
@router.patch("/{post_id}", response_model=PostDetailResponse, summary="게시글 수정")
def update_post(
    post_id: int,
    payload: PostUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> PostDetailResponse:
    post = PostService(db).update(post_id, current_user, payload)
    return PostDetailResponse.model_validate(post)


# 게시글 삭제
# 사용 지양 -> 8.21) patch 요청으로 변경
@router.patch(
    "/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="게시글 삭제 (논리적 삭제 상태)",
)
def delete_post(post_id: int, current_user: CurrentUser, db: DbSession) -> None:
    PostService(db).delete(post_id, current_user)


# ------------------------------------------------------------------ 부가기능


# 좋아요 누르기
@router.post(
    "/{post_id}/likes",
    status_code=status.HTTP_201_CREATED,
    summary="게시글 좋아요",
)
def like_post(
    post_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    PostService(db).like_post(post_id, current_user)


# 좋아요 취소
@router.delete(
    "/{post_id}/likes",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="게시글 좋아요 취소",
)
def unlike_post(
    post_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    PostService(db).unlike_post(post_id, current_user)


# 공유 기능
@router.get(
    "/{post_id}/share",
    response_model=PostShareResponse,
    summary="게시글 공유 URL 조회",
)
def share_post(
    post_id: int,
    db: DbSession,
) -> PostShareResponse:
    return PostService(db).get_share_url(post_id)


# 이미지 업로드 기능
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
) -> PostImageResponse:
    return PostService(db).upload_image(
        post_id,
        current_user,
        image,
    )
