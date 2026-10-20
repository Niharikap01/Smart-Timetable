"""Persist program-elective groups and link their timetable course rows.

Revision ID: 004
Revises: 003
"""
from alembic import op
import sqlalchemy as sa


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "program_electives",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("semester", sa.Integer(), nullable=False),
        sa.Column("course_code", sa.String(length=50), nullable=False),
        sa.Column("course_name", sa.String(length=200), nullable=False),
        sa.Column("weekly_sessions", sa.Integer(), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_program_electives_semester", "program_electives", ["semester"])

    op.create_table(
        "program_elective_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("program_elective_id", sa.Integer(), sa.ForeignKey("program_electives.id"), nullable=False),
        sa.Column("group_name", sa.String(length=100), nullable=False),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("teachers.id"), nullable=False),
        sa.Column("student_count", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_program_elective_groups_program_elective_id", "program_elective_groups", ["program_elective_id"])
    op.create_index("ix_program_elective_groups_teacher_id", "program_elective_groups", ["teacher_id"])

    op.create_table(
        "program_elective_group_sections",
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("program_elective_groups.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("section_id", sa.Integer(), sa.ForeignKey("sections.id", ondelete="CASCADE"), primary_key=True),
    )

    with op.batch_alter_table("courses") as batch_op:
        batch_op.add_column(sa.Column("program_elective_group_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_courses_program_elective_group",
            "program_elective_groups",
            ["program_elective_group_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_courses_program_elective_group_id", ["program_elective_group_id"])


def downgrade() -> None:
    with op.batch_alter_table("courses") as batch_op:
        batch_op.drop_index("ix_courses_program_elective_group_id")
        batch_op.drop_constraint("fk_courses_program_elective_group", type_="foreignkey")
        batch_op.drop_column("program_elective_group_id")
    op.drop_table("program_elective_group_sections")
    op.drop_index("ix_program_elective_groups_teacher_id", table_name="program_elective_groups")
    op.drop_index("ix_program_elective_groups_program_elective_id", table_name="program_elective_groups")
    op.drop_table("program_elective_groups")
    op.drop_index("ix_program_electives_semester", table_name="program_electives")
    op.drop_table("program_electives")
