"""User DTO."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.security import BCRYPT_MAX_PASSWORD_BYTES
from app.modules.users.user_model import UserRole

# bcrypt 는 72바이트를 넘는 입력을 잘라내므로, 그 길이를 상한으로 못 박는다.
# 상한이 없으면 "앞 72바이트만 같아도 로그인되는" 상태가 조용히 만들어진다.
# ASCII 기준 최대 길이로 환산해 사용한다.
PasswordStr = Annotated[str, Field(min_length=8, max_length=BCRYPT_MAX_PASSWORD_BYTES)]
NicknameStr = Annotated[str, Field(min_length=2, max_length=50)]


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
    user_created_at: datetime
