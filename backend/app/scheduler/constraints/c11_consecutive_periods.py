from typing import List
from collections import defaultdict
from .base import Constraint, ConstraintResult, ScheduleAssignment


class ConsecutivePeriodsConstraint(Constraint):
    code = "C11"
    name = "No more than N continuous periods without a break"

    def check(self, candidate: ScheduleAssignment, existing: List[ScheduleAssignment], config: dict) -> ConstraintResult:
        limit = config.get("MAX_CONSECUTIVE_PERIODS", 2)
        section_day = [
            a for a in existing
            if a.section_id == candidate.section_id and a.day == candidate.day
        ]
        occupied = set()
        for a in section_day:
            for s in range(a.slot_index, a.slot_index + a.duration):
                occupied.add(s)
        for s in range(candidate.slot_index, candidate.slot_index + candidate.duration):
            occupied.add(s)

        if not occupied:
            return ConstraintResult(valid=True, constraint=self.code)

        sorted_slots = sorted(occupied)
        run = 1
        for i in range(1, len(sorted_slots)):
            if sorted_slots[i] == sorted_slots[i - 1] + 1:
                run += 1
                if run > limit:
                    return ConstraintResult(
                        valid=False, constraint=self.code,
                        message=f"Section {candidate.section_id} would have {run} consecutive periods on {candidate.day}",
                    )
            else:
                run = 1
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(self, assignments: List[ScheduleAssignment], config: dict) -> List[ConstraintResult]:
        limit = config.get("MAX_CONSECUTIVE_PERIODS", 2)
        by_section_day: dict = defaultdict(set)
        for a in assignments:
            for s in range(a.slot_index, a.slot_index + a.duration):
                by_section_day[(a.section_id, a.day)].add(s)
        results = []
        for (sid, day), slots in by_section_day.items():
            sorted_slots = sorted(slots)
            run = 1
            for i in range(1, len(sorted_slots)):
                if sorted_slots[i] == sorted_slots[i - 1] + 1:
                    run += 1
                    if run > limit:
                        results.append(ConstraintResult(
                            valid=False, constraint=self.code,
                            message=f"Section {sid} has {run} consecutive periods on {day}",
                        ))
                        break
                else:
                    run = 1
        return results
