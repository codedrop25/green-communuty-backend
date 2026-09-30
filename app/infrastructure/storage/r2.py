"""R2 오브젝트 스토리지 클라이언트."""

from typing import BinaryIO

import boto3

from app.core.config import settings
from app.core.exceptions import StorageNotConfiguredError
from app.infrastructure.storage.base import Storage


class R2Storage(Storage):
    """Cloudflare R2 안에 파일을 저장하고 조회하는 클래스."""

    def __init__(self) -> None:
        """R2 연결 준비: 객체가 실행될때 자동으로 실행되는 초기화 메서드.
        설정을 확인하고, 버킷 이름을 저장한다."""
        # 1.만약 R2 연결에 필요한 인증, 계정, 버킷 정보가 부족하다면 -> 사용 중단
        if (
            settings.R2_ACCESS_KEY_ID is None
            or settings.R2_SECRET_ACCESS_KEY is None
            or not settings.R2_ACCOUNT_ID
            or not settings.R2_BUCKET_NAME
        ):
            raise StorageNotConfiguredError
        # 2.이후 메서드에서 사용할 버킷 이름을 객체에 저장한다.
        self._bucket = settings.R2_BUCKET_NAME
        # 3.S3 호환 API 를 사용해 Cloudflare R2 클라이언트를 만든다.
        self._client = boto3.client(
            "s3",
            endpoint_url=(f"http://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"),
            aws_access_key_id=(settings.R2_ACCESS_KEY_ID.get_secret_value()),
            aws_secret_access_key=(settings.R2_SECRET_ACCESS_KEY.get_secret_value()),
            region_name=settings.R2_REGION,
        )

    def upload(self, key: str, fileobj: BinaryIO, content_type: str | None = None) -> str:
        """파일 저장: 파일 객체를 R2 에 업로드 하고 객체키를 반환한다."""
        # 1.Content_Type이 있다면 R2에 함께 저장할 설정을 만든다.
        extra = {"ContentType": content_type} if content_type else None
        # 2.파일 객체를 지정한 버킷과 객체 키로 업로드 한다.
        self._client.upload_fileobj(
            fileobj,
            self._bucket,
            key,
            ExtraArgs=extra,
        )
        # 3.DB 에 저장할 객체 키를 반환한다.
        return key

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """임시 조회 URL 생성: 비공개 R2 객체를 조회할 임시 URL 을 생성한다."""
        # 1.임시 URL 로 조회할 버킷과 객체 키를 지정한다.
        params = {
            "Bucket": self._bucket,
            "Key": key,
        }
        # 2.지정한 객체를 조회할 수 있는 임시 URL 을 생성하여 반환한다.
        # * .generate_presigned_url() : 인증시간, 만료시간을 포함한 임시 URL을 생성하는 boto3 메서드
        return self._client.generate_presigned_url(
            ClientMethod="get_object",  # 허용권한 설정
            Params=params,  # 어느 버킷의 어느 객체를 조회할지 알려줌
            ExpiresIn=expires_in,  # URL 유효시간을 초 단위로 전달
        )

    # def delete(self, key: str) -> None:
    #     """파일 삭제: 실제 data 는 유지하되, R2에서 객체를 조회할시 제외한다."""
    #     pass
