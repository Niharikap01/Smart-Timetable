from typing import List
from .base import Constraint, ConstraintResult, ScheduleAssignment


class RoomInventoryConstraint(Constraint):
    """Room inventory comes from database, not hardcoded counts."""
    code = "C16"
    name = "Room inventory must be configurable"

    def check(self, candidate: ScheduleAssignment, existing: List[ScheduleAssignment], config: dict) -> ConstraintResult:
        valid_room_ids: set = config.get("valid_room_ids", set())
        if valid_room_ids and candidate.room_id not in valid_room_ids:
            return ConstraintResult(
                valid=False, constraint=self.code,
                message=f"Room {candidate.room_id} not in active room inventory",
            )
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(self, assignments: List[ScheduleAssignment], config: dict) -> List[ConstraintResult]:
        valid_room_ids: set = config.get("valid_room_ids", set())
        if not valid_room_ids:
            return []
        return [
            ConstraintResult(
                valid=False, constraint=self.code,
                message=f"Session {a.session_id} uses room {a.room_id} not in active inventory",
            )
            for a in assignments if a.room_id not in valid_room_ids
        ]
