from typing import List
from .base import Constraint, ConstraintResult, ScheduleAssignment


class RoomTypeConstraint(Constraint):
    code = "C05"
    name = "Room type must match required room type"

    def check(self, candidate: ScheduleAssignment, existing: List[ScheduleAssignment], config: dict) -> ConstraintResult:
        if candidate.room_type != candidate.required_room_type:
            return ConstraintResult(
                valid=False, constraint=self.code,
                message=f"Room type '{candidate.room_type}' != required '{candidate.required_room_type}'",
            )
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(self, assignments: List[ScheduleAssignment], config: dict) -> List[ConstraintResult]:
        return [
            ConstraintResult(
                valid=False, constraint=self.code,
                message=f"Session {a.session_id}: room type '{a.room_type}' != required '{a.required_room_type}'",
            )
            for a in assignments if a.room_type != a.required_room_type
        ]
