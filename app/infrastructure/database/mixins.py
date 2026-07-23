"""모델 공통 Mixin.

시각 컬럼은 모두 **UTC 기준 naive datetime** 으로 저장한다.
MySQL 의 DATETIME 은 타임존 정보를 보관하지 못하므로, 어느 인스턴스에서 INSERT 하든
같은 기준이 되도록 커넥션 세션 타임존을 UTC 로 고정한다 (`session.py` 의 connect 이벤트 참고).
표시용 타임존 변환은 클라이언트/프레젠테이션 계층의 책임으로 둔다.
"""

from datetime import datetime

from sqlalchemy import DateTime, func, text
from sqlalchemy.orm import Mapped, mapped_column

# `func.now()` 가 아니라 텍스트를 쓰는 이유:
#   MySQL 은 `DEFAULT (now())` 를 표현식 기본값으로 보고 `(now())` 라고 되돌려주는데,
#   Alembic 은 메타데이터 쪽 `func.now()` 를 문자열로 렌더링하지 못한다.
#   그 결과 두 값을 비교할 수 없어, 바뀐 것이 없는데도 autogenerate 가
#   매번 같은 `alter_column` 을 만들어낸다.
#   `CURRENT_TIMESTAMP` 는 ANSI 표준이며 MySQL 도 동일한 문자열로 보고하므로
#   양쪽 표기가 일치해 오탐이 발생하지 않는다.
_NOW = text("CURRENT_TIMESTAMP")


class TimestampMixin:
    """생성/수정 시각.

    `created_at` 은 **서버(DB) 기본값**으로 채운다.
    ORM 을 거치지 않는 마이그레이션 스크립트나 수동 SQL 로 INSERT 하더라도
    감사(audit) 컬럼이 비지 않도록 하기 위함이다.

    `updated_at` 의 `onupdate` 는 **ORM 이 UPDATE 문을 만들 때** 값을 채우는 방식이다.
    즉 이 앱을 통한 수정에만 적용되고, DB 에 직접 실행한 raw UPDATE 는 갱신되지 않는다.
    MySQL 의 `ON UPDATE CURRENT_TIMESTAMP` 를 쓰면 그것까지 잡을 수 있지만,
    MySQL 전용 DDL 이라 이식성을 잃으므로 채택하지 않았다.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=_NOW,
        comment="생성 시각 (UTC)",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=_NOW,
        # onupdate 는 ORM 이 UPDATE 문을 만들 때 적용된다 (DDL 이 아니므로 오탐과 무관).
        onupdate=func.now(),
        comment="수정 시각 (UTC)",
    )


class SoftDeleteMixin:
    """논리 삭제 (PLAN.md 6-3).

    `deleted_at IS NULL` 필터는 전역 이벤트 훅으로 자동 주입하지 않고
    **Repository 에서 명시적으로** 건다.
    자동 주입은 "왜 이 행이 안 나오지?" 류의 디버깅을 매우 어렵게 만들기 때문이다.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        default=None,
        index=True,
        comment="논리 삭제 시각 (UTC). NULL 이면 미삭제",
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
