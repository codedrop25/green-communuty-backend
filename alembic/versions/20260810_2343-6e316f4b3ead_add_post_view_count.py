"""add post view count

Revision ID: 6e316f4b3ead
Revises: 3eb81cd3f427
Create Date: 2026-08-10 23:43:03.595766
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6e316f4b3ead"
down_revision: str | Sequence[str] | None = "3eb81cd3f427"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    op.drop_constraint(
        op.f("fk_comments_post_id_posts"),
        "comments",
        type_="foreignkey",
    )

    op.alter_column(
        "posts",
        "id",
        new_column_name="post_id",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )

    op.alter_column(
        "posts",
        "title",
        new_column_name="post_title",
        existing_type=sa.String(length=200),
        existing_nullable=False,
    )

    op.alter_column(
        "posts",
        "content",
        new_column_name="post_content",
        existing_type=sa.Text(),
        existing_nullable=False,
    )

    op.add_column(
        "posts",
        sa.Column(
            "post_view_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column("posts", "post_view_count")

    op.alter_column(
        "posts",
        "post_content",
        new_column_name="content",
        existing_type=sa.Text(),
        existing_nullable=False,
    )

    op.alter_column(
        "posts",
        "post_title",
        new_column_name="title",
        existing_type=sa.String(length=200),
        existing_nullable=False,
    )

    op.alter_column(
        "posts",
        "post_id",
        new_column_name="id",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
