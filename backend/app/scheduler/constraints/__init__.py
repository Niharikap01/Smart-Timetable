from .base import Constraint, ConstraintResult, ScheduleAssignment
from .c01_teacher_conflict import TeacherConflictConstraint
from .c02_section_conflict import SectionConflictConstraint
from .c03_room_conflict import RoomConflictConstraint
from .c04_capacity import CapacityConstraint
from .c05_room_type import RoomTypeConstraint
from .c06_weekly_sessions import WeeklySessionsConstraint
from .c07_contiguous_sessions import ContiguousSessionsConstraint
from .c08_teacher_availability import TeacherAvailabilityConstraint
from .c09_reserved_slots import ReservedSlotsConstraint
from .c10_daily_lecture_limit import DailyLectureLimitConstraint
from .c11_consecutive_periods import ConsecutivePeriodsConstraint
from .c12_section_daily_hours import SectionDailyHoursConstraint
from .c13_recess import RecessConstraint
from .c14_visiting_faculty import VisitingFacultyConstraint
from .c15_senior_faculty import SeniorFacultyConstraint
from .c16_room_inventory import RoomInventoryConstraint
from .c17_teacher_daily_hours import TeacherDailyHoursConstraint
from .c18_honours_slot import HonoursSlotConstraint
from .c19_section_gaps import SectionGapsConstraint
from .c20_section_start_time import SectionStartTimeConstraint


ALL_CONSTRAINTS = [
    TeacherConflictConstraint(),
    SectionConflictConstraint(),
    RoomConflictConstraint(),
    CapacityConstraint(),
    RoomTypeConstraint(),
    WeeklySessionsConstraint(),
    ContiguousSessionsConstraint(),
    TeacherAvailabilityConstraint(),
    ReservedSlotsConstraint(),
    DailyLectureLimitConstraint(),
    ConsecutivePeriodsConstraint(),
    SectionDailyHoursConstraint(),
    RecessConstraint(),
    VisitingFacultyConstraint(),
    SeniorFacultyConstraint(),
    RoomInventoryConstraint(),
    TeacherDailyHoursConstraint(),
    HonoursSlotConstraint(),
    SectionGapsConstraint(),
    SectionStartTimeConstraint(),
]


def get_hard_constraints(config: dict) -> list:
    return [c for c in ALL_CONSTRAINTS if c.is_enabled(config) and c.is_hard(config)]


def get_all_enabled(config: dict) -> list:
    return [c for c in ALL_CONSTRAINTS if c.is_enabled(config)]
