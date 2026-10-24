from typing import List
from .base import Constraint, ConstraintResult, ScheduleAssignment
from app.scheduler.batches import assignment_batch_keys


def _longest_run(occupied: set[int]) -> int:
    longest = run = 0
    previous = None
    for slot in sorted(occupied):
        run = run + 1 if previous is not None and slot == previous + 1 else 1
        longest = max(longest, run)
        previous = slot
    return longest


class ConsecutivePeriodsConstraint(Constraint):
    code = "C11"
    name = "No more than N continuous periods without a break"

    def check(self, candidate: ScheduleAssignment, existing: List[ScheduleAssignment], config: dict) -> ConstraintResult:
        limit = config.get("MAX_CONSECUTIVE_PERIODS", 2)
        candidate_slots = set(range(candidate.slot_index, candidate.slot_index + candidate.duration))
        for key in assignment_batch_keys(candidate):
            occupied = {
                slot for assignment in existing
                if key in assignment_batch_keys(assignment) and assignment.day == candidate.day
                for slot in range(assignment.slot_index, assignment.slot_index + assignment.duration)
            } | candidate_slots
            run = _longest_run(occupied)
            if run > limit:
                return ConstraintResult(valid=False, constraint=self.code,
                    message=f"Section {candidate.section_id} would have {run} consecutive periods on {candidate.day}")
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(self, assignments: List[ScheduleAssignment], config: dict) -> List[ConstraintResult]:
        limit = config.get("MAX_CONSECUTIVE_PERIODS", 2)
        by_section_day: dict = {}
        for a in assignments:
            for key in assignment_batch_keys(a):
                by_section_day.setdefault((*key, a.day), set()).update(
                    range(a.slot_index, a.slot_index + a.duration)
                )
        results = []
        for (sid, _batch, day), slots in by_section_day.items():
            run = _longest_run(slots)
            if run > limit:
                results.append(ConstraintResult(valid=False, constraint=self.code,
                    message=f"Section {sid} has {run} consecutive periods on {day}"))
        return results
