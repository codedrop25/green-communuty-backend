"""Comment 엔드포인트.

댓글은 게시글에 종속되므로 생성/조회는 `/posts/{post_id}/comments` 아래에 둔다.
수정/삭제는 댓글 ID 만으로 대상이 특정되므로 `/comments/{comment_id}` 를 쓴다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.common.dependencies import CurrentUser, DbSession
from app.common.pagination import PageParams, PageResponse
from app.modules.comments.schemas import CommentCreate, CommentResponse, CommentUpdate
from app.modules.comments.service import CommentService

router = APIRouter(tags=["comments"])


@router.get(
    "/posts/{post_id}/comments",
    response_model=PageResponse[CommentResponse],
    summary="게시글의 댓글 목록",
)
def list_comments(
    post_id: int,
    params: Annotated[PageParams, Depends()],
    db: DbSession,
) -> PageResponse[CommentResponse]:
    comments, total = CommentService(db).list_by_post(post_id, params)
    return PageResponse.create(
        items=[CommentResponse.model_validate(comment) for comment in comments],
        total=total,
        params=params,
    )


@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="댓글 작성",
)
def create_comment(
    post_id: int,
    payload: CommentCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> CommentResponse:
    comment = CommentService(db).create(post_id, current_user, payload)
    return CommentResponse.model_validate(comment)


@router.patch(
    "/comments/{comment_id}",
    response_model=CommentResponse,
    summary="댓글 수정",
)
def update_comment(
    comment_id: int,
    payload: CommentUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> CommentResponse:
    comment = CommentService(db).update(comment_id, current_user, payload)
    return CommentResponse.model_validate(comment)


@router.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="댓글 삭제 (논리 삭제)",
)
def delete_comment(comment_id: int, current_user: CurrentUser, db: DbSession) -> None:
    CommentService(db).delete(comment_id, current_user)
