"""Post DTO."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

TitleStr = Annotated[str, Field(min_length=1, max_length=200)]
ContentStr = Annotated[str, Field(min_length=1)]


# Response DTO
class AuthorSummary(BaseModel):
    """응답에 포함되는 작성자 요약.
    `UserResponse` 전체를 넣지 않는 이유는, 게시글 조회에서 다른 사용자의
    이메일·활성 상태까지 노출할 필요가 없기 때문이다.
    """

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    user_nickname: str


# Request DTO
class PostCreate(BaseModel):
    post_title: TitleStr
    post_content: ContentStr


# Request DTO
class PostUpdate(BaseModel):
    """부분 수정. 보낸 필드만 반영한다."""

    # None 의 의미는 필수값이 아닌 선택값이라는 뜻.
    post_title: TitleStr | None = None
    post_content: ContentStr | None = None


# Response DTO
class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    comment_id: int
    comment_content: str
    author: AuthorSummary
    created_at: datetime


# Response DTO
class PostSummaryResponse(BaseModel):
    """목록용 응답. 본문과 댓글을 담지 않는다."""

    model_config = ConfigDict(from_attributes=True)

    post_id: int
    post_title: str
    author: AuthorSummary
    created_at: datetime

    @classmethod
    def from_entities(cls, post, author) -> "PostSummaryResponse":
        return cls(
            post_id=post.post_id,
            post_title=post.post_title,
            post_content=post.post_content,
            author=AuthorSummary(
                user_id=author.user_id,
                user_nickname=author.user_nickname,
            ),
            created_at=post.created_at,
        )


# ResponseDTO
class PostDetailResponse(BaseModel):
    """상세용 응답. 댓글 목록을 포함한다."""

    model_config = ConfigDict(from_attributes=True)

    post_id: int
    post_title: str
    post_content: str
    post_view_count: int  # 조회수
    post_like_count: int  # 좋아요
    is_liked: bool  # 좋아요
    author: AuthorSummary
    comments: list[CommentResponse]
    created_at: datetime
    updated_at: datetime

    # * self : 현재 객체
    # * cls : 현재 클래스
    @classmethod
    def from_entities(
        cls,
        post,
        author,
        post_like_count: int,
        is_liked: bool,
    ) -> "PostDetailResponse":
        return cls(
            post_id=post.post_id,
            post_title=post.post_title,
            post_content=post.post_content,
            post_like_count=post_like_count,
            is_liked=is_liked,
            author=AuthorSummary(
                user_id=author.user_id,
                user_nickname=author.user_nickname,
            ),
            comments=[],  # 댓글 조회
            created_at=post.created_at,
            updated_at=post.updated_at,
        )


# 공유 기능
# Response DTO
class PostShareResponse(BaseModel):
    share_url: str


# 이미지 업로드 기능
class PostImageResponse(BaseModel):
    image_id: int
    post_id: int
    image_url: str
