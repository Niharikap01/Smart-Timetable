from app.scheduler.constraints.base import ScheduleAssignment
from app.scheduler.constraints.c13_recess import RecessConstraint


def _assignment(section_id):
    return ScheduleAssignment(session_id="S", course_id=1, section_id=section_id,
        teacher_id=1, room_id=1, day="Monday", slot_index=2, duration=1,
        room_type="lecture", room_capacity=60, section_strength=50,
        course_type="lecture", required_room_type="lecture", faculty_type="regular")


def test_recess_is_scoped_to_its_section():
    constraint = RecessConstraint()
    config = {"recess_slots": {(2, "Monday", 2)}}
    assert not constraint.check(_assignment(2), [], config).valid
    assert constraint.check(_assignment(3), [], config).valid
