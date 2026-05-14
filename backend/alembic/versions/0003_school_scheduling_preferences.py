"""scheduling_preferences JSON on schools

Revision ID: 0003_school_prefs
Revises: 0002_class_subject_hours
Create Date: 2026-04-30
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_school_prefs"
down_revision = "0002_class_subject_hours"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "schools",
        sa.Column("scheduling_preferences", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("schools", "scheduling_preferences")
