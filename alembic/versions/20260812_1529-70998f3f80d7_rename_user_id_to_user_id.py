"""rename user id to user_id

Revision ID: 70998f3f80d7
Revises: 6e316f4b3ead
Create Date: 2026-08-12 15:29:11.734993

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "70998f3f80d7"
down_revision: str | Sequence[str] | None = "6e316f4b3ead"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rename users.user_id to users.user_id."""
    op.alter_column(
        "users",
        "id",
        new_column_name="user_id",
        existing_type=sa.Integer(),
        existing_nullable=False,
        autoincrement=True,
    )


def downgrade() -> None:
    """Rename users.user_id back to users.user_id."""
    op.alter_column(
        "users",
        "user_id",
        new_column_name="id",
        existing_type=sa.Integer(),
        existing_nullable=False,
        autoincrement=True,
    )
