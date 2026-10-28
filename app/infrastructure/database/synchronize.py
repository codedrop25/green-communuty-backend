"""모델 → DB 스키마 자동 동기화 (TypeORM 의 `synchronize: true` 에 해당).

`DB_SYNCHRONIZE=true` 이면 앱 기동 시 모델(`Base.metadata`)과 실제 DB 를 비교해
차이를 즉시 DB 에 반영한다. Alembic autogenerate 의 비교 엔진을 그대로 쓰되,
마이그레이션 파일을 만들지 않고 비교 결과로 나온 작업(op)을 바로 실행한다.

주의:
    - **삭제까지 반영한다.** 모델에서 지운 테이블/컬럼/인덱스는 DB 에서도 DROP 된다.
      컬럼 이름 변경은 "기존 컬럼 DROP + 새 컬럼 ADD" 로 인식되므로 그 컬럼의 데이터는 사라진다.
    - MySQL 의 DDL 은 트랜잭션으로 묶이지 않는다(문장마다 암묵적 commit).
      중간에 실패하면 앞서 실행된 변경은 그대로 남는다.
    - local/dev 전용이다. 그 외 환경에서 켜면 `Settings` 검증이 기동을 막는다.
    - 동기화로 바뀐 스키마는 Alembic 이력(alembic_version)에 남지 않는다.
      운영 반영은 지금처럼 `make migration` 으로 마이그레이션 파일을 만들어야 한다.

적용 전 미리보기 (DB 를 바꾸지 않고 실행될 작업만 출력):
    make sync-preview
"""

from typing import Any

from alembic.autogenerate import produce_migrations
from alembic.operations import Operations
from alembic.operations.ops import MigrateOperation
from alembic.runtime.migration import MigrationContext
from sqlalchemy.engine import Connection
from sqlalchemy.sql.schema import SchemaItem

from app.core.logging_config import get_logger
from app.infrastructure.database.model_registry import Base
from app.infrastructure.database.session import engine

logger = get_logger(__name__)

# Alembic 이 관리하는 버전 테이블. 모델에 없다는 이유로 DROP 하면 마이그레이션 이력이 사라진다.
ALEMBIC_VERSION_TABLE = "alembic_version"


def _include_object(
    _object: SchemaItem,
    name: str | None,
    type_: str,
    _reflected: bool,
    _compare_to: SchemaItem | None,
) -> bool:
    """비교 대상에서 Alembic 버전 테이블을 제외한다."""
    return not (type_ == "table" and name == ALEMBIC_VERSION_TABLE)


def _configure_context(connection: Connection) -> MigrationContext:
    """`alembic/env.py` 와 같은 비교 옵션으로 MigrationContext 를 만든다."""
    opts: dict[str, Any] = {
        "compare_type": True,
        "compare_server_default": True,
        "include_object": _include_object,
    }
    return MigrationContext.configure(connection, opts=opts)


def _collect_operations(context: MigrationContext) -> list[MigrateOperation]:
    """모델과 DB 의 차이를 실행 가능한 단일 작업 목록으로 펼친다.

    autogenerate 결과는 테이블 단위 묶음(ModifyTableOps) 안에 하위 작업을 품고 있다.
    묶음을 만나면 그 자리에 하위 작업을 끼워 넣어, autogenerate 가 정한 실행 순서
    (예: 인덱스 DROP → 컬럼 DROP)를 그대로 유지한다.
    """
    upgrade_ops = produce_migrations(context, Base.metadata).upgrade_ops
    if upgrade_ops is None:
        return []

    operations: list[MigrateOperation] = []
    pending: list[MigrateOperation] = list(upgrade_ops.ops)
    while pending:
        operation = pending.pop(0)
        children = getattr(operation, "ops", None)
        if children is not None:
            pending[0:0] = children
        else:
            operations.append(operation)
    return operations


def _describe(operation: MigrateOperation) -> str:
    """로그용 한 줄 설명. 예) AddColumnOp table=posts column=post_menu_id"""
    parts = [type(operation).__name__]
    table_name = getattr(operation, "table_name", None)
    if table_name:
        parts.append(f"table={table_name}")
    column = getattr(operation, "column", None)
    column_name = getattr(column, "name", None) or getattr(operation, "column_name", None)
    if column_name:
        parts.append(f"column={column_name}")
    for attr in ("index_name", "constraint_name"):
        value = getattr(operation, attr, None)
        if value:
            parts.append(f"{attr.removesuffix('_name')}={value}")
    return " ".join(parts)


def preview_synchronize() -> list[str]:
    """DB 를 바꾸지 않고, 동기화 시 실행될 작업 목록만 돌려준다."""
    with engine.connect() as connection:
        return [_describe(op) for op in _collect_operations(_configure_context(connection))]


def synchronize_database() -> int:
    """모델과 DB 의 차이를 DB 에 반영하고, 실행한 작업 수를 돌려준다."""
    with engine.begin() as connection:
        context = _configure_context(connection)
        operations = _collect_operations(context)
        if not operations:
            logger.info("db_synchronize_up_to_date")
            return 0

        executor = Operations(context)
        for operation in operations:
            # 스키마 변경(특히 DROP)은 되돌릴 수 없으므로 하나하나 눈에 띄게 남긴다.
            logger.warning("db_synchronize_apply", operation=_describe(operation))
            executor.invoke(operation)

    logger.info("db_synchronize_completed", applied=len(operations))
    return len(operations)


if __name__ == "__main__":
    planned = preview_synchronize()
    if not planned:
        print("모델과 DB 스키마가 일치합니다. 실행할 작업이 없습니다.")
    else:
        print(f"DB_SYNCHRONIZE=true 로 기동하면 아래 {len(planned)}개 작업이 실행됩니다.")
        for line in planned:
            print(f"  - {line}")
