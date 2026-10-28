"""Settings 기동 시 검증 단위 테스트."""

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings

_SECRET_KEY = SecretStr("unit-test-secret-key-that-is-long-enough")


@pytest.mark.parametrize("environment", ["local", "dev"])
def test_db_synchronize_is_allowed_in_dev_environments(environment: str) -> None:
    settings = Settings(
        _env_file=None,
        ENVIRONMENT=environment,
        DB_SYNCHRONIZE=True,
        SECRET_KEY=_SECRET_KEY,
    )

    assert settings.DB_SYNCHRONIZE is True


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_db_synchronize_is_rejected_outside_dev_environments(environment: str) -> None:
    with pytest.raises(ValidationError, match="DB_SYNCHRONIZE"):
        Settings(
            _env_file=None,
            ENVIRONMENT=environment,
            DB_SYNCHRONIZE=True,
            SECRET_KEY=_SECRET_KEY,
        )
