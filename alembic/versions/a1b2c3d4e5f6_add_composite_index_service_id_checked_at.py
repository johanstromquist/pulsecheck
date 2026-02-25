"""add composite index on health_checks(service_id, checked_at)

Revision ID: a1b2c3d4e5f6
Revises: 8e429901f835
Create Date: 2026-02-25 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '8e429901f835'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add composite index for metrics query performance."""
    op.create_index(
        "ix_health_checks_service_id_checked_at",
        "health_checks",
        ["service_id", "checked_at"],
    )


def downgrade() -> None:
    """Remove composite index."""
    op.drop_index("ix_health_checks_service_id_checked_at", table_name="health_checks")
