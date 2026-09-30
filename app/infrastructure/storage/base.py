"""오브젝트 스토리지가 기본으로 제공해야 하는 기능."""

# * abc: abstract base class, 추상 기반 클래스를 만들기 위한 파이썬 기본 제공 모듈
from abc import ABC, abstractmethod
from typing import BinaryIO


class Storage(ABC):
    """S3 과 R2 스토리지가 따라야 하는 공통규칙.
    실제 코드는 각 스토리지에서 상속받아서 구현한다.
    """

    @abstractmethod
    def upload(
        self,
        key: str,
        fileobj: BinaryIO,
        content_type: str | None = None,
    ) -> str:
        """파일을 스토리지에 업로드하고 객체 키를 반환한다."""
        raise NotImplementedError

    @abstractmethod
    def generate_presigned_url(self, key: str, expires_in: int) -> str:
        """클리이언트가 파일을 조회할 수 있는 url 을 반환한다."""
        raise NotImplementedError

    # @abstractmethod
    # def soft_delete(self,key:str) -> None:
    #     """스토리지에서 파일을 삭제한다."""
    #     raise NotImplementedError
