"""Comment 엔드포인트."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.common.dependencies import CurrentUser, DbSession
from app.common.pagination import PageParams, PageResponse
from app.modules.comments.comment_schemas import (
    CommentCreate,
    CommentResponse,
    CommentUpdate,
)
from app.modules.comments.comment_service import CommentService

# 댓글 API 관리
router = APIRouter(tags=["comments"])


# 게시글 댓글 목록 조회
@router.get(
    "/posts/{post_id}/comments",
    response_model=PageResponse[CommentResponse],
    summary="게시글 댓글 목록",
)
def list_comments(
    # 댓글을 조회할 게시글 번호
    post_id: int,
    # 페이지 정보
    params: Annotated[PageParams, Depends()],
    # DB 연결
    db: DbSession,
) -> PageResponse[CommentResponse]:
    # 댓글 목록, 전체 댓글 개수, 답글 개수 조회
    comments, total, reply_counts = CommentService(db).list_by_post(
        post_id,
        params,
    )

    # 댓글 응답 목록
    items: list[CommentResponse] = []

    for comment in comments:
        # 댓글 응답 형식으로 변환
        item = CommentResponse.model_validate(comment)

        # 해당 댓글의 답글 개수 추가
        item.reply_count = reply_counts.get(
            comment.comment_id,
            0,
        )

        items.append(item)

    # 댓글 목록 반환
    return PageResponse.create(
        items=items,
        # 전체 댓글 개수
        total=total,
        # 현재 페이지 정보
        params=params,
    )


# 댓글의 답글 목록 조회
@router.get(
    "/comments/{comment_id}/replies",
    response_model=list[CommentResponse],
    summary="댓글 답글 목록",
)
def list_replies(
    # 답글을 조회할 댓글 번호
    comment_id: int,
    # DB 연결
    db: DbSession,
) -> list[CommentResponse]:
    # 해당 댓글의 답글 목록 조회
    replies = CommentService(db).list_by_parent(
        comment_id,
    )

    # 답글 목록 반환
    return [CommentResponse.model_validate(reply) for reply in replies]


# 댓글 또는 답글 작성
@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="댓글 작성",
)
def create_comment(
    # 댓글을 작성할 게시글 번호
    post_id: int,
    # 작성할 댓글 내용
    payload: CommentCreate,
    # 현재 로그인한 사용자
    current_user: CurrentUser,
    # DB 연결
    db: DbSession,
) -> CommentResponse:
    # 댓글 또는 답글 작성
    comment = CommentService(db).create(
        post_id,
        current_user,
        payload,
    )

    # 작성된 댓글 반환
    return CommentResponse.model_validate(comment)


# 댓글 수정
@router.patch(
    "/comments/{comment_id}",
    response_model=CommentResponse,
    summary="댓글 수정",
)
def update_comment(
    # 수정할 댓글 번호
    comment_id: int,
    # 수정할 댓글 내용
    payload: CommentUpdate,
    # 현재 로그인한 사용자
    current_user: CurrentUser,
    # DB 연결
    db: DbSession,
) -> CommentResponse:
    # 댓글 수정
    comment = CommentService(db).update(
        comment_id,
        current_user,
        payload,
    )

    # 수정된 댓글 반환
    return CommentResponse.model_validate(comment)


# 댓글 삭제 상태로 변경
@router.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="댓글 삭제",
)
def delete_comment(
    # 삭제할 댓글 번호
    comment_id: int,
    # 현재 로그인한 사용자
    current_user: CurrentUser,
    # DB 연결
    db: DbSession,
) -> None:
    # 댓글 삭제 상태로 변경
    CommentService(db).delete(
        comment_id,
        current_user,
    )
