"""Tests for the CSP solver: small dataset, impossible dataset, timeout, bitmask, MRV."""
import pytest
from app.scheduler.csp_solver import CSPSolver, SolverConfig
from app.scheduler.session_expander import expand_sessions
from app.scheduler.domain import SchedulingSession, RoomInfo
from app.scheduler.bitmask import OccupancyTracker


def _small_config():
    return SolverConfig(
        timeout_seconds=10,
        max_restarts=2,
        debug=False,
        days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        slots_per_day=8,
        constraint_config={
            "reserved_slots": set(),
            "recess_slots": set(),
            "honours_slots": set(),
            "HONOURS_RESERVED_ENABLED": False,
            "teacher_unavailable": set(),
            "MAX_CONSECUTIVE_PERIODS": 3,
            "MAX_SECTION_DAILY_HOURS": 6,
            "MAX_LECTURE_PERIODS_PER_DAY": 5,
            "MAX_TEACHER_DAILY_HOURS": 7,
        },
    )


def _small_courses():
    return [
        {"id": 1, "course_code": "CS301", "course_name": "DB", "course_type": "lecture",
         "weekly_sessions": 3, "duration": 1, "section_id": 1, "teacher_id": 1,
         "required_room_type": "lecture", "section_strength": 50, "faculty_type": "regular", "priority": 5},
        {"id": 2, "course_code": "CS302", "course_name": "OS", "course_type": "lecture",
         "weekly_sessions": 3, "duration": 1, "section_id": 1, "teacher_id": 2,
         "required_room_type": "lecture", "section_strength": 50, "faculty_type": "regular", "priority": 5},
        {"id": 3, "course_code": "CS303", "course_name": "DS Lab", "course_type": "lab",
         "weekly_sessions": 1, "duration": 2, "section_id": 1, "teacher_id": 1,
         "required_room_type": "lab", "section_strength": 50, "faculty_type": "regular", "priority": 7},
        {"id": 4, "course_code": "CS304", "course_name": "Math", "course_type": "lecture",
         "weekly_sessions": 2, "duration": 1, "section_id": 2, "teacher_id": 3,
         "required_room_type": "lecture", "section_strength": 45, "faculty_type": "regular", "priority": 5},
        {"id": 5, "course_code": "CS305", "course_name": "English", "course_type": "lecture",
         "weekly_sessions": 2, "duration": 1, "section_id": 2, "teacher_id": 4,
         "required_room_type": "lecture", "section_strength": 45, "faculty_type": "regular", "priority": 5},
    ]


def _small_rooms():
    return [
        RoomInfo(room_id=1, room_number="CR-01", room_type="lecture", capacity=60),
        RoomInfo(room_id=2, room_number="CR-02", room_type="lecture", capacity=60),
        RoomInfo(room_id=3, room_number="LAB-01", room_type="lab", capacity=60),
    ]


def test_csp_generates_valid_schedule():
    courses = _small_courses()
    sessions = expand_sessions(courses)
    rooms = _small_rooms()
    config = _small_config()
    solver = CSPSolver(config)
    result = solver.solve(sessions, rooms)
    assert result.status == "VALID"
    assert result.sessions_scheduled == result.sessions_expected
    assert result.hard_constraint_violations == 0


def test_session_expansion():
    courses = _small_courses()
    sessions = expand_sessions(courses)
    # 3 + 3 + 1 + 2 + 2 = 11
    assert len(sessions) == 11
    lab_sessions = [s for s in sessions if s.course_type == "lab"]
    assert len(lab_sessions) == 1
    assert lab_sessions[0].duration == 2


def test_impossible_dataset():
    """More sessions than can fit in 1 day with 1 room."""
    courses = [
        {"id": i, "course_code": f"CS{i}", "course_name": f"C{i}", "course_type": "lecture",
         "weekly_sessions": 1, "duration": 1, "section_id": 1, "teacher_id": i,
         "required_room_type": "lecture", "section_strength": 50, "faculty_type": "regular", "priority": 5}
        for i in range(1, 50)  # 49 sessions, but section daily limit is 6
    ]
    rooms = [RoomInfo(room_id=1, room_number="CR-01", room_type="lecture", capacity=60)]
    sessions = expand_sessions(courses)
    config = _small_config()
    config.timeout_seconds = 5
    solver = CSPSolver(config)
    result = solver.solve(sessions, rooms)
    assert result.status in ("FAILED", "TIMEOUT")
    assert result.sessions_scheduled < result.sessions_expected


def test_timeout():
    courses = [
        {"id": i, "course_code": f"CS{i}", "course_name": f"C{i}", "course_type": "lecture",
         "weekly_sessions": 5, "duration": 1, "section_id": 1, "teacher_id": i,
         "required_room_type": "lecture", "section_strength": 50, "faculty_type": "regular", "priority": 5}
        for i in range(1, 20)
    ]
    rooms = [RoomInfo(room_id=1, room_number="CR-01", room_type="lecture", capacity=60)]
    sessions = expand_sessions(courses)
    config = _small_config()
    config.timeout_seconds = 2
    solver = CSPSolver(config)
    result = solver.solve(sessions, rooms)
    assert result.status in ("FAILED", "TIMEOUT")


def test_bitmask_conflict():
    ot = OccupancyTracker()
    ot.assign(teacher_id=1, section_id=1, room_id=1, day="Monday", slot_index=0, duration=1)
    assert ot.has_teacher_conflict(1, "Monday", 0, 1)
    assert not ot.has_teacher_conflict(1, "Monday", 1, 1)
    assert ot.has_room_conflict(1, "Monday", 0, 1)
    assert ot.has_any_conflict(1, 1, 1, "Monday", 0, 1)
    assert not ot.has_any_conflict(2, 2, 2, "Monday", 0, 1)


def test_bitmask_unassign():
    ot = OccupancyTracker()
    ot.assign(1, 1, 1, "Monday", 0, 1)
    assert ot.has_teacher_conflict(1, "Monday", 0, 1)
    ot.unassign(1, 1, 1, "Monday", 0, 1)
    assert not ot.has_teacher_conflict(1, "Monday", 0, 1)


def test_bitmask_multi_period():
    ot = OccupancyTracker()
    ot.assign(1, 1, 1, "Monday", 2, 2)  # slots 2 and 3
    assert ot.has_teacher_conflict(1, "Monday", 2, 1)
    assert ot.has_teacher_conflict(1, "Monday", 3, 1)
    assert not ot.has_teacher_conflict(1, "Monday", 1, 1)
    assert not ot.has_teacher_conflict(1, "Monday", 4, 1)


def test_mrv_selects_most_constrained():
    from app.scheduler.heuristics import select_next_session
    s1 = SchedulingSession("s1", 1, 1, 1, 1, "lecture", "lecture", 50, "regular")
    s2 = SchedulingSession("s2", 2, 1, 2, 1, "lecture", "lecture", 50, "regular")
    domains = {"s1": [None] * 5, "s2": [None] * 2}
    result = select_next_session([s1, s2], domains)
    assert result.session_id == "s2"


def test_multi_period_lab_contiguous():
    """Verify lab sessions with duration=2 get contiguous slots."""
    courses = [
        {"id": 1, "course_code": "LAB1", "course_name": "Lab", "course_type": "lab",
         "weekly_sessions": 1, "duration": 2, "section_id": 1, "teacher_id": 1,
         "required_room_type": "lab", "section_strength": 50, "faculty_type": "regular", "priority": 7},
    ]
    rooms = [RoomInfo(room_id=1, room_number="LAB-01", room_type="lab", capacity=60)]
    sessions = expand_sessions(courses)
    config = _small_config()
    solver = CSPSolver(config)
    result = solver.solve(sessions, rooms)
    assert result.status == "VALID"
    assert result.assignments[0].duration == 2


def test_teacher_daily_hours_respected():
    """All sessions for one teacher shouldn't exceed daily limit."""
    courses = _small_courses()
    sessions = expand_sessions(courses)
    rooms = _small_rooms()
    config = _small_config()
    solver = CSPSolver(config)
    result = solver.solve(sessions, rooms)
    assert result.status == "VALID"
    from collections import defaultdict
    by_teacher_day = defaultdict(int)
    for a in result.assignments:
        by_teacher_day[(a.teacher_id, a.day)] += a.duration
    for (tid, day), hours in by_teacher_day.items():
        assert hours <= 7, f"Teacher {tid} has {hours} hours on {day}"


def test_balanced_mode_spreads_a_section_across_the_week():
    """Balanced mode must not leave working days empty when load permits."""
    courses = [
        {"id": index, "course_code": f"CS{index}", "course_name": f"Course {index}",
         "course_type": "lecture", "weekly_sessions": 1, "duration": 1,
         "section_id": 1, "teacher_id": index, "required_room_type": "lecture",
         "section_strength": 50, "faculty_type": "regular", "priority": 5}
        for index in range(1, 6)
    ]
    config = _small_config()
    config.constraint_config["PREFER_BALANCED_DAYS"] = True
    solver = CSPSolver(config)
    result = solver.solve(expand_sessions(courses), [
        RoomInfo(room_id=1, room_number="CR-01", room_type="lecture", capacity=60),
    ])

    assert result.status == "VALID"
    assert {assignment.day for assignment in result.assignments} == {
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
    }
