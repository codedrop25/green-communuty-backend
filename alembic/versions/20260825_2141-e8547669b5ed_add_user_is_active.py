"""rename is_active to user_is_active"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8547669b5ed"
down_revision: str | Sequence[str] | None = "6c1f3338a488"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "is_active",
        new_column_name="user_is_active",
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "user_is_active",
        new_column_name="is_active",
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )
