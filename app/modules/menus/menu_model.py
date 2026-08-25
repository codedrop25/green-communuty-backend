"""메뉴(카테고리) 테이블 정의.

트리 저장 방식은 인접 리스트(Adjacency List)를 쓴다.
각 행이 자기 부모의 id 만 들고 있는 구조라 깊이 제한이 없다.
"제약 없는 계층형 메뉴" 요구사항에 맞고, FK 를 걸지 않는 팀 규칙에서
데이터 중복이 가장 적어 정합성 관리 부담이 작다.

트레이드오프: 전체 트리 조회 시 쿼리가 늘어날 수 있다.
Repository 에서 한 번에 다 읽어와 메모리에서 조립하는 방식으로 완화했고,
추후 Redis 캐싱을 붙이는 것을 전제로 한다.
"""

from __future__ import annotations

# Index            조회 속도를 올리는 색인
# UniqueConstraint 중복을 막는 제약조건
from sqlalchemy import Index, Integer, String, UniqueConstraint

# Mapped        "이 속성은 DB 컬럼이다" 라고 알려주는 타입 표기
# mapped_column 기본키 여부, 길이, NULL 허용 같은 세부 설정
from sqlalchemy.orm import Mapped, mapped_column

# 모든 모델의 부모 클래스.
# 제약조건 이름 규칙(pk_ / uq_ / ix_)이 여기 정의돼 있어서
# Alembic 이 나중에 제약조건을 수정하거나 되돌릴 때 이름을 찾을 수 있다.
from app.infrastructure.database.base import Base

# 상속만 하면 컬럼이 자동으로 붙는 부품들.
#   TimestampMixin  → created_at, updated_at
#   SoftDeleteMixin → deleted_at
from app.infrastructure.database.mixins import SoftDeleteMixin, TimestampMixin


class Menu(Base, TimestampMixin, SoftDeleteMixin):
    """게시판 카테고리. 자기 자신을 부모로 참조하는 트리 구조."""

    # 실제 DB 테이블 이름
    __tablename__ = "menus"

    # 기본키. autoincrement 로 1, 2, 3... 자동 증가한다.
    menu_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 메뉴 이름. nullable=False 라 비워둘 수 없다.
    menu_name: Mapped[str] = mapped_column(String(50), nullable=False)

    # 부모 메뉴의 번호. int | None 은 "정수이거나 비어 있을 수 있다"는 뜻으로,
    # 비어 있으면(NULL) 최상위 메뉴다.
    # index=True : "이 메뉴의 자식들 다 가져와" 가 가장 잦은 조회라서 색인을 건다.
    # FK 는 팀 규칙에 따라 걸지 않으므로, 부모가 실제로 존재하는지는
    # Service 계층에서 직접 검증한다.
    menu_parent_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    # 컬럼이 아닌 테이블 전체 설정을 넣는 자리.
    __table_args__ = (
        # 같은 부모 아래 같은 이름 금지.
        # deleted_at 을 조합에 포함한 이유:
        # 논리 삭제된 행이 테이블에 그대로 남기 때문에, 이걸 빼면
        # 한 번 지웠던 이름을 다시 만들 수 없게 된다.
        UniqueConstraint("menu_parent_id", "menu_name", "deleted_at", name="uq_menus_parent_name"),
        # 모든 조회에 deleted_at IS NULL 조건이 붙으므로 색인을 건다.
        Index("ix_menus_deleted_at", "deleted_at"),
    )
