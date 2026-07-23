"""S3 호환 오브젝트 스토리지 클라이언트.

PLAN.md 6-1: 이번 범위에서는 **인프라 스텁**이다.
연결 설정과 기본 업로드/조회 메서드까지만 제공하고,
업로드 API 엔드포인트는 구현하지 않는다.

S3 설정이 비어 있어도 앱은 정상 기동해야 한다 (스토리지를 쓰지 않는 배포가 존재).
그래서 클라이언트를 모듈 로드 시점이 아니라 **첫 사용 시점에** 만든다.
"""

from functools import lru_cache
from typing import TYPE_CHECKING, BinaryIO

import boto3
from botocore.config import Config

from app.core.config import settings
from app.core.exceptions import StorageNotConfiguredError

if TYPE_CHECKING:
    from types_boto3_s3.client import S3Client


@lru_cache(maxsize=1)
def _build_client() -> "S3Client":
    """boto3 S3 클라이언트를 생성한다 (프로세스당 1회).

    `S3_ENDPOINT_URL` 을 지정하면 MinIO 등 S3 호환 스토리지로 붙고,
    비워 두면 AWS S3 로 붙는다.
    """
    if settings.S3_ACCESS_KEY is None or settings.S3_SECRET_KEY is None:
        raise StorageNotConfiguredError

    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY.get_secret_value(),
        aws_secret_access_key=settings.S3_SECRET_KEY.get_secret_value(),
        region_name=settings.S3_REGION,
        config=Config(
            # MinIO 등 호환 스토리지는 virtual-host 스타일 URL 을 지원하지 않는 경우가 많다.
            s3={"addressing_style": "path"},
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=3,
            read_timeout=10,
        ),
    )


class S3Storage:
    """오브젝트 스토리지 래퍼.

    boto3 를 직접 쓰지 않고 한 겹 감싸는 이유는, 버킷명·에러 처리 같은
    반복되는 관심사를 한 곳에 모으고 나중에 스토리지 교체 시
    이 클래스만 바꾸면 되게 하기 위함이다.
    """

    def __init__(self) -> None:
        if not settings.S3_BUCKET:
            raise StorageNotConfiguredError
        self._bucket = settings.S3_BUCKET
        self._client = _build_client()

    def upload(self, key: str, fileobj: BinaryIO, content_type: str | None = None) -> str:
        """파일 객체를 업로드하고 저장된 key 를 돌려준다."""
        extra = {"ContentType": content_type} if content_type else None
        self._client.upload_fileobj(fileobj, self._bucket, key, ExtraArgs=extra)
        return key

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """다운로드용 서명 URL 을 발급한다.

        버킷을 공개로 열지 않고도 클라이언트가 직접 내려받게 하는 표준 방식이다.
        """
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)


def get_storage() -> S3Storage:
    """스토리지 의존성.

    S3 설정이 없으면 `StorageNotConfiguredError` 가 발생하고,
    전역 예외 핸들러가 503 으로 변환한다.
    """
    return S3Storage()
