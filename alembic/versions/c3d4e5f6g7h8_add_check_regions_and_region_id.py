"""add check_regions table and region_id to health_checks

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-25
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c3d4e5f6g7h8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "check_regions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("endpoint_url", sa.String(length=2048), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.add_column(
        "health_checks",
        sa.Column("region_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_health_checks_region_id",
        "health_checks",
        "check_regions",
        ["region_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_health_checks_region_id",
        "health_checks",
        ["region_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_health_checks_region_id", table_name="health_checks")
    op.drop_constraint("fk_health_checks_region_id", "health_checks", type_="foreignkey")
    op.drop_column("health_checks", "region_id")
    op.drop_table("check_regions")
