"""SQLAlchemy Declarative Base.

모든 ORM 모델은 이 `Base` 를 상속한다.
Alembic 의 autogenerate 는 `Base.metadata` 를 기준으로 스키마 차이를 계산하므로,
모델이 여기에 등록되지 않으면 마이그레이션에서 조용히 누락된다.
(등록 보장은 `model_registry.py` 참고)
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# 제약조건 이름을 규칙으로 고정한다.
# 이름을 DB 가 자동 생성하도록 두면 Alembic 이 downgrade 나 제약 변경 시
# 대상 이름을 특정하지 못해 마이그레이션이 실패한다.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
