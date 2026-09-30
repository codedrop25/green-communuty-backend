"""Post 비즈니스 로직.

소유권 검증을 Router가 아닌 Service에서 하는 이유:
Router에만 두면 배치 작업이나 다른 서비스에서 호출할 때 검증이 우회될 수 있다.
"""

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, ImageOps
from redis import Redis
from sqlalchemy.orm import Session

from app.common.dependencies import CurrentUser
from app.common.pagination import PageParams
from app.core.exceptions import ForbiddenError, NotFoundError
from app.infrastructure.storage.base import Storage
from app.modules.posts.post_model import Post
from app.modules.posts.post_repository import PostRepository
from app.modules.posts.post_schemas import (
    PostCreate,
    PostDetailResponse,
    PostImageResponse,
    PostShareResponse,
    PostSummaryResponse,
    PostUpdate,
)
from app.modules.reports.report_repository import ReportRepository
from app.modules.users.user_model import User, UserRole

MAX_IMAGE_HEIGHT_PX = 15_000
MAX_CONTENT_WIDTH_PX = 1_600


class PostService:
    def __init__(
        self,
        db: Session,
        redis: Redis,
        storage: Storage,
    ) -> None:
        """게시글 기능에 필요한 DB, Redis, Storage를 준비한다."""

        self._db = db
        self._report_repository = ReportRepository(db)
        self._post_repository = PostRepository(db, redis)

        # 설정에 따라 S3Storage 또는 R2Storage가 전달된다.
        self._storage = storage

    # ------------------------------------------------------------------ 조회

    def get_detail(
        self,
        post_id: int,
        current_user: CurrentUser,
    ) -> PostDetailResponse:
        """게시글 상세 정보를 조회한다."""

        row = self._post_repository.get_detail(post_id)

        if row is None:
            raise NotFoundError("게시글을 찾을 수 없습니다.")

        post, author = row

        # 게시글 작성자가 아닌 경우에만 조회수를 증가시킨다.
        is_author = post.author_id == current_user.user_id

        if not is_author:
            post.post_view_count += 1
            self._post_repository.flush()

        # 게시글의 좋아요 정보도 함께 조회한다.
        post_like_count = self._post_repository.count_likes(post_id)
        is_liked = self._post_repository.get_like(
            post_id,
            current_user.user_id,
        )

        return PostDetailResponse.from_entities(
            post,
            author,
            post.post_view_count,
            post_like_count,
            is_liked,
        )

    def list_posts(
        self,
        params: PageParams,
        current_user: CurrentUser,
    ) -> tuple[list[tuple[Post, User]], int]:
        """게시글 목록을 조회한다."""

        # 아직 PostRepository에 get_filter_words()가 없으므로
        # 필터링하지 않는 빈 집합을 임시로 전달한다.
        filter_words: set[str] = set()

        return self._post_repository.list_paginated(
            params,
            filter_words,
        )

    # ---------------------------------------------------------- 생성/수정/삭제

    def create(
        self,
        author: User,
        payload: PostCreate,
    ) -> PostSummaryResponse:
        """새로운 게시글을 등록한다."""

        post = Post(
            post_title=payload.post_title,
            post_content=payload.post_content,
            author_id=author.user_id,
        )

        self._post_repository.add(post)
        self._db.commit()

        return PostSummaryResponse.from_entities(post, author)

    def update(
        self,
        post_id: int,
        current_user: User,
        payload: PostUpdate,
    ) -> PostDetailResponse:
        """작성자가 게시글을 수정한다."""

        post = self._get_owned(post_id, current_user)

        # 실제 요청으로 전달된 필드만 가져온다.
        changes = payload.model_dump(exclude_unset=True)

        # 전달받은 필드의 값을 Post 객체에 적용한다.
        for field, value in changes.items():
            setattr(post, field, value)

        self._post_repository.flush()
        self._db.commit()

        # 수정된 게시글을 상세 응답 형태로 다시 조회한다.
        return self.get_detail(post_id, current_user)

    def delete(
        self,
        post_id: int,
        current_user: User,
    ) -> None:
        """게시글을 논리적으로 삭제한다."""

        post = self._get_owned(post_id, current_user)

        # 실제 행을 삭제하지 않고 삭제 시각을 기록한다.
        post.deleted_at = datetime.now(UTC).replace(tzinfo=None)

        self._post_repository.flush()
        self._db.commit()

    # ------------------------------------------------------------------ 인가

    def _get_owned(
        self,
        post_id: int,
        current_user: User,
    ) -> Post:
        """게시글 조회와 수정 권한 검사를 함께 수행한다."""

        post = self._post_repository.get_by_id(post_id)

        if post is None:
            raise NotFoundError("게시글을 찾을 수 없습니다.")

        # 작성자 또는 관리자만 게시글을 수정할 수 있다.
        if post.author_id != current_user.user_id and current_user.user_role != UserRole.ADMIN:
            raise ForbiddenError("본인이 작성한 게시글만 수정/삭제할 수 있습니다.")

        return post

    # ------------------------------------------------------------------ 좋아요

    def like_post(
        self,
        post_id: int,
        current_user: CurrentUser,
    ) -> None:
        """게시글에 좋아요를 등록한다."""

        post = self._post_repository.get_by_id(post_id)

        if post is None:
            raise NotFoundError("게시글을 찾을 수 없습니다.")

        existing_like = self._post_repository.get_like(
            post_id,
            current_user.user_id,
        )

        # 이미 좋아요를 눌렀다면 중복 등록하지 않는다.
        if existing_like:
            return

        # Redis에 좋아요 상태를 임시로 저장한다.
        self._post_repository.add_like(
            post_id,
            current_user.user_id,
        )

    def unlike_post(
        self,
        post_id: int,
        current_user: CurrentUser,
    ) -> None:
        """게시글 좋아요를 취소한다."""

        like = self._post_repository.get_like(
            post_id,
            current_user.user_id,
        )

        # 등록된 좋아요가 없다면 취소할 것도 없다.
        if not like:
            return

        self._post_repository.delete_like(
            post_id,
            current_user.user_id,
        )

    # ------------------------------------------------------------------ 공유

    def get_share_url(
        self,
        post_id: int,
    ) -> PostShareResponse:
        """게시글 공유 주소를 반환한다."""

        post = self._post_repository.get_by_id(post_id)

        if post is None:
            raise NotFoundError("게시글을 찾을 수 없습니다.")

        share_url = f"http://localhost:5173/posts/{post_id}"

        return PostShareResponse(
            share_url=share_url,
        )

    # ------------------------------------------------------------------ 이미지

    def upload_image(
        self,
        post_id: int,
        current_user: CurrentUser,
        image: UploadFile,
    ) -> PostImageResponse:
        """원본, 본문용, 썸네일 이미지를 스토리지에 저장한다."""

        post = self._post_repository.get_by_id(post_id)

        if post is None:
            raise NotFoundError("게시글을 찾을 수 없습니다.")

        if post.author_id != current_user.user_id:
            raise ForbiddenError("본인이 작성한 게시글에만 이미지를 추가할 수 있습니다.")

        # TODO: 파일 형식, 확장자, 용량 제한 검사
        # self._validate_image(image)

        # 원본 파일의 확장자를 가져온다.
        suffix = Path(image.filename or "").suffix.lower()

        # 업로드된 파일 전체를 bytes로 읽는다.
        original_data = image.file.read()

        # 원본을 본문용 이미지와 썸네일 이미지로 변환한다.
        content_data = self._resize_image(
            original_data,
            max_width=MAX_CONTENT_WIDTH_PX,
        )
        thumbnail_data = self._create_thumbnail_image(
            original_data,
        )

        # 파일 이름이 중복되지 않도록 UUID를 생성한다.
        file_id = uuid4()

        # 원본은 사용자가 업로드한 확장자를 유지한다.
        original_key = f"posts/{post_id}/original/{file_id}{suffix}"

        # 변환된 이미지는 실제 데이터 형식에 맞춰 webp를 사용한다.
        content_key = f"posts/{post_id}/content/{file_id}.webp"
        thumbnail_key = f"posts/{post_id}/thumbnail/{file_id}.webp"

        try:
            # bytes를 BytesIO로 감싸 파일 객체처럼 전달한다.
            self._storage.upload(
                key=original_key,
                fileobj=BytesIO(original_data),
                content_type=image.content_type,
            )

            self._storage.upload(
                key=content_key,
                fileobj=BytesIO(content_data),
                content_type="image/webp",
            )

            self._storage.upload(
                key=thumbnail_key,
                fileobj=BytesIO(thumbnail_data),
                content_type="image/webp",
            )

            # DB에는 스토리지에 저장된 객체 키만 기록한다.
            post_image = self._post_repository.add_image(
                post_id=post_id,
                image_original_path=original_key,
                image_content_path=content_key,
                image_thumbnail_path=thumbnail_key,
            )

            self._db.commit()

        except Exception:
            # DB 작업에 실패했다면 DB 변경을 취소한다.
            self._db.rollback()
            raise

        return PostImageResponse(
            image_id=post_image.image_id,
            post_id=post_image.post_id,
            # 1시간 동안 사용할 수 있는 임시 이미지 URL을 발급한다.
            image_url=self._storage.generate_presigned_url(
                key=content_key,
                expires_in=3600,
            ),
        )

    @staticmethod
    def _resize_image(
        original_data: bytes,
        max_width: int,
    ) -> bytes:
        """이미지 비율을 유지하면서 본문용 크기로 축소한다."""

        # bytes 데이터를 Pillow 이미지로 연다.
        with Image.open(BytesIO(original_data)) as opened_image:
            # EXIF 회전 정보를 실제 이미지 방향에 적용한다.
            image = ImageOps.exif_transpose(opened_image)

            # 세로가 지나치게 긴 이미지는 업로드하지 않는다.
            if image.height > MAX_IMAGE_HEIGHT_PX:
                raise ValueError("이미지 길이는 15000px 이하까지만 업로드할 수 있습니다.")

            # 이미지가 투명도 정보를 가지고 있는지 확인한다.
            has_transparency = image.mode in {"RGBA", "LA"} or (
                image.mode == "P" and "transparency" in image.info
            )

            # 투명도가 있으면 RGBA, 없으면 RGB로 변환한다.
            image = image.convert("RGBA" if has_transparency else "RGB")

            # 비율을 유지하면서 최대 가로 크기 이하로 줄인다.
            image.thumbnail(
                (max_width, MAX_IMAGE_HEIGHT_PX),
                Image.Resampling.LANCZOS,
            )

            # 변환된 이미지를 메모리에 저장할 공간이다.
            output = BytesIO()

            # 실제 데이터 형식을 WebP로 변환한다.
            image.save(
                output,
                format="WEBP",
                quality=85,
            )

            return output.getvalue()

    @staticmethod
    def _create_thumbnail_image(
        original_data: bytes,
    ) -> bytes:
        """이미지를 300×300 크기의 WebP 썸네일로 변환한다."""

        with Image.open(BytesIO(original_data)) as opened_image:
            # EXIF 회전을 적용하고 투명도 처리를 위해 RGBA로 변환한다.
            image = ImageOps.exif_transpose(opened_image).convert("RGBA")

            # 투명한 부분을 흰 배경과 합성한 후 RGB로 변환한다.
            image = Image.alpha_composite(
                Image.new("RGBA", image.size, "white"),
                image,
            ).convert("RGB")

            # 세로형 이미지는 중앙을 자른다.
            # 가로형 이미지는 위아래에 흰 여백을 추가한다.
            image = (
                ImageOps.fit(
                    image,
                    (300, 300),
                    method=Image.Resampling.LANCZOS,
                    centering=(0.5, 0.5),
                )
                if image.height >= image.width
                else ImageOps.pad(
                    image,
                    (300, 300),
                    method=Image.Resampling.LANCZOS,
                    color="white",
                )
            )

            output = BytesIO()

            # 썸네일을 WebP 데이터로 저장한다.
            image.save(
                output,
                format="WEBP",
                quality=80,
            )

            return output.getvalue()
