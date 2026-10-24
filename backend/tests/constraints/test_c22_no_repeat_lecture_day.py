import pytest

from app.scheduler.constraints.base import ScheduleAssignment
from app.scheduler.constraints.c22_no_repeat_lecture_day import NoRepeatLecturePerDayConstraint


def _assignment(session_id, *, course_type="lecture", day="Monday"):
    return ScheduleAssignment(
        session_id=session_id,
        course_id=12,
        section_id=4,
        teacher_id=8,
        room_id=3,
        day=day,
        slot_index=1,
        course_type=course_type,
    )


def test_same_lecture_course_cannot_repeat_in_a_section_on_one_day():
    rule = NoRepeatLecturePerDayConstraint()
    first = _assignment("lecture-1")
    same_day = _assignment("lecture-2")
    next_day = _assignment("lecture-3", day="Tuesday")

    assert not rule.check(same_day, [first], {}).valid
    assert rule.check(next_day, [first], {}).valid


def test_rule_does_not_apply_to_laboratory_sessions():
    rule = NoRepeatLecturePerDayConstraint()
    first = _assignment("lab-1", course_type="lab")
    second = _assignment("lab-2", course_type="lab")

    assert rule.check(second, [first], {}).valid


def test_full_validation_reports_repeated_lecture_course_day():
    rule = NoRepeatLecturePerDayConstraint()
    violations = rule.validate_full(
        [_assignment("lecture-1"), _assignment("lecture-2")],
        {},
    )

    assert len(violations) == 1
    assert violations[0].constraint == "C22"


def test_cp_sat_rejects_two_weekly_lectures_when_only_one_day_is_available():
    pytest.importorskip("ortools")

    from app.scheduler.cp_sat_solver import CPSATSolver
    from app.scheduler.csp_solver import SolverConfig
    from app.scheduler.domain import RoomInfo
    from app.scheduler.session_expander import expand_sessions

    config = SolverConfig(
        timeout_seconds=5,
        days=["Monday"],
        slots_per_day=4,
        constraint_config={
            "reserved_slots": set(),
            "recess_slots": set(),
            "allowed_break_slots": set(),
            "honours_slots": set(),
            "HONOURS_RESERVED_ENABLED": False,
            "teacher_unavailable": set(),
            "MAX_CONSECUTIVE_PERIODS": 3,
            "MAX_SECTION_DAILY_HOURS": 4,
            "MAX_LECTURE_PERIODS_PER_DAY": 4,
            "MAX_TEACHER_DAILY_HOURS": 4,
            "MAX_SECTION_START_SLOT": 3,
            "expected_sessions_per_course": {12: 2},
            "valid_room_ids": {3},
        },
    )
    sessions = expand_sessions([{
        "id": 12,
        "course_code": "CS301",
        "course_name": "Database Systems",
        "course_type": "lecture",
        "weekly_sessions": 2,
        "duration": 1,
        "section_id": 4,
        "teacher_id": 8,
        "required_room_type": "lecture",
        "section_strength": 40,
        "faculty_type": "regular",
    }])
    rooms = [RoomInfo(room_id=3, room_number="CR-301", room_type="lecture", capacity=60)]

    result = CPSATSolver(config).solve(sessions, rooms)

    assert result.status == "FAILED"
