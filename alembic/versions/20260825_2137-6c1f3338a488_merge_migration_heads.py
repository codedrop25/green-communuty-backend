"""merge migration heads

Revision ID: 6c1f3338a488
Revises: b686b1a38ef2, d439f5babf47
Create Date: 2026-08-25 21:37:21.478737

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "6c1f3338a488"
down_revision: str | Sequence[str] | None = ("b686b1a38ef2", "d439f5babf47")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
