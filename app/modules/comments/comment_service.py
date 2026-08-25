"""Comment 비즈니스 로직."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.common.pagination import PageParams
from app.core.exceptions import ForbiddenError, NotFoundError
from app.modules.comments.comment_model import Comment
from app.modules.comments.comment_repository import CommentRepository
from app.modules.comments.comment_schemas import CommentCreate, CommentUpdate
from app.modules.posts.post_repository import PostRepository
from app.modules.users.user_model import User
from tests.conftest import redis_client


class CommentService:
    def __init__(self, db: Session) -> None:
        # DB 연결
        self._db = db

        # 댓글 Repository 사용
        self._repository = CommentRepository(db)

        # 게시글 확인
        self._posts = PostRepository(db, redis_client)

    # 게시글 댓글 목록 조회
    def list_by_post(
        self,
        post_id: int,
        params: PageParams,
    ) -> tuple[list[Comment], int, dict[int, int]]:
        # 게시글 존재 확인
        self._ensure_post_exists(post_id)

        # 댓글 목록, 전체 댓글 개수, 답글 개수 조회
        return self._repository.list_by_post(
            post_id,
            params,
        )

    # 댓글의 답글 목록 조회
    def list_by_parent(
        self,
        comment_id: int,
    ) -> list[Comment]:
        # 댓글 존재 확인
        comment = self._repository.get_by_id(comment_id)

        # 댓글이 없으면 오류
        if comment is None:
            raise NotFoundError("댓글을 찾을 수 없습니다.")

        # 해당 댓글의 답글 목록 조회
        return self._repository.list_by_parent(comment_id)

    # 댓글 및 답글 작성
    def create(
        self,
        post_id: int,
        author: User,
        payload: CommentCreate,
    ) -> Comment:
        # 게시글 존재 확인
        self._ensure_post_exists(post_id)

        # 답글 작성인 경우
        if payload.parent_comment_id is not None:
            # 답글을 작성할 기존 댓글 조회
            parent_comment = self._repository.get_parent_comment(
                payload.parent_comment_id,
            )

            # 기존 댓글이 없으면 작성 불가
            if parent_comment is None:
                raise NotFoundError("댓글을 찾을 수 없습니다.")

            # 다른 게시글의 댓글에는 답글 작성 불가
            if parent_comment.post_id != post_id:
                raise NotFoundError("해당 게시글의 댓글이 아닙니다.")

            # 답글에 다시 답글 작성 불가
            # 답글에 답하고 싶으면 @멘션 사용
            if parent_comment.parent_comment_id is not None:
                raise ForbiddenError("답글에는 다시 답글을 작성할 수 없습니다.")

        # 댓글 내용에 있는 멘션 확인
        self._validate_mentions(
            post_id,
            payload.content,
        )

        # 저장할 댓글 생성
        comment = Comment(
            content=payload.content,
            post_id=post_id,
            # 현재 로그인한 사용자 번호 저장
            author_id=author.user_id,
            # 일반 댓글이면 None, 답글이면 기존 댓글 번호 저장
            parent_comment_id=payload.parent_comment_id,
        )

        # 댓글 등록
        self._repository.add(comment)

        # 변경 내용 최종 저장
        self._db.commit()

        # 생성된 댓글 반환
        return comment

    # 댓글 수정
    def update(
        self,
        comment_id: int,
        current_user: User,
        payload: CommentUpdate,
    ) -> Comment:
        # 본인이 작성한 댓글인지 확인
        comment = self._get_owned(
            comment_id,
            current_user,
        )

        # 수정한 댓글 내용의 멘션 확인
        self._validate_mentions(
            comment.post_id,
            payload.content,
        )

        # 댓글 내용 수정
        comment.content = payload.content

        # 수정 내용 DB 반영
        self._repository.flush()

        # 변경 내용 최종 저장
        self._db.commit()

        # 수정된 댓글 반환
        return comment

    # 댓글 삭제 상태로 변경
    def delete(
        self,
        comment_id: int,
        current_user: User,
    ) -> None:
        # 본인이 작성한 댓글인지 확인
        comment = self._get_owned(
            comment_id,
            current_user,
        )

        # 현재 시간을 삭제 시간으로 저장
        comment.deleted_at = datetime.now(UTC).replace(tzinfo=None)

        # 삭제 상태 DB 반영
        self._repository.flush()

        # 변경 내용 최종 저장
        self._db.commit()

    # 게시글 존재 확인
    def _ensure_post_exists(
        self,
        post_id: int,
    ) -> None:
        if self._posts.get_by_id(post_id) is None:
            raise NotFoundError("게시글을 찾을 수 없습니다.")

    # 본인이 작성한 댓글인지 확인
    def _get_owned(
        self,
        comment_id: int,
        current_user: User,
    ) -> Comment:
        # 댓글 조회
        comment = self._repository.get_by_id(comment_id)

        # 댓글이 없으면 오류
        if comment is None:
            raise NotFoundError("댓글을 찾을 수 없습니다.")

        # 댓글 작성자 확인
        if comment.author_id != current_user.user_id:
            raise ForbiddenError("본인이 작성한 댓글만 수정/삭제할 수 있습니다.")

        return comment

    # 댓글 내용의 멘션 확인
    def _validate_mentions(
        self,
        post_id: int,
        content: str,
    ) -> None:
        # 댓글 내용을 띄어쓰기 기준으로 나눔
        words = content.split()

        # 댓글 내용을 하나씩 확인
        for word in words:
            # @로 시작하는 경우 멘션 확인
            if word.startswith("@"):
                # @를 제외하고 닉네임만 가져오기
                user_nickname = word[1:]

                # 닉네임이 없는 경우 넘어가기
                if not user_nickname:
                    continue

                # 비슷한 닉네임의 사용자 목록 조회
                users = self._repository.search_mention_users(
                    post_id,
                    user_nickname,
                )

                # 입력한 닉네임과 같은 사용자가 있는지 확인
                mention_user = None

                for user in users:
                    if user.user_nickname == user_nickname:
                        mention_user = user
                        break

                # 사용자가 없으면 멘션 불가
                if mention_user is None:
                    raise NotFoundError(f"멘션한 사용자 @{user_nickname}을 찾을 수 없습니다.")
