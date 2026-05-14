"""class_subject_hours for curriculum plan

Revision ID: 0002_class_subject_hours
Revises: 0001_init
Create Date: 2026-04-30
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_class_subject_hours"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "class_subject_hours",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("student_classes.id"), nullable=False),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("hours_per_week", sa.Integer(), nullable=False),
        sa.UniqueConstraint("school_id", "class_id", "subject_id", name="uq_class_subject_hours"),
    )
    op.create_index("ix_class_subject_hours_school_id", "class_subject_hours", ["school_id"])
    op.create_index("ix_class_subject_hours_class_id", "class_subject_hours", ["class_id"])


def downgrade() -> None:
    op.drop_index("ix_class_subject_hours_class_id", table_name="class_subject_hours")
    op.drop_index("ix_class_subject_hours_school_id", table_name="class_subject_hours")
    op.drop_table("class_subject_hours")
