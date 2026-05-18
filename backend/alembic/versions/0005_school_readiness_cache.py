"""school readiness cache columns

Revision ID: 0005_readiness_cache
Revises: 0004_product_core
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_readiness_cache"
down_revision = "0004_product_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "schools",
        sa.Column("readiness_status", sa.String(16), nullable=False, server_default="unknown"),
    )
    op.add_column("schools", sa.Column("readiness_checked_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("schools", "readiness_checked_at")
    op.drop_column("schools", "readiness_status")
