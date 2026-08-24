"""Post DB 접근.

두 가지 규칙이 이 파일 전체에 적용된다.
    1. 논리 삭제 필터(`deleted_at IS NULL`)를 **명시적으로** 건다.
       전역 훅으로 자동 주입하지 않는 이유는, 안 보이는 필터가 디버깅을 어렵게 하기 때문이다.
    2. 연관 엔티티는 **eager loading 을 명시**한다.
       모델의 `lazy="raise"` 때문에 빠뜨리면 예외가 나므로 N+1 이 숨을 곳이 없다.
"""

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.common.pagination import PageParams
from app.modules.comments.comment_model import Comment
from app.modules.posts.posts_image_model import PostImage
from app.modules.posts.posts_like_model import PostLike
from app.modules.posts.posts_model import Post
from app.modules.users.model import User


class PostRepository:
    # 생성자
    def __init__(self, db: Session) -> None:
        self._db = db

    # * @staticmethod : self 를 사용하지 않는 메서드
    # * _active : 클래스 내부의 private 와 비슷한 성격
    @staticmethod
    def _active() -> Select[tuple[Post]]:
        """삭제되지 않은 게시글만 대상으로 하는 기본 쿼리."""
        return select(Post).where(Post.deleted_at.is_(None))

    # post_id 로 post 를 조회하는 기능
    def get_by_id(self, post_id: int) -> Post | None:
        """수정/삭제 등 본문만 필요한 경우. 연관 엔티티는 로드하지 않는다."""
        stmt = self._active().where(Post.post_id == post_id)

        # Optional<Post> findByPostId(Long PostId)
        # * stmt : statement(실행문) 의 줄임말인 듯, 실행할 SELECT 쿼리
        # * scalars(stmt) : 쿼리 실행 + Post 객체만 추출
        # * one_or_none() : 1개면 반환, 0개면 None / 2개 이상이면 PK 예외 발생
        return self._db.scalars(stmt).one_or_none()

    # post 상세 조회
    # 8.02) 아직 코멘트까지 불러오는 코드 없음. 반환 타입 빠진 상태.
    def get_detail(self, post_id: int):
        """상세 조회 — 작성자와 댓글(+댓글 작성자)까지 함께 로드한다.

        `selectinload` 는 관계마다 IN 절 쿼리를 한 번씩 더 보낸다.
        `joinedload` 와 달리 1:N 에서 부모 행이 중복되지 않아,
        댓글이 많아도 결과 집합이 곱해지지 않는다.
        총 쿼리 수: 게시글 1 + 작성자 1 + 댓글 1 + 댓글작성자 1 = 4 (댓글 수와 무관).
        """
        stmt = (
            self._active()
            .join(
                User,
                Post.author_id == User.user_id,
            )
            .add_columns(User)
            .where(
                Post.post_id == post_id,
            )
        )
        # * scalars : 여러 행의 첫번째 값을 순서대로 꺼내온다.
        # * execute : 행 전체를 가져온다.
        return self._db.execute(stmt).one_or_none()

    # 특정 페이지의 목록을 조회
    def list_paginated(self, params: PageParams):
        """목록 조회 — 작성자만 함께 로드한다.

        목록에 댓글 본문은 필요 없으므로 로드하지 않는다.
        필요 없는 데이터를 미리 가져오는 것도 N+1 만큼이나 흔한 성능 문제다.
        """
        total = (
            self._db.scalar(  # scalar : 단일 값 하나만 가져온다.
                select(func.count())  # func : SQL 함수를 호출하는 메서드 -> COUNT(*)
                .select_from(Post)  # FROM posts
                .where(Post.deleted_at.is_(None))  # WHERE deleted_at IS NULL
            )
            or 0
        )
        stmt = (
            self._active()
            .join(
                User,
                Post.author_id == User.user_id,
            )
            .add_columns(User)
            # .order_by(Post.post_id.desc())
            # * .order_by, desc 등은 지양하는게 좋음,가져와서 로직으로 푸는게 더 데이터 적으로 낫다.
            .offset(params.offset)
            .limit(params.limit)
        )
        rows = self._db.execute(stmt).all()

        return rows, total

    # 삭제되지 않은 댓글 갯수를 count
    def count_comments(self, post_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(Comment)
            .where(Comment.post_id == post_id, Comment.deleted_at.is_(None))
        )
        return self._db.scalar(stmt) or 0

    # 좋아요 count
    def count_likes(self, post_id: int) -> int:
        stmt = select(func.count()).select_from(PostLike).where(PostLike.post_id == post_id)
        return self._db.scalar(stmt) or 0

    # 게시글 저장
    def add(self, post: Post) -> Post:
        self._db.add(post)
        self._db.flush()
        self._db.refresh(post)
        return post

    # service 에서 DB에 바로 접근하지 않도록 한 번 감싼 캡슐화 메서드
    def flush(self) -> None:
        self._db.flush()

    # ------------------------------------------------------------------ 부가기능

    # 좋아요 누르기
    def get_like(self, post_id: int, user_id: int) -> PostLike | None:
        stmt = select(PostLike).where(
            PostLike.post_id == post_id,
            PostLike.user_id == user_id,
        )
        return self._db.scalars(stmt).one_or_none()

    # 좋아요 저장
    def add_like(self, post_id: int, user_id: int) -> PostLike:
        like = PostLike(
            post_id=post_id,
            user_id=user_id,
        )
        self._db.add(like)
        self._db.flush()
        return like

    # 좋아요 취소
    def delete_like(self, like: PostLike) -> None:
        self._db.delete(like)
        self._db.flush()

    # 이미지 저장
    def add_image(
        self,
        post_id: int,
        image_path: str,
    ) -> PostImage:
        post_image = PostImage(
            post_id=post_id,
            image_path=image_path,
        )
        self._db.add(post_image)
        self._db.flush()
        self._db.refresh(post_image)

        return post_image
