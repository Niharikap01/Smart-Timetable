"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2026-08-19
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
    )
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "teachers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("employee_id", sa.String(50), nullable=False, unique=True),
        sa.Column("email", sa.String(200), nullable=False, unique=True),
        sa.Column("max_daily_hours", sa.Integer(), nullable=False, server_default="7"),
        sa.Column(
            "faculty_type",
            sa.Enum("regular", "visiting", "senior", "contract", name="facultytype"),
            nullable=False,
            server_default="regular",
        ),
        sa.Column("preferences", sa.String(1000), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
    )
    op.create_index("ix_teachers_employee_id", "teachers", ["employee_id"])

    op.create_table(
        "sections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("semester", sa.Integer(), nullable=False),
        sa.Column("strength", sa.Integer(), nullable=False),
        sa.Column("program", sa.String(100), nullable=False, server_default="CSE"),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
    )

    op.create_table(
        "rooms",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("room_number", sa.String(50), nullable=False, unique=True),
        sa.Column(
            "room_type",
            sa.Enum("lecture", "lab", name="roomtype"),
            nullable=False,
        ),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("building", sa.String(100), nullable=True),
        sa.Column("floor", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
    )
    op.create_index("ix_rooms_room_number", "rooms", ["room_number"])

    op.create_table(
        "timeslots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "day",
            sa.Enum(
                "Monday", "Tuesday", "Wednesday", "Thursday",
                "Friday", "Saturday", name="dayofweek",
            ),
            nullable=False,
        ),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("slot_index", sa.Integer(), nullable=False),
        sa.Column("is_reserved", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("reservation_reason", sa.String(200), nullable=True),
    )

    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("course_code", sa.String(50), nullable=False),
        sa.Column("course_name", sa.String(200), nullable=False),
        sa.Column(
            "course_type",
            sa.Enum("lecture", "lab", "tutorial", name="coursetype"),
            nullable=False,
        ),
        sa.Column("weekly_sessions", sa.Integer(), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("section_id", sa.Integer(), sa.ForeignKey("sections.id"), nullable=False),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("teachers.id"), nullable=False),
        sa.Column(
            "required_room_type",
            sa.Enum("lecture", "lab", name="roomtype"),
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
    )
    op.create_index("ix_courses_course_code", "courses", ["course_code"])

    op.create_table(
        "teacher_availability",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("teachers.id"), nullable=False),
        sa.Column(
            "day",
            sa.Enum(
                "Monday", "Tuesday", "Wednesday", "Thursday",
                "Friday", "Saturday", name="dayofweek",
            ),
            nullable=False,
        ),
        sa.Column("slot_index", sa.Integer(), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default="1"),
    )

    op.create_table(
        "reserved_slots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "day",
            sa.Enum(
                "Monday", "Tuesday", "Wednesday", "Thursday",
                "Friday", "Saturday", name="dayofweek",
            ),
            nullable=False,
        ),
        sa.Column("slot_index", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False),
    )

    op.create_table(
        "generated_schedules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("VALID", "FAILED", "IN_PROGRESS", name="schedulestatus"),
            nullable=False,
        ),
        sa.Column("hard_constraint_violations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("soft_constraint_score", sa.Float(), nullable=True),
        sa.Column("generation_time_ms", sa.Integer(), nullable=True),
        sa.Column("algorithm", sa.String(100), nullable=False, server_default="CSP_BACKTRACKING"),
        sa.Column("version", sa.String(50), nullable=True),
        sa.Column("backtracks", sa.Integer(), nullable=True),
        sa.Column("restarts", sa.Integer(), nullable=True),
    )

    op.create_table(
        "timetable_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("section_id", sa.Integer(), sa.ForeignKey("sections.id"), nullable=False),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("teachers.id"), nullable=False),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("rooms.id"), nullable=False),
        sa.Column("timeslot_id", sa.Integer(), sa.ForeignKey("timeslots.id"), nullable=False),
        sa.Column(
            "day",
            sa.Enum(
                "Monday", "Tuesday", "Wednesday", "Thursday",
                "Friday", "Saturday", name="dayofweek",
            ),
            nullable=False,
        ),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("session_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "generated_schedule_id",
            sa.Integer(),
            sa.ForeignKey("generated_schedules.id"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("timetable_sessions")
    op.drop_table("generated_schedules")
    op.drop_table("reserved_slots")
    op.drop_table("teacher_availability")
    op.drop_table("courses")
    op.drop_table("timeslots")
    op.drop_table("rooms")
    op.drop_table("sections")
    op.drop_table("teachers")
    op.drop_table("users")
