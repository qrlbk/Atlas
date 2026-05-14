"""init schema

Revision ID: 0001_init
Revises:
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


user_role = postgresql.ENUM(
    "admin",
    "school_manager",
    "viewer",
    name="userrole",
    create_type=False,
)
classroom_specialization = postgresql.ENUM(
    "standard",
    "chemistry_lab",
    "physics_lab",
    "gym",
    "language_room",
    name="classroomspecialization",
    create_type=False,
)


def upgrade() -> None:
    user_role.create(op.get_bind(), checkfirst=True)
    classroom_specialization.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "schools",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=True),
    )

    op.create_table(
        "teachers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("subjects", sa.JSON(), nullable=False),
        sa.Column("weekly_load_limit", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unavailable_days", sa.JSON(), nullable=False),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
    )
    op.create_index("ix_teachers_school_id", "teachers", ["school_id"])

    op.create_table(
        "classrooms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("room_number", sa.String(length=50), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("specialization", classroom_specialization, nullable=False),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
    )
    op.create_index("ix_classrooms_school_id", "classrooms", ["school_id"])

    op.create_table(
        "student_classes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("class_name", sa.String(length=50), nullable=False),
        sa.Column("students_count", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
    )
    op.create_index("ix_student_classes_school_id", "student_classes", ["school_id"])

    op.create_table(
        "subjects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("requires_special_room", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("required_specialization", classroom_specialization, nullable=True),
    )

    op.create_table(
        "lesson_slots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("lesson_number", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.UniqueConstraint("day_of_week", "lesson_number", name="uq_slot_day_lesson"),
    )

    op.create_table(
        "group_flows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_name", sa.String(length=100), nullable=False),
        sa.Column("combined_classes", sa.JSON(), nullable=False),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
    )
    op.create_index("ix_group_flows_school_id", "group_flows", ["school_id"])

    op.create_table(
        "schedule_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("student_classes.id"), nullable=False),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("teachers.id"), nullable=False),
        sa.Column("classroom_id", sa.Integer(), sa.ForeignKey("classrooms.id"), nullable=False),
        sa.Column("lesson_slot_id", sa.Integer(), sa.ForeignKey("lesson_slots.id"), nullable=False),
        sa.Column("is_grouped", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("group_flows.id"), nullable=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
    )
    op.create_index("ix_schedule_school_slot", "schedule_items", ["school_id", "lesson_slot_id"])
    op.create_index("ix_schedule_teacher_slot", "schedule_items", ["teacher_id", "lesson_slot_id"])
    op.create_index("ix_schedule_classroom_slot", "schedule_items", ["classroom_id", "lesson_slot_id"])


def downgrade() -> None:
    op.drop_index("ix_schedule_classroom_slot", table_name="schedule_items")
    op.drop_index("ix_schedule_teacher_slot", table_name="schedule_items")
    op.drop_index("ix_schedule_school_slot", table_name="schedule_items")
    op.drop_table("schedule_items")
    op.drop_index("ix_group_flows_school_id", table_name="group_flows")
    op.drop_table("group_flows")
    op.drop_table("lesson_slots")
    op.drop_table("subjects")
    op.drop_index("ix_student_classes_school_id", table_name="student_classes")
    op.drop_table("student_classes")
    op.drop_index("ix_classrooms_school_id", table_name="classrooms")
    op.drop_table("classrooms")
    op.drop_index("ix_teachers_school_id", table_name="teachers")
    op.drop_table("teachers")
    op.drop_table("users")
    op.drop_table("schools")
    classroom_specialization.drop(op.get_bind(), checkfirst=True)
    user_role.drop(op.get_bind(), checkfirst=True)
