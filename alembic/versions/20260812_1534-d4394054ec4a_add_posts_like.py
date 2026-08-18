"""add posts like

Revision ID: d4394054ec4a
Revises: 70998f3f80d7
Create Date: 2026-08-12 15:34:53.317865
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4394054ec4a"
down_revision: str | Sequence[str] | None = "70998f3f80d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    # ------------------------------------------------------------
    # posts_like 테이블 생성
    # ------------------------------------------------------------
    op.create_table(
        "posts_like",
        sa.Column(
            "like_id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "post_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="생성 시각 (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="수정 시각 (UTC)",
        ),
        sa.PrimaryKeyConstraint(
            "like_id",
            name=op.f("pk_posts_like"),
        ),
        sa.UniqueConstraint(
            "post_id",
            "user_id",
            name="uq_posts_like_post_id_user_id",
        ),
    )

    op.create_index(
        op.f("ix_posts_like_post_id"),
        "posts_like",
        ["post_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_posts_like_user_id"),
        "posts_like",
        ["user_id"],
        unique=False,
    )

    # ------------------------------------------------------------
    # comments 컬럼 rename
    # id -> comment_id
    # content -> comment_content
    # ------------------------------------------------------------
    op.alter_column(
        "comments",
        "id",
        new_column_name="comment_id",
        existing_type=sa.Integer(),
        existing_nullable=False,
        autoincrement=True,
    )

    op.alter_column(
        "comments",
        "content",
        new_column_name="comment_content",
        existing_type=sa.Text(),
        existing_nullable=False,
    )

    # comments.post_id -> posts.post_id FK
    op.create_foreign_key(
        op.f("fk_comments_post_id_posts"),
        "comments",
        "posts",
        ["post_id"],
        ["post_id"],
        ondelete="CASCADE",
    )

    # ------------------------------------------------------------
    # post_view_count 생성 시 사용했던 임시 DB 기본값 제거
    # ------------------------------------------------------------
    op.alter_column(
        "posts",
        "post_view_count",
        existing_type=sa.Integer(),
        server_default=None,
        existing_nullable=False,
    )

    # Post -> User FK를 사용하지 않는 현재 모델 구조에 맞춰 제거
    op.drop_constraint(
        op.f("fk_posts_author_id_users"),
        "posts",
        type_="foreignkey",
    )

    # ------------------------------------------------------------
    # users 컬럼 rename
    # 기존 데이터는 그대로 유지
    # ------------------------------------------------------------

    # email의 기존 UNIQUE 인덱스는 컬럼명 변경 전에 제거
    op.drop_index(
        op.f("uq_users_email"),
        table_name="users",
    )

    op.alter_column(
        "users",
        "email",
        new_column_name="user_email",
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )

    op.alter_column(
        "users",
        "password_hash",
        new_column_name="user_password_hash",
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )

    op.alter_column(
        "users",
        "nickname",
        new_column_name="user_nickname",
        existing_type=sa.String(length=50),
        existing_nullable=False,
    )

    op.alter_column(
        "users",
        "role",
        new_column_name="user_role",
        existing_type=sa.String(length=20),
        existing_nullable=False,
        existing_server_default="USER",
    )

    # 이름이 변경된 user_email에 UNIQUE 제약 다시 생성
    op.create_unique_constraint(
        op.f("uq_users_user_email"),
        "users",
        ["user_email"],
    )


def downgrade() -> None:
    """Downgrade schema."""

    # ------------------------------------------------------------
    # users 원래 이름으로 복구
    # ------------------------------------------------------------
    op.drop_constraint(
        op.f("uq_users_user_email"),
        "users",
        type_="unique",
    )

    op.alter_column(
        "users",
        "user_role",
        new_column_name="role",
        existing_type=sa.String(length=20),
        existing_nullable=False,
        existing_server_default="USER",
    )

    op.alter_column(
        "users",
        "user_nickname",
        new_column_name="nickname",
        existing_type=sa.String(length=50),
        existing_nullable=False,
    )

    op.alter_column(
        "users",
        "user_password_hash",
        new_column_name="password_hash",
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )

    op.alter_column(
        "users",
        "user_email",
        new_column_name="email",
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )

    op.create_index(
        op.f("uq_users_email"),
        "users",
        ["email"],
        unique=True,
    )

    # 기존 Post -> User FK 복원
    op.create_foreign_key(
        op.f("fk_posts_author_id_users"),
        "posts",
        "users",
        ["author_id"],
        ["user_id"],
    )

    # post_view_count의 기존 DB 기본값 복구
    op.alter_column(
        "posts",
        "post_view_count",
        existing_type=sa.Integer(),
        server_default=sa.text("'0'"),
        existing_nullable=False,
    )

    # ------------------------------------------------------------
    # comments 복구
    # ------------------------------------------------------------
    op.drop_constraint(
        op.f("fk_comments_post_id_posts"),
        "comments",
        type_="foreignkey",
    )

    op.alter_column(
        "comments",
        "comment_content",
        new_column_name="content",
        existing_type=sa.Text(),
        existing_nullable=False,
    )

    op.alter_column(
        "comments",
        "comment_id",
        new_column_name="id",
        existing_type=sa.Integer(),
        existing_nullable=False,
        autoincrement=True,
    )

    # ------------------------------------------------------------
    # posts_like 제거
    # ------------------------------------------------------------
    op.drop_index(
        op.f("ix_posts_like_user_id"),
        table_name="posts_like",
    )

    op.drop_index(
        op.f("ix_posts_like_post_id"),
        table_name="posts_like",
    )

    op.drop_table("posts_like")
