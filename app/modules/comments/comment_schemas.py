"""Comment DTO."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["CommentCreate", "CommentResponse", "CommentUpdate"]


# 댓글 내용 길이 제한
CommentContentStr = Annotated[
    str,
    Field(min_length=1, max_length=1000),
]


class CommentCreate(BaseModel):
    """댓글 및 대댓글 작성 요청."""

    # 댓글 내용
    comment_content: CommentContentStr

    # 부모 댓글 번호
    # 일반 댓글은 NULL, 대댓글이면 부모 댓글 번호 저장
    parent_comment_id: int | None = None


class CommentUpdate(BaseModel):
    """댓글 수정 요청."""

    # 수정할 댓글 내용
    comment_content: CommentContentStr


class CommentResponse(BaseModel):
    """댓글 응답."""

    # DB에서 조회한 댓글 데이터를 응답에 사용
    model_config = ConfigDict(from_attributes=True)

    # 댓글 고유 번호
    comment_id: int

    # 게시글 번호
    post_id: int

    # 댓글 작성자 번호
    author_id: int

    # 댓글 내용
    comment_content: str

    # 부모 댓글 번호
    # 일반 댓글은 NULL, 답글이면 부모 댓글 번호
    parent_comment_id: int | None = None

    # 답글 개수
    reply_count: int = 0

    # 댓글 등록 시간
    created_at: datetime

    # 댓글 수정 시간
    updated_at: datetime
