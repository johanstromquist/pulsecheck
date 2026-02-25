"""add ssl_certificates table and ssl_expiry condition type

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-25 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create ssl_certificates table and add ssl_expiry to condition_type enum."""
    op.create_table(
        "ssl_certificates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "service_id",
            sa.Uuid(),
            sa.ForeignKey("services.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("issuer", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("serial_number", sa.String(255), nullable=False),
        sa.Column("not_before", sa.DateTime(timezone=True), nullable=False),
        sa.Column("not_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("days_until_expiry", sa.Integer(), nullable=False),
        sa.Column(
            "last_checked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Add ssl_expiry to condition_type enum (PostgreSQL)
    op.execute("ALTER TYPE condition_type ADD VALUE IF NOT EXISTS 'ssl_expiry'")


def downgrade() -> None:
    """Drop ssl_certificates table."""
    op.drop_table("ssl_certificates")
    # Note: PostgreSQL does not support removing enum values
