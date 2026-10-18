from typing import List
from .base import Constraint, ConstraintResult, ScheduleAssignment


class CapacityConstraint(Constraint):
    code = "C04"
    name = "Room capacity >= section strength"

    def check(self, candidate: ScheduleAssignment, existing: List[ScheduleAssignment], config: dict) -> ConstraintResult:
        if candidate.room_capacity < candidate.section_strength:
            return ConstraintResult(
                valid=False, constraint=self.code,
                message=f"Room capacity {candidate.room_capacity} < section strength {candidate.section_strength}",
            )
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(self, assignments: List[ScheduleAssignment], config: dict) -> List[ConstraintResult]:
        return [
            ConstraintResult(
                valid=False, constraint=self.code,
                message=f"Session {a.session_id}: room capacity {a.room_capacity} < strength {a.section_strength}",
            )
            for a in assignments if a.room_capacity < a.section_strength
        ]
