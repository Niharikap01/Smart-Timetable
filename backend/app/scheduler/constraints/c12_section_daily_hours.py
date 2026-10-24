from typing import List
from .base import Constraint, ConstraintResult, ScheduleAssignment
from app.scheduler.batches import assignment_batch_keys


class SectionDailyHoursConstraint(Constraint):
    code = "C12"
    name = "Maximum scheduled hours per day for a section"

    def check(self, candidate: ScheduleAssignment, existing: List[ScheduleAssignment], config: dict) -> ConstraintResult:
        limit = config.get("MAX_SECTION_DAILY_HOURS", 6)
        candidate_slots = set(range(candidate.slot_index, candidate.slot_index + candidate.duration))
        for key in assignment_batch_keys(candidate):
            occupied = {
                slot for assignment in existing
                if key in assignment_batch_keys(assignment) and assignment.day == candidate.day
                for slot in range(assignment.slot_index, assignment.slot_index + assignment.duration)
            } | candidate_slots
            if len(occupied) > limit:
                return ConstraintResult(valid=False, constraint=self.code,
                    message=f"Section {candidate.section_id} would have {len(occupied)} hours on {candidate.day} (limit {limit})")
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(self, assignments: List[ScheduleAssignment], config: dict) -> List[ConstraintResult]:
        limit = config.get("MAX_SECTION_DAILY_HOURS", 6)
        by_section_day: dict = {}
        for a in assignments:
            for key in assignment_batch_keys(a):
                by_section_day.setdefault((*key, a.day), set()).update(
                    range(a.slot_index, a.slot_index + a.duration)
                )
        return [
            ConstraintResult(
                valid=False, constraint=self.code,
                message=f"Section {sid} has {hrs} hours on {day} (limit {limit})",
            )
            for (sid, _batch, day), slots in by_section_day.items() if len(slots) > limit
            for hrs in [len(slots)]
        ]
