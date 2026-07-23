"""애플리케이션 전역 설정.

설계 원칙 (PLAN.md 3-1):
    - 모든 설정값은 이 모듈의 `settings` 를 통해서만 접근한다.
      `os.environ` 직접 접근은 ruff 규칙(TID251)으로 차단되어 있다.
    - 비밀값은 `SecretStr` 로 선언한다. 실수로 로깅하거나 예외 메시지에 포함되어도
      `**********` 로 마스킹되므로, 사고의 1차 방어선이 된다.
    - 잘못된 조합(예: threadpool > 커넥션 풀)은 런타임에 장애로 드러나기 전에
      기동 시점에 `ValidationError` 로 즉시 실패시킨다.
"""

from functools import cached_property
from typing import Literal
from urllib.parse import quote_plus

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "dev", "staging", "production"]

# 개발 편의를 위한 기본 SECRET_KEY. 운영 환경에서 이 값이 그대로 쓰이면 기동을 막는다.
# 길이를 아래 최소값 이상으로 맞춰 로컬에서도 PyJWT 경고가 뜨지 않게 한다.
_INSECURE_SECRET_KEY = "change-me-in-production-this-is-not-a-secret"

# RFC 7518 3.2: HMAC 키는 해시 출력 크기(SHA-256 = 32바이트) 이상이어야 한다.
# 이보다 짧으면 서명 강도가 알고리즘이 보장하는 수준에 못 미친다.
MIN_SECRET_KEY_BYTES = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        # OS 환경 변수에는 이 앱과 무관한 값이 많으므로 미정의 항목은 무시한다.
        extra="ignore",
    )

    # ---------------------------------------------------------------- 앱
    ENVIRONMENT: Environment = "local"
    PROJECT_NAME: str = "community-backend"
    API_V1_PREFIX: str = "/api/v1"

    # ---------------------------------------------------------------- 보안 / JWT
    SECRET_KEY: SecretStr = SecretStr(_INSECURE_SECRET_KEY)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, ge=1)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=14, ge=1)

    # ---------------------------------------------------------------- CORS / 쿠키
    # pydantic-settings 는 list 타입 필드를 JSON 으로 파싱하려 시도하므로,
    # 콤마 구분 문자열을 그대로 받고 `cors_origins` 프로퍼티에서 분해한다.
    CORS_ORIGINS: str = "http://localhost:3000"

    # PLAN.md 4-4: Refresh Token 을 HttpOnly 쿠키로 전달할 때의 속성.
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"

    # ---------------------------------------------------------------- Rate Limit
    # PLAN.md 4-3: 로그인 brute-force 방어. 적용 대상은 POST /auth/login 한 곳뿐이다.
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = Field(default=5, ge=1)
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = Field(default=300, ge=1)

    # ---------------------------------------------------------------- MySQL
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "app"
    MYSQL_PASSWORD: SecretStr = SecretStr("app")
    MYSQL_DB: str = "community"

    DB_POOL_SIZE: int = Field(default=20, ge=1)
    DB_MAX_OVERFLOW: int = Field(default=30, ge=0)
    DB_POOL_TIMEOUT: int = Field(default=30, ge=1)
    DB_ECHO: bool = False

    # PLAN.md 3-3: `def` 라우터가 실행되는 AnyIO threadpool 크기.
    # 이 값이 커넥션 풀 총량보다 크면 QueuePool 타임아웃이 발생한다 (아래 검증 로직 참고).
    THREADPOOL_MAX_WORKERS: int = Field(default=40, ge=1)

    # ---------------------------------------------------------------- Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: SecretStr | None = None
    REDIS_DB: int = 0

    # ---------------------------------------------------------------- S3
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY: SecretStr | None = None
    S3_SECRET_KEY: SecretStr | None = None
    S3_BUCKET: str | None = None
    S3_REGION: str = "ap-northeast-2"

    # ================================================================ 정규화

    @field_validator(
        "REDIS_PASSWORD",
        "S3_ENDPOINT_URL",
        "S3_ACCESS_KEY",
        "S3_SECRET_KEY",
        "S3_BUCKET",
        mode="before",
    )
    @classmethod
    def _empty_str_to_none(cls, value: object) -> object:
        """`.env` 에서 `KEY=` 로 비워둔 항목을 None 으로 정규화한다.

        빈 문자열을 그대로 두면 "값이 없음"이 아니라 "빈 값이 설정됨"으로 취급된다.
        예를 들어 REDIS_PASSWORD 가 빈 문자열이면 접속 URL 이 `redis://:@host` 가 되어
        비밀번호가 없는 Redis 에 빈 AUTH 를 시도하다 연결이 실패한다.
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value

    # ================================================================ 파생 값

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @cached_property
    def cors_origins(self) -> list[str]:
        """콤마 구분 문자열을 Origin 리스트로 분해한다."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @cached_property
    def database_url(self) -> str:
        """SQLAlchemy 접속 URL.

        비밀번호에 `@`, `:`, `/` 같은 문자가 있으면 URL 파싱이 깨지므로 반드시 인코딩한다.
        charset 은 이모지 저장을 위해 utf8mb4 를 강제한다 (PLAN.md 7-2).
        """
        user = quote_plus(self.MYSQL_USER)
        password = quote_plus(self.MYSQL_PASSWORD.get_secret_value())
        return (
            f"mysql+pymysql://{user}:{password}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
            f"?charset=utf8mb4"
        )

    @cached_property
    def redis_url(self) -> str:
        password = (
            f":{quote_plus(self.REDIS_PASSWORD.get_secret_value())}@"
            if self.REDIS_PASSWORD is not None
            else ""
        )
        return f"redis://{password}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ================================================================ 기동 시 검증

    @model_validator(mode="after")
    def _validate_secret_key(self) -> "Settings":
        """운영 환경에서 기본 SECRET_KEY 사용을 차단한다.

        JWT 서명 키가 공개된 기본값이면 누구나 임의의 유저로 토큰을 위조할 수 있다.
        배포 실수를 런타임 취약점이 아니라 기동 실패로 바꾼다.

        길이도 함께 검증한다. PyJWT 는 짧은 키에 경고만 내고 서명을 진행하므로,
        경고를 놓치면 약한 키로 운영에 나갈 수 있다.
        """
        secret = self.SECRET_KEY.get_secret_value()

        if self.is_production and secret == _INSECURE_SECRET_KEY:
            raise ValueError(
                "운영 환경에서는 SECRET_KEY 를 반드시 별도 값으로 설정해야 합니다. "
                '예: python -c "import secrets; print(secrets.token_urlsafe(64))"'
            )

        if len(secret.encode("utf-8")) < MIN_SECRET_KEY_BYTES:
            raise ValueError(
                f"SECRET_KEY 는 최소 {MIN_SECRET_KEY_BYTES}바이트 이상이어야 합니다 "
                f"(현재 {len(secret.encode('utf-8'))}바이트). "
                "RFC 7518 기준 HS256 의 최소 권장 키 길이입니다."
            )
        return self

    @model_validator(mode="after")
    def _validate_pool_capacity(self) -> "Settings":
        """PLAN.md 3-3: threadpool worker 수 <= DB 커넥션 총량.

        Sync 스택에서는 `def` 라우터 하나당 스레드 하나가 커넥션 하나를 점유한다.
        worker 가 커넥션보다 많으면 초과분은 풀을 기다리다
        `TimeoutError: QueuePool limit ... reached` 로 실패한다.
        부하가 걸려야 드러나는 장애이므로 기동 시점에 못 박는다.
        """
        capacity = self.DB_POOL_SIZE + self.DB_MAX_OVERFLOW
        if self.THREADPOOL_MAX_WORKERS > capacity:
            raise ValueError(
                f"THREADPOOL_MAX_WORKERS({self.THREADPOOL_MAX_WORKERS}) 가 "
                f"DB 커넥션 총량({capacity} = DB_POOL_SIZE {self.DB_POOL_SIZE} "
                f"+ DB_MAX_OVERFLOW {self.DB_MAX_OVERFLOW}) 보다 큽니다. "
                "부하 시 QueuePool 타임아웃이 발생하므로 두 값을 맞춰주세요."
            )
        return self

    @model_validator(mode="after")
    def _validate_cookie_policy(self) -> "Settings":
        """SameSite=None 쿠키는 브라우저가 Secure 를 함께 요구한다.

        조합이 어긋나면 브라우저가 쿠키를 조용히 버려서
        "로그인은 되는데 토큰 재발급만 안 되는" 재현 어려운 버그가 된다.
        """
        if self.COOKIE_SAMESITE == "none" and not self.COOKIE_SECURE:
            raise ValueError(
                "COOKIE_SAMESITE=none 은 COOKIE_SECURE=true 를 함께 설정해야 합니다 "
                "(브라우저가 Secure 없는 SameSite=None 쿠키를 거부합니다)."
            )
        return self


settings = Settings()
