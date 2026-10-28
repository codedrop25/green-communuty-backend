"""User DTO."""

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.core.security import BCRYPT_MAX_PASSWORD_BYTES
from app.modules.users.user_model import UserRole


def validate_password_bytes(value: str) -> str:
    # bcrypt 5는 글자 수가 아닌 UTF-8 바이트 수가 72를 넘으면 예외를 발생시킨다.
    if len(value.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError("비밀번호는 UTF-8 기준 72바이트 이내로 입력해주세요.")
    return value


PasswordStr = Annotated[
    str,
    Field(min_length=8, max_length=BCRYPT_MAX_PASSWORD_BYTES),
    AfterValidator(validate_password_bytes),
]
NicknameStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=50)]


class UserCreate(BaseModel):
    """회원가입 요청."""

    user_email: EmailStr
    user_password: PasswordStr
    user_nickname: NicknameStr


class UserUpdate(BaseModel):
    """프로필 수정 요청. 주어진 필드만 변경한다."""

    user_nickname: NicknameStr | None = None


class UserResponse(BaseModel):
    """유저 응답.

    `password_hash` 는 절대 포함하지 않는다.
    ORM 모델을 그대로 반환하지 않고 이 DTO 로 필드를 화이트리스트하는 이유가 이것이다.
    """

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    user_email: EmailStr
    user_nickname: str
    user_role: UserRole
    user_is_active: bool
    user_created_at: datetime = Field(validation_alias="created_at")
