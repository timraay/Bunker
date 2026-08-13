"""Bifrost Integration

Revision ID: 043e9a98925f
Revises: 9da79cb1c027
Create Date: 2026-08-12 15:12:26.469000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "043e9a98925f"
down_revision: str | None = "9da79cb1c027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TYPE integrationtype
        ADD VALUE IF NOT EXISTS 'BIFROST' AFTER 'COMMUNITY_RCON';
    """)


def downgrade() -> None:
    pass
