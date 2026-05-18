"""product core: plan, events, snapshots, usage counters

Revision ID: 0004_product_core
Revises: 0003_school_prefs
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_product_core"
down_revision = "0003_school_prefs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("schools", sa.Column("plan", sa.String(20), nullable=False, server_default="free"))
    op.add_column("schools", sa.Column("trial_ends_at", sa.DateTime(), nullable=True))
    op.add_column("schools", sa.Column("subscription_ends_at", sa.DateTime(), nullable=True))
    op.add_column(
        "schools",
        sa.Column("schedule_publish_state", sa.String(20), nullable=False, server_default="draft"),
    )
    op.add_column("schools", sa.Column("published_at", sa.DateTime(), nullable=True))

    op.create_table(
        "school_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "schedule_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False, index=True),
        sa.Column("label", sa.String(255), nullable=False, server_default=""),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("items_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "usage_counters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False, index=True),
        sa.Column("metric", sa.String(64), nullable=False),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("school_id", "metric", "period", name="uq_usage_counter"),
    )


def downgrade() -> None:
    op.drop_table("usage_counters")
    op.drop_table("schedule_snapshots")
    op.drop_table("school_events")
    op.drop_column("schools", "published_at")
    op.drop_column("schools", "schedule_publish_state")
    op.drop_column("schools", "subscription_ends_at")
    op.drop_column("schools", "trial_ends_at")
    op.drop_column("schools", "plan")
