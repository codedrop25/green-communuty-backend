"""Post DB 접근.

두 가지 규칙이 이 파일 전체에 적용된다.
    1. 논리 삭제 필터(`deleted_at IS NULL`)를 **명시적으로** 건다.
       전역 훅으로 자동 주입하지 않는 이유는, 안 보이는 필터가 디버깅을 어렵게 하기 때문이다.
    2. 연관 엔티티는 **eager loading 을 명시**한다.
       모델의 `lazy="raise"` 때문에 빠뜨리면 예외가 나므로 N+1 이 숨을 곳이 없다.
"""

from typing import cast

from redis import Redis
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.common.pagination import PageParams
from app.modules.comments.comment_model import Comment
from app.modules.posts.post_image_model import PostImage
from app.modules.posts.post_like_model import PostLike
from app.modules.posts.post_model import Post
from app.modules.users.user_model import User


class PostRepository:
    # 생성자
    # 8.22) redis 사용을 위한 기본 코드 추가
    def __init__(self, db: Session, redis: Redis) -> None:
        self._db = db
        self._redis = redis

    # * @staticmethod : self 를 사용하지 않는 메서드
    # * _active : 클래스 내부의 private 와 비슷한 성격
    @staticmethod
    def _active() -> Select[tuple[Post]]:
        """삭제되지 않은 게시글만 대상으로 하는 기본 쿼리."""
        return select(Post).where(Post.deleted_at.is_(None))

    # post_id 로 post 를 조회하는 기능
    def get_by_id(self, post_id: int) -> Post | None:
        """수정/삭제 등 본문만 필요한 경우. 연관 엔티티는 로드하지 않는다."""
        statement = self._active().where(Post.post_id == post_id)

        # Optional<Post> findByPostId(Long PostId)
        # * statement : statement(실행문) 의 줄임말인 듯, 실행할 SELECT 쿼리
        # * scalars(statement) : 쿼리 실행 + Post 객체만 추출
        # * one_or_none() : 1개면 반환, 0개면 None / 2개 이상이면 PK 예외 발생
        return self._db.scalars(statement).one_or_none()

    # post 상세 조회
    # 8.02) 코멘트까지 불러오는 코드 추가 필요
    def get_detail(self, post_id: int) -> tuple[Post, User] | None:
        """상세 조회 — 작성자와 댓글(+댓글 작성자)까지 함께 로드한다.
        `selectinload` 는 관계마다 IN 절 쿼리를 한 번씩 더 보낸다.
        `joinedload` 와 달리 1:N 에서 부모 행이 중복되지 않아,
        댓글이 많아도 결과 집합이 곱해지지 않는다.
        총 쿼리 수: 게시글 1 + 작성자 1 + 댓글 1 + 댓글작성자 1 = 4 (댓글 수와 무관).
        """
        statement = (
            self._active()
            .join(
                User,
                Post.author_id == User.user_id,
            )
            .add_columns(User)
            .where(Post.post_id == post_id)
        )
        # * scalars : 여러 행의 첫번째 값을 순서대로 꺼내온다.
        # * execute : 행 전체를 가져온다.
        row = self._db.execute(statement).one_or_none()

        if row is None:
            return None

        return row[0], row[1]

    # 특정 페이지의 목록을 조회
    # 8.21) 반환타입 추가
    def list_paginated(self, params: PageParams) -> tuple[list[tuple[Post, User]], int]:
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
        statement = (
            self._active()
            .join(User, Post.author_id == User.user_id)
            .add_columns(User)
            # .order_by(Post.post_id.desc())
            # * .order_by, desc 등은 지양하는게 좋음,가져와서 로직으로 푸는게 더 데이터 적으로 낫다.
            .offset(params.offset)
            .limit(params.limit)
        )
        rows = self._db.execute(statement).all()

        result = [(row[0], row[1]) for row in rows]

        return result, total

    # 삭제되지 않은 댓글 갯수를 count
    def count_comments(self, post_id: int) -> int:
        statement = (
            select(func.count())
            .select_from(Comment)
            .where(Comment.post_id == post_id, Comment.deleted_at.is_(None))
        )
        return self._db.scalar(statement) or 0

    # 좋아요 count
    def count_likes(self, post_id: int) -> int:
        statement = select(func.count()).select_from(PostLike).where(PostLike.post_id == post_id)
        return self._db.scalar(statement) or 0

    # 게시글 저장
    def add(self, post: Post) -> Post:
        self._db.add(post)
        self._db.flush()
        self._db.refresh(post)
        return post

    # service 에서 DB에 바로 접근하지 않도록 한 번 감싼 캡슐화 메서드
    def flush(self) -> None:
        self._db.flush()

    # ------------------------------------------------------------------ 좋아요

    # 좋아요 상태 조회
    # 8.22) redis 추가
    def get_like(self, post_id: int, user_id: int) -> bool:
        key = f"post_like:{post_id}:{user_id}"  # ex) post_like:10:3

        # 1. Redis 의 like data 조회
        redis_status = cast(str | None, self._redis.get(key))
        if redis_status is not None:  # Redis 에 값이 있다면
            return redis_status == "1"  # "1"과 비교하여 True / False 반환

        # 2. 만약 Redis 가 비어있다면 DB를 조회
        statement = select(PostLike).where(
            PostLike.post_id == post_id,
            PostLike.user_id == user_id,
        )
        like = self._db.scalars(statement).one_or_none()

        return like is not None  # DB에 data 가 있으면 True / 없으면 False 반환

    # 좋아요 임시 저장
    # 8.22) DB 에 바로 저장하던 코드를 -> redis 에 임시 저장 코드로 수정
    def add_like(self, post_id: int, user_id: int) -> None:
        key = f"post_like:{post_id}:{user_id}"  # ex) post_like:10:3
        self._redis.set(key, 1)  # 1=Like , 0=None

    # 8.23) 좋아요 DB 저장 코드 추가
    def scan_like_to_db(self) -> None:
        """Redis 에 임시 저장된 data 를 DB 에 반영."""

        # 코드 진행 중 Redis 에서 처리된 데이터를 저장하기 위한 빈 list
        processed_keys: list[str] = []
        for key in self._redis.scan_iter(match="post_like:*"):
            _, post_id, user_id = key.split(":")  # 언패킹 post_like:10:3 -> _ , post_id, user_id
            post_id = int(post_id)
            user_id = int(user_id)
            status = self._redis.get(key)

            # 1. DB 에 이미 like data 가 있는지 조회
            statement = select(PostLike).where(
                PostLike.post_id == post_id,
                PostLike.user_id == user_id,
            )
            existing_like = self._db.scalars(statement).one_or_none()

            # 2-1. 만약 Redis에 값이 like고, DB는 비어있다면 add
            if status == "1" and existing_like is None:
                like = PostLike(
                    post_id=post_id,
                    user_id=user_id,
                )
                self._db.add(like)
            # 2-2. Redis는 none 인데 DB엔 like 가 있다면 삭제
            elif status == "0" and existing_like is not None:
                self._db.delete(existing_like)
            # 3. 확인이 끝난 행은 list 에 기록
            processed_keys.append(key)

        # 4. DB 에 저장 확정
        self._db.commit()
        # 5. Redis 임시 data 삭제
        if processed_keys:
            self._redis.delete(*processed_keys)  # *리스트변수명: 리스트 안의 인자를 언패킹

    # 좋아요 임시 저장 취소
    # 8.22) redis 추가
    def delete_like(self, post_id: int, user_id: int) -> None:
        key = f"post_like:{post_id}:{user_id}"
        self._redis.set(key, 0)

    # ------------------------------------------------------------------ 이미지

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
