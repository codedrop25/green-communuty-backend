"""Auth DTO."""

from pydantic import BaseModel, EmailStr, Field

from app.modules.users.user_schemas import PasswordStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: PasswordStr


class TokenResponse(BaseModel):
    """토큰 발급 응답.

    Refresh Token 은 본문에 담지 않는다 (PLAN.md 4-4).
    HttpOnly 쿠키로만 내려보내 JavaScript 에서 읽을 수 없게 하고,
    XSS 가 발생하더라도 Refresh Token 은 탈취되지 않도록 한다.
    """

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access Token 만료까지 남은 초")


class MessageResponse(BaseModel):
    """본문에 담을 데이터가 없는 성공 응답 (로그아웃 등)."""

    message: str
