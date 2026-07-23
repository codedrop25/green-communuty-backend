"""Alembic 실행 환경.

두 가지를 앱과 일치시키는 것이 이 파일의 핵심이다.

1. **접속 정보**: `alembic.ini` 에 URL 을 두지 않고 `app.core.config.settings` 에서 주입한다.
   설정 접근 경로를 앱과 하나로 통일하고, 비밀번호가 저장소에 커밋되지 않게 한다.
2. **모델 등록**: `model_registry` 를 import 해 모든 모델이 `Base.metadata` 에 올라온
   상태를 보장한다. 이것이 없으면 autogenerate 가 테이블을 인식하지 못해
   DROP TABLE 마이그레이션을 생성한다.

주의: `alembic.ini` 는 **ASCII 로만** 작성한다.
Alembic 이 ini 를 로케일 인코딩(한국어 Windows 는 cp949)으로 읽기 때문에,
UTF-8 한글 주석을 넣으면 Linux 컨테이너에서는 멀쩡하고 Windows 에서만
`UnicodeDecodeError` 로 죽는다. 한글 설명은 이 파일에 둔다.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.infrastructure.database.model_registry import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ini 대신 앱 설정에서 접속 URL 을 주입한다.
# `%` 는 configparser 의 보간 문자이므로, URL 에 포함될 경우를 대비해 이스케이프한다.
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """엔진 없이 SQL 스크립트만 생성하는 모드 (`alembic upgrade head --sql`)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # 컬럼 타입 변경(예: VARCHAR(50) -> VARCHAR(100))을 감지한다.
        # 기본값은 False 라서 타입만 바꾼 변경이 조용히 누락된다.
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """실제 DB 에 연결해 마이그레이션을 적용하는 모드."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        # 마이그레이션은 단발성 프로세스이므로 커넥션 풀을 두지 않는다.
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
