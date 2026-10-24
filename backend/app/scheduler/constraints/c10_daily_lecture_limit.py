from typing import List
from .base import Constraint, ConstraintResult, ScheduleAssignment
from app.scheduler.batches import assignment_batch_keys


class DailyLectureLimitConstraint(Constraint):
    """Configurable: MAX_LECTURE_PERIODS_PER_DAY (pending confirmation)."""
    code = "C10"
    name = "Maximum lecture periods per day"

    def check(self, candidate: ScheduleAssignment, existing: List[ScheduleAssignment], config: dict) -> ConstraintResult:
        limit = config.get("MAX_LECTURE_PERIODS_PER_DAY", 5)
        if candidate.course_type != "lecture":
            return ConstraintResult(valid=True, constraint=self.code)
        candidate_slots = set(range(candidate.slot_index, candidate.slot_index + candidate.duration))
        for key in assignment_batch_keys(candidate):
            occupied = {
                slot for assignment in existing
                if key in assignment_batch_keys(assignment) and assignment.day == candidate.day
                and assignment.course_type == "lecture"
                for slot in range(assignment.slot_index, assignment.slot_index + assignment.duration)
            }
            if len(occupied | candidate_slots) > limit:
                return ConstraintResult(valid=False, constraint=self.code,
                    message=f"Section {candidate.section_id} would exceed {limit} lecture periods on {candidate.day}")
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(self, assignments: List[ScheduleAssignment], config: dict) -> List[ConstraintResult]:
        limit = config.get("MAX_LECTURE_PERIODS_PER_DAY", 5)
        by_section_day: dict = {}
        for a in assignments:
            if a.course_type == "lecture":
                for key in assignment_batch_keys(a):
                    by_section_day.setdefault((*key, a.day), set()).update(
                        range(a.slot_index, a.slot_index + a.duration)
                    )
        return [
            ConstraintResult(
                valid=False, constraint=self.code,
                message=f"Section {sid} has {cnt} lecture periods on {day} (limit {limit})",
            )
            for (sid, _batch, day), slots in by_section_day.items() if len(slots) > limit
            for cnt in [len(slots)]
        ]
