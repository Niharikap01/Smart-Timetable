"""Tests for Phase 14: linked groups (electives / parallel lab pairs)."""
from app.scheduler.csp_solver import CSPSolver, SolverConfig
from app.scheduler.session_expander import expand_sessions, group_sessions
from app.scheduler.domain import RoomInfo


def _config():
    return SolverConfig(
        timeout_seconds=10,
        max_restarts=2,
        days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        slots_per_day=8,
        constraint_config={
            "reserved_slots": set(), "recess_slots": set(), "honours_slots": set(),
            "HONOURS_RESERVED_ENABLED": False, "teacher_unavailable": set(),
            "MAX_CONSECUTIVE_PERIODS": 3, "MAX_SECTION_DAILY_HOURS": 6,
            "MAX_LECTURE_PERIODS_PER_DAY": 5, "MAX_TEACHER_DAILY_HOURS": 7,
        },
    )


def _elective_courses():
    """DPD / ECOM / IDPS: one section, 3 different electives, same slot."""
    return [
        {"id": 1, "course_code": "DPD", "course_name": "DPD", "course_type": "lecture",
         "weekly_sessions": 2, "duration": 1, "section_id": 1, "teacher_id": 1,
         "required_room_type": "lecture", "section_strength": 20, "faculty_type": "regular",
         "priority": 5, "link_group": "ELEC1"},
        {"id": 2, "course_code": "ECOM", "course_name": "ECOM", "course_type": "lecture",
         "weekly_sessions": 2, "duration": 1, "section_id": 1, "teacher_id": 2,
         "required_room_type": "lecture", "section_strength": 20, "faculty_type": "regular",
         "priority": 5, "link_group": "ELEC1"},
        {"id": 3, "course_code": "IDPS", "course_name": "IDPS", "course_type": "lecture",
         "weekly_sessions": 2, "duration": 1, "section_id": 1, "teacher_id": 3,
         "required_room_type": "lecture", "section_strength": 15, "faculty_type": "regular",
         "priority": 5, "link_group": "ELEC1"},
    ]


def _rooms():
    return [
        RoomInfo(room_id=1, room_number="DT-103", room_type="lecture", capacity=25),
        RoomInfo(room_id=2, room_number="DT-112", room_type="lecture", capacity=25),
        RoomInfo(room_id=3, room_number="DT-203", room_type="lecture", capacity=25),
    ]


def test_grouping_collects_same_link_group():
    sessions = expand_sessions(_elective_courses())
    units = group_sessions(sessions)
    # 3 courses x 2 weekly sessions = 6 sessions, grouped into 2 units of 3
    assert len(sessions) == 6
    assert len(units) == 2
    for u in units:
        assert len(u) == 3
        assert len({m.link_group_id for m in u}) == 1


def test_expand_keeps_link_group_when_course_data_is_a_dict():
    sessions = expand_sessions([_elective_courses()[0]])
    assert sessions[0].link_group_id == "1:ELEC1:1"


def test_solver_places_elective_group_on_same_slot():
    sessions = expand_sessions(_elective_courses())
    solver = CSPSolver(_config())
    result = solver.solve(sessions, _rooms())
    assert result.status == "VALID"
    assert result.sessions_scheduled == 6

    # Every member of a link_group must share day+slot_index.
    by_group = {}
    for a in result.assignments:
        by_group.setdefault(a.link_group_id, []).append(a)
    for gid, members in by_group.items():
        assert gid is not None
        days_slots = {(m.day, m.slot_index) for m in members}
        assert len(days_slots) == 1, f"group {gid} not co-located: {days_slots}"
        # ...but each member has its own distinct room.
        rooms_used = {m.room_id for m in members}
        assert len(rooms_used) == len(members), f"group {gid} reused a room: {members}"


def test_solver_rejects_group_with_mismatched_durations():
    courses = _elective_courses()
    courses[1]["duration"] = 2  # break the "same duration" assumption
    sessions = expand_sessions(courses)
    solver = CSPSolver(_config())
    result = solver.solve(sessions, _rooms())
    assert result.status == "FAILED"
