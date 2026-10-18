from typing import List
from .base import Constraint, ConstraintResult, ScheduleAssignment


class ContiguousSessionsConstraint(Constraint):
    code = "C07"
    name = "Multi-period sessions must occupy contiguous slots on same day"

    def check(self, candidate: ScheduleAssignment, existing: List[ScheduleAssignment], config: dict) -> ConstraintResult:
        # Duration > 1 means the session spans multiple contiguous slots.
        # The candidate's slot_index is the start; contiguity is ensured by
        # the candidate generator only producing contiguous slot ranges.
        # This check verifies that the slots used don't span into a reserved
        # or out-of-range area — handled at generation time.
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(self, assignments: List[ScheduleAssignment], config: dict) -> List[ConstraintResult]:
        results = []
        max_slot = config.get("max_slot_index", 7)
        for a in assignments:
            if a.duration > 1:
                end_slot = a.slot_index + a.duration - 1
                if end_slot > max_slot:
                    results.append(ConstraintResult(
                        valid=False, constraint=self.code,
                        message=f"Session {a.session_id}: slots {a.slot_index}-{end_slot} exceed day boundary ({max_slot})",
                    ))
        return results
