"""Comment DTO."""

from typing import Annotated

from pydantic import BaseModel, Field

# 상세 응답 스키마는 posts 와 공유한다.
# 같은 모양의 DTO 를 두 번 정의하면 한쪽만 바뀌어 응답 포맷이 갈라진다.
from app.modules.posts.schemas import CommentResponse

__all__ = ["CommentCreate", "CommentResponse", "CommentUpdate"]

CommentContentStr = Annotated[str, Field(min_length=1, max_length=1000)]


class CommentCreate(BaseModel):
    content: CommentContentStr


class CommentUpdate(BaseModel):
    content: CommentContentStr
