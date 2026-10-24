"""Regression tests for the Google OR-Tools CP-SAT solver."""
import pytest

pytest.importorskip("ortools")

from app.scheduler.cp_sat_solver import CPSATSolver
from app.scheduler.csp_solver import SolverConfig
from app.scheduler.domain import RoomInfo
from app.scheduler.session_expander import expand_sessions


def _config():
    return SolverConfig(
        timeout_seconds=10,
        days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        slots_per_day=8,
        constraint_config={
            "reserved_slots": set(),
            "recess_slots": set(),
            "allowed_break_slots": set(),
            "honours_slots": set(),
            "HONOURS_RESERVED_ENABLED": False,
            "teacher_unavailable": set(),
            "MAX_CONSECUTIVE_PERIODS": 3,
            "MAX_SECTION_DAILY_HOURS": 6,
            "MAX_LECTURE_PERIODS_PER_DAY": 5,
            "MAX_TEACHER_DAILY_HOURS": 7,
            "MAX_SECTION_START_SLOT": 3,
            "expected_sessions_per_course": {1: 3, 2: 2, 3: 1},
            "valid_room_ids": {1, 2},
            "PREFER_BALANCED_DAYS": True,
        },
    )


def _courses():
    return [
        {"id": 1, "course_code": "CS301", "course_name": "DBMS", "course_type": "lecture",
         "weekly_sessions": 3, "duration": 1, "section_id": 1, "teacher_id": 1,
         "required_room_type": "lecture", "section_strength": 50, "faculty_type": "regular", "priority": 5},
        {"id": 2, "course_code": "CS302", "course_name": "OS", "course_type": "lecture",
         "weekly_sessions": 2, "duration": 1, "section_id": 1, "teacher_id": 2,
         "required_room_type": "lecture", "section_strength": 50, "faculty_type": "regular", "priority": 5},
        {"id": 3, "course_code": "CS303", "course_name": "Networks Lab", "course_type": "lab",
         "weekly_sessions": 1, "duration": 2, "section_id": 2, "teacher_id": 1,
         "required_room_type": "lab", "section_strength": 45, "faculty_type": "regular", "priority": 7},
    ]


def test_cp_sat_generates_and_validates_a_timetable():
    result = CPSATSolver(_config()).solve(
        expand_sessions(_courses()),
        [
            RoomInfo(room_id=1, room_number="CR-101", room_type="lecture", capacity=60),
            RoomInfo(room_id=2, room_number="LAB-101", room_type="lab", capacity=60),
        ],
    )

    assert result.status == "VALID"
    assert result.algorithm == "GOOGLE_OR_TOOLS_CP_SAT"
    assert result.sessions_scheduled == result.sessions_expected == 6
    assert result.hard_constraint_violations == 0


def test_cp_sat_respects_section_specific_recess():
    config = _config()
    config.constraint_config["recess_slots"] = {(1, "Monday", 0)}
    result = CPSATSolver(config).solve(
        expand_sessions(_courses()),
        [
            RoomInfo(room_id=1, room_number="CR-101", room_type="lecture", capacity=60),
            RoomInfo(room_id=2, room_number="LAB-101", room_type="lab", capacity=60),
        ],
    )

    assert result.status == "VALID"
    assert not any(
        assignment.section_id == 1 and assignment.day == "Monday" and assignment.slot_index == 0
        for assignment in result.assignments
    )


def test_cp_sat_balances_periods_across_the_week():
    """Balanced mode should avoid leaving one cohort with an overloaded day."""
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    courses = [
        {"id": index, "course_code": f"CS{index}", "course_name": f"Course {index}",
         "course_type": "lecture", "weekly_sessions": 1, "duration": 1,
         "section_id": 1, "teacher_id": index, "required_room_type": "lecture",
         "section_strength": 50, "faculty_type": "regular", "priority": 5}
        for index in range(1, 13)
    ]
    config = _config()
    config.days = days
    config.constraint_config["expected_sessions_per_course"] = {index: 1 for index in range(1, 13)}
    result = CPSATSolver(config).solve(
        expand_sessions(courses),
        [RoomInfo(room_id=1, room_number="CR-101", room_type="lecture", capacity=60)],
    )

    assert result.status == "VALID"
    daily_load = {day: sum(assignment.day == day for assignment in result.assignments) for day in days}
    assert daily_load == {day: 2 for day in days}
