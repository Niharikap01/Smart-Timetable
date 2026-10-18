"""Persist coordinator editable constraint profiles and schedule snapshots.

Revision ID: 003
Revises: 002
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("is_coordinator", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.create_table(
        "constraint_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, unique=True),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("change_reason", sa.String(length=500), nullable=False),
        sa.Column("changed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_constraint_profiles_version", "constraint_profiles", ["version"], unique=True)

    with op.batch_alter_table("generated_schedules") as batch_op:
        batch_op.add_column(sa.Column("constraint_profile_version", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("constraint_config_snapshot", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("generated_schedules") as batch_op:
        batch_op.drop_column("constraint_config_snapshot")
        batch_op.drop_column("constraint_profile_version")
    op.drop_index("ix_constraint_profiles_version", table_name="constraint_profiles")
    op.drop_table("constraint_profiles")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("is_coordinator")
