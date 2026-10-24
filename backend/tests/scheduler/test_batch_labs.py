"""Batch-pair lab behavior across candidate generation and both solvers."""
import pytest

from app.scheduler.candidate_generator import generate_unit_candidates
from app.scheduler.constraints.base import ScheduleAssignment
from app.scheduler.constraints.c01_teacher_conflict import TeacherConflictConstraint
from app.scheduler.constraints.c02_section_conflict import SectionConflictConstraint
from app.scheduler.constraints.c04_capacity import CapacityConstraint
from app.scheduler.csp_solver import CSPSolver, SolverConfig
from app.scheduler.domain import RoomInfo
from app.scheduler.session_expander import expand_sessions


def _courses(shared_teacher=False):
    second_faculty = [12, 11] if shared_teacher else [13, 14]
    return [
        {
            "id": 1, "course_code": "DP-LAB", "course_name": "Design Patterns Lab",
            "course_type": "lab", "weekly_sessions": 1, "duration": 2,
            "section_id": 5, "teacher_id": 11, "teacher_ids": [11, 12],
            "required_room_type": "lab", "section_strength": 60,
            "faculty_type": "regular", "batch_label": "B1/B2",
            "link_group": "SEM5-LAB-BLOCK-1",
        },
        {
            "id": 2, "course_code": "SE-LAB", "course_name": "Software Engineering Lab",
            "course_type": "lab", "weekly_sessions": 1, "duration": 2,
            "section_id": 5, "teacher_id": second_faculty[0], "teacher_ids": second_faculty,
            "required_room_type": "lab", "section_strength": 60,
            "faculty_type": "regular", "batch_label": "B3/B4",
            "link_group": "SEM5-LAB-BLOCK-1",
        },
    ]


def _rooms():
    return [
        RoomInfo(1, "LAB-101", "lab", 35),
        RoomInfo(2, "LAB-102", "lab", 35),
    ]


def _config():
    return SolverConfig(
        timeout_seconds=5,
        max_restarts=1,
        days=["Monday", "Tuesday"],
        slots_per_day=4,
        constraint_config={
            "reserved_slots": set(), "recess_slots": set(), "honours_slots": set(),
            "HONOURS_RESERVED_ENABLED": False, "teacher_unavailable": set(),
            "MAX_CONSECUTIVE_PERIODS": 2, "MAX_SECTION_DAILY_HOURS": 4,
            "MAX_LECTURE_PERIODS_PER_DAY": 4, "MAX_TEACHER_DAILY_HOURS": 7,
            "MAX_SECTION_START_SLOT": 3, "valid_room_ids": {1, 2},
            "PREFER_BALANCED_DAYS": False,
        },
    )


@pytest.mark.parametrize("algorithm", ["csp", "cp-sat"])
def test_two_lab_batch_pairs_run_together_in_distinct_labs(algorithm):
    courses = _courses()
    sessions = expand_sessions(courses)
    config = _config()
    if algorithm == "cp-sat":
        pytest.importorskip("ortools")
        from app.scheduler.cp_sat_solver import CPSATSolver
        result = CPSATSolver(config).solve(sessions, _rooms())
    else:
        result = CSPSolver(config).solve(sessions, _rooms())

    assert result.status == "VALID"
    assert result.sessions_scheduled == result.sessions_expected == 2
    assert len({assignment.room_id for assignment in result.assignments}) == 2
    assert len({(assignment.day, assignment.slot_index) for assignment in result.assignments}) == 1
    assert {assignment.batch_label for assignment in result.assignments} == {"B1/B2", "B3/B4"}
    assert all(assignment.required_capacity == 30 for assignment in result.assignments)
    assert not any(
        not TeacherConflictConstraint().check(assignment, result.assignments[:index], config.constraint_config).valid
        for index, assignment in enumerate(result.assignments)
    )


@pytest.mark.parametrize("algorithm", ["csp", "cp-sat"])
def test_independent_batch_pairs_can_concurrently_use_two_available_rooms(algorithm):
    courses = _courses()
    for course in courses:
        course["link_group"] = None
    sessions = expand_sessions(courses)
    config = _config()
    config.days = ["Monday"]
    config.slots_per_day = 2  # Each two-period lab has exactly one possible start.
    if algorithm == "cp-sat":
        pytest.importorskip("ortools")
        from app.scheduler.cp_sat_solver import CPSATSolver
        result = CPSATSolver(config).solve(sessions, _rooms())
    else:
        result = CSPSolver(config).solve(sessions, _rooms())

    assert result.status == "VALID"
    assert len({(assignment.day, assignment.slot_index) for assignment in result.assignments}) == 1
    assert len({assignment.room_id for assignment in result.assignments}) == 2


def test_linked_batch_labs_cannot_share_one_faculty_member():
    sessions = expand_sessions(_courses(shared_teacher=True))
    units = [sessions]
    assert generate_unit_candidates(
        units[0], _rooms(), ["Monday"], 4, set(), set(), set(), False, set()
    ) == []


def test_disjoint_batch_pairs_can_overlap_but_same_students_cannot():
    rule = SectionConflictConstraint()
    first = ScheduleAssignment("b12", 1, 5, 11, 1, "Monday", 1, course_type="lab", batch_label="B1/B2")
    second_pair = ScheduleAssignment("b34", 2, 5, 13, 2, "Monday", 1, course_type="lab", batch_label="B3/B4")
    overlapping_pair = ScheduleAssignment("b2", 3, 5, 15, 3, "Monday", 1, course_type="lab", batch_label="B1/B2")
    whole_section = ScheduleAssignment("all", 4, 5, 16, 4, "Monday", 1)

    assert rule.check(second_pair, [first], {}).valid
    assert not rule.check(overlapping_pair, [first], {}).valid
    assert not rule.check(whole_section, [first], {}).valid


def test_batch_pair_room_capacity_is_half_the_section_strength():
    rule = CapacityConstraint()
    pair_lab = ScheduleAssignment(
        "lab", 1, 5, 11, 1, "Monday", 1, room_capacity=30,
        section_strength=60, course_type="lab", batch_label="B1/B2",
    )
    assert rule.check(pair_lab, [], {}).valid
    pair_lab.room_capacity = 29
    assert not rule.check(pair_lab, [], {}).valid
