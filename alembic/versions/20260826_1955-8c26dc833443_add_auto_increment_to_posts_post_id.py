"""add auto increment to posts post id

Revision ID: 8c26dc833443
Revises: e8547669b5ed
Create Date: 2026-08-26 19:55:40.100241

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c26dc833443"
down_revision: str | Sequence[str] | None = "e8547669b5ed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """posts.post_id에 자동 증가를 설정한다."""
    op.drop_constraint(
        "fk_comments_post_id_posts",
        "comments",
        type_="foreignkey",
    )

    op.alter_column(
        "posts",
        "post_id",
        existing_type=sa.Integer(),
        existing_nullable=False,
        autoincrement=True,
    )

    op.create_foreign_key(
        "fk_comments_post_id_posts",
        "comments",
        "posts",
        ["post_id"],
        ["post_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """posts.post_id의 자동 증가를 해제한다."""
    op.drop_constraint(
        "fk_comments_post_id_posts",
        "comments",
        type_="foreignkey",
    )

    op.alter_column(
        "posts",
        "post_id",
        existing_type=sa.Integer(),
        existing_nullable=False,
        autoincrement=False,
    )

    op.create_foreign_key(
        "fk_comments_post_id_posts",
        "comments",
        "posts",
        ["post_id"],
        ["post_id"],
        ondelete="CASCADE",
    )
