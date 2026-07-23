"""Post DTO."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

TitleStr = Annotated[str, Field(min_length=1, max_length=200)]
ContentStr = Annotated[str, Field(min_length=1)]


class AuthorSummary(BaseModel):
    """응답에 포함되는 작성자 요약.

    `UserResponse` 전체를 넣지 않는 이유는, 게시글 조회에서 다른 사용자의
    이메일·활성 상태까지 노출할 필요가 없기 때문이다.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    nickname: str


class PostCreate(BaseModel):
    title: TitleStr
    content: ContentStr


class PostUpdate(BaseModel):
    """부분 수정. 보낸 필드만 반영한다."""

    title: TitleStr | None = None
    content: ContentStr | None = None


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    author: AuthorSummary
    created_at: datetime


class PostSummaryResponse(BaseModel):
    """목록용 응답. 본문과 댓글을 담지 않는다."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    author: AuthorSummary
    created_at: datetime


class PostDetailResponse(BaseModel):
    """상세용 응답. 댓글 목록을 포함한다."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    author: AuthorSummary
    comments: list[CommentResponse]
    created_at: datetime
    updated_at: datetime
