"""Tests for every hard constraint — each constructs a valid and invalid scenario."""
import pytest
from app.scheduler.constraints.base import ScheduleAssignment, ConstraintResult
from app.scheduler.constraints.c01_teacher_conflict import TeacherConflictConstraint
from app.scheduler.constraints.c02_section_conflict import SectionConflictConstraint
from app.scheduler.constraints.c03_room_conflict import RoomConflictConstraint
from app.scheduler.constraints.c04_capacity import CapacityConstraint
from app.scheduler.constraints.c05_room_type import RoomTypeConstraint
from app.scheduler.constraints.c08_teacher_availability import TeacherAvailabilityConstraint
from app.scheduler.constraints.c09_reserved_slots import ReservedSlotsConstraint
from app.scheduler.constraints.c10_daily_lecture_limit import DailyLectureLimitConstraint
from app.scheduler.constraints.c11_consecutive_periods import ConsecutivePeriodsConstraint
from app.scheduler.constraints.c12_section_daily_hours import SectionDailyHoursConstraint
from app.scheduler.constraints.c13_recess import RecessConstraint
from app.scheduler.constraints.c14_visiting_faculty import VisitingFacultyConstraint
from app.scheduler.constraints.c17_teacher_daily_hours import TeacherDailyHoursConstraint
from app.scheduler.constraints.c18_honours_slot import HonoursSlotConstraint
from app.scheduler.constraints.c19_section_gaps import SectionGapsConstraint
from app.scheduler.constraints.c20_section_start_time import SectionStartTimeConstraint
from app.scheduler.conflict_checker import check_candidate, validate_schedule, is_candidate_valid

CFG = {"MAX_CONSECUTIVE_PERIODS": 2, "MAX_SECTION_DAILY_HOURS": 6,
       "MAX_LECTURE_PERIODS_PER_DAY": 5, "MAX_TEACHER_DAILY_HOURS": 7}


def _make(sid="s1", cid=1, secid=1, tid=1, rid=1, day="Monday", slot=0, dur=1,
          rtype="lecture", rcap=60, sstr=50, ctype="lecture", rroom="lecture", ftype="regular"):
    return ScheduleAssignment(
        session_id=sid, course_id=cid, section_id=secid, teacher_id=tid,
        room_id=rid, day=day, slot_index=slot, duration=dur,
        room_type=rtype, room_capacity=rcap, section_strength=sstr,
        course_type=ctype, required_room_type=rroom, faculty_type=ftype,
    )


# C01 Teacher conflict
def test_teacher_no_conflict():
    c = TeacherConflictConstraint()
    existing = [_make(tid=1, slot=0)]
    cand = _make(tid=1, slot=1)
    assert c.check(cand, existing, CFG).valid

def test_teacher_double_booking():
    c = TeacherConflictConstraint()
    existing = [_make(tid=1, slot=0)]
    cand = _make(sid="s2", tid=1, slot=0)
    r = c.check(cand, existing, CFG)
    assert not r.valid
    assert r.constraint == "C01"


# C02 Section conflict
def test_section_no_conflict():
    c = SectionConflictConstraint()
    existing = [_make(secid=1, slot=0)]
    cand = _make(secid=1, slot=1)
    assert c.check(cand, existing, CFG).valid

def test_section_double_booking():
    c = SectionConflictConstraint()
    existing = [_make(secid=1, slot=0)]
    cand = _make(sid="s2", secid=1, slot=0)
    assert not c.check(cand, existing, CFG).valid


# C03 Room conflict
def test_room_no_conflict():
    c = RoomConflictConstraint()
    existing = [_make(rid=1, slot=0)]
    cand = _make(rid=1, slot=1)
    assert c.check(cand, existing, CFG).valid

def test_room_double_booking():
    c = RoomConflictConstraint()
    existing = [_make(rid=1, slot=0)]
    cand = _make(sid="s2", rid=1, slot=0, tid=2, secid=2)
    assert not c.check(cand, existing, CFG).valid


# C04 Capacity
def test_room_capacity_ok():
    c = CapacityConstraint()
    cand = _make(rcap=60, sstr=50)
    assert c.check(cand, [], CFG).valid

def test_room_capacity_fail():
    c = CapacityConstraint()
    cand = _make(rcap=30, sstr=50)
    r = c.check(cand, [], CFG)
    assert not r.valid
    assert r.constraint == "C04"


# C05 Room type
def test_room_type_match():
    c = RoomTypeConstraint()
    cand = _make(rtype="lab", rroom="lab")
    assert c.check(cand, [], CFG).valid

def test_room_type_mismatch():
    c = RoomTypeConstraint()
    cand = _make(rtype="lecture", rroom="lab")
    assert not c.check(cand, [], CFG).valid


# C08 Teacher availability
def test_teacher_available():
    c = TeacherAvailabilityConstraint()
    cand = _make(tid=1, day="Monday", slot=0)
    assert c.check(cand, [], {**CFG, "teacher_unavailable": set()}).valid

def test_teacher_unavailable():
    c = TeacherAvailabilityConstraint()
    cand = _make(tid=1, day="Monday", slot=0)
    cfg = {**CFG, "teacher_unavailable": {(1, "Monday", 0)}}
    assert not c.check(cand, [], cfg).valid


# C09 Reserved slots
def test_not_reserved():
    c = ReservedSlotsConstraint()
    cand = _make(day="Monday", slot=0)
    assert c.check(cand, [], {**CFG, "reserved_slots": set()}).valid

def test_reserved_slot():
    c = ReservedSlotsConstraint()
    cand = _make(day="Monday", slot=0)
    cfg = {**CFG, "reserved_slots": {("Monday", 0)}}
    assert not c.check(cand, [], cfg).valid


# C10 Daily lecture limit
def test_lecture_limit_ok():
    c = DailyLectureLimitConstraint()
    existing = [_make(secid=1, slot=i, sid=f"e{i}") for i in range(4)]
    cand = _make(secid=1, slot=4, sid="new")
    assert c.check(cand, existing, {**CFG, "MAX_LECTURE_PERIODS_PER_DAY": 5}).valid

def test_lecture_limit_exceeded():
    c = DailyLectureLimitConstraint()
    existing = [_make(secid=1, slot=i, sid=f"e{i}") for i in range(5)]
    cand = _make(secid=1, slot=5, sid="new")
    assert not c.check(cand, existing, {**CFG, "MAX_LECTURE_PERIODS_PER_DAY": 5}).valid


# C11 Consecutive periods
def test_consecutive_ok():
    c = ConsecutivePeriodsConstraint()
    existing = [_make(secid=1, slot=0), _make(secid=1, slot=1, sid="e2")]
    # slot 3 leaves a gap at 2
    cand = _make(secid=1, slot=3, sid="new")
    assert c.check(cand, existing, {**CFG, "MAX_CONSECUTIVE_PERIODS": 2}).valid

def test_consecutive_exceeded():
    c = ConsecutivePeriodsConstraint()
    existing = [_make(secid=1, slot=0), _make(secid=1, slot=1, sid="e2")]
    cand = _make(secid=1, slot=2, sid="new")
    assert not c.check(cand, existing, {**CFG, "MAX_CONSECUTIVE_PERIODS": 2}).valid


# C12 Section daily hours
def test_section_hours_ok():
    c = SectionDailyHoursConstraint()
    existing = [_make(secid=1, slot=i, sid=f"e{i}") for i in range(5)]
    cand = _make(secid=1, slot=5, sid="new")
    assert c.check(cand, existing, {**CFG, "MAX_SECTION_DAILY_HOURS": 6}).valid

def test_section_hours_exceeded():
    c = SectionDailyHoursConstraint()
    existing = [_make(secid=1, slot=i, sid=f"e{i}") for i in range(6)]
    cand = _make(secid=1, slot=6, sid="new")
    assert not c.check(cand, existing, {**CFG, "MAX_SECTION_DAILY_HOURS": 6}).valid


# C13 Recess
def test_recess_ok():
    c = RecessConstraint()
    cand = _make(day="Monday", slot=0)
    assert c.check(cand, [], {**CFG, "recess_slots": {("Monday", 4)}}).valid

def test_recess_violated():
    c = RecessConstraint()
    cand = _make(day="Monday", slot=4)
    assert not c.check(cand, [], {**CFG, "recess_slots": {("Monday", 4)}}).valid


# C14 Visiting faculty
def test_visiting_available():
    c = VisitingFacultyConstraint()
    cand = _make(ftype="visiting", tid=1, day="Monday", slot=0)
    assert c.check(cand, [], {**CFG, "teacher_unavailable": set()}).valid

def test_visiting_unavailable():
    c = VisitingFacultyConstraint()
    cand = _make(ftype="visiting", tid=1, day="Monday", slot=0)
    assert not c.check(cand, [], {**CFG, "teacher_unavailable": {(1, "Monday", 0)}}).valid

def test_visiting_constraint_skips_regular():
    c = VisitingFacultyConstraint()
    cand = _make(ftype="regular", tid=1, day="Monday", slot=0)
    assert c.check(cand, [], {**CFG, "teacher_unavailable": {(1, "Monday", 0)}}).valid


# C17 Teacher daily hours
def test_teacher_hours_ok():
    c = TeacherDailyHoursConstraint()
    existing = [_make(tid=1, slot=i, sid=f"e{i}") for i in range(6)]
    cand = _make(tid=1, slot=6, sid="new")
    assert c.check(cand, existing, {**CFG, "MAX_TEACHER_DAILY_HOURS": 7}).valid

def test_teacher_hours_exceeded():
    c = TeacherDailyHoursConstraint()
    existing = [_make(tid=1, slot=i, sid=f"e{i}") for i in range(7)]
    cand = _make(tid=1, slot=7, sid="new")
    assert not c.check(cand, existing, {**CFG, "MAX_TEACHER_DAILY_HOURS": 7}).valid


# C18 Honours slot
def test_honours_disabled():
    c = HonoursSlotConstraint()
    cand = _make(day="Monday", slot=5)
    assert c.check(cand, [], {**CFG, "HONOURS_RESERVED_ENABLED": False}).valid

def test_honours_slot_violated():
    c = HonoursSlotConstraint()
    cand = _make(day="Monday", slot=5)
    cfg = {**CFG, "HONOURS_RESERVED_ENABLED": True, "honours_slots": {("Monday", 5)}}
    assert not c.check(cand, [], cfg).valid


# C19 Student timetable gaps
def test_section_gap_requires_registered_recess():
    c = SectionGapsConstraint()
    existing = [_make(secid=1, slot=0)]
    cand = _make(sid="later", secid=1, slot=2)
    assert not c.check(cand, existing, CFG).valid


def test_section_gap_allows_registered_recess():
    c = SectionGapsConstraint()
    existing = [_make(secid=1, slot=0)]
    cand = _make(sid="later", secid=1, slot=2)
    assert c.check(cand, existing, {**CFG, "allowed_break_slots": {(1, "Monday", 1)}}).valid


def test_section_gap_never_allows_two_hour_break():
    c = SectionGapsConstraint()
    existing = [_make(secid=1, slot=0)]
    cand = _make(sid="later", secid=1, slot=3)
    allowed = {(1, "Monday", 1), (1, "Monday", 2)}
    assert not c.check(cand, existing, {**CFG, "allowed_break_slots": allowed}).valid


# C20 Section start time
def test_section_may_start_at_noon():
    c = SectionStartTimeConstraint()
    assert c.check(_make(secid=1, slot=3), [], {**CFG, "MAX_SECTION_START_SLOT": 3}).valid


def test_section_may_not_start_at_one_pm():
    c = SectionStartTimeConstraint()
    assert not c.check(_make(secid=1, slot=4), [], {**CFG, "MAX_SECTION_START_SLOT": 3}).valid


# Full conflict checker
def test_is_candidate_valid_ok():
    cand = _make()
    assert is_candidate_valid(cand, [], CFG)

def test_is_candidate_valid_conflict():
    existing = [_make(tid=1, slot=0)]
    cand = _make(sid="s2", tid=1, slot=0)
    assert not is_candidate_valid(cand, existing, CFG)

def test_validate_schedule_clean():
    assignments = [_make(slot=0), _make(sid="s2", slot=1, tid=2, secid=2, rid=2)]
    violations = validate_schedule(assignments, CFG)
    assert len(violations) == 0

def test_validate_schedule_with_violation():
    assignments = [_make(slot=0), _make(sid="s2", slot=0, secid=1)]
    violations = validate_schedule(assignments, CFG)
    assert any(v.constraint == "C01" or v.constraint == "C02" or v.constraint == "C03" for v in violations)


# Multi-period tests
def test_multi_period_teacher_conflict():
    c = TeacherConflictConstraint()
    existing = [_make(tid=1, slot=0)]
    cand = _make(sid="s2", tid=1, slot=0, dur=2)
    assert not c.check(cand, existing, CFG).valid

def test_multi_period_no_conflict():
    c = TeacherConflictConstraint()
    existing = [_make(tid=1, slot=0)]
    cand = _make(sid="s2", tid=1, slot=1, dur=2)
    assert c.check(cand, existing, CFG).valid
