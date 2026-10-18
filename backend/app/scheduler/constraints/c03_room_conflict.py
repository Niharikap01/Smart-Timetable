from typing import List
from .base import Constraint, ConstraintResult, ScheduleAssignment


class RoomConflictConstraint(Constraint):
    code = "C03"
    name = "No room double-booking"

    def check(self, candidate: ScheduleAssignment, existing: List[ScheduleAssignment], config: dict) -> ConstraintResult:
        for a in existing:
            if a.room_id == candidate.room_id and a.day == candidate.day:
                cand_slots = set(range(candidate.slot_index, candidate.slot_index + candidate.duration))
                exist_slots = set(range(a.slot_index, a.slot_index + a.duration))
                if cand_slots & exist_slots:
                    return ConstraintResult(
                        valid=False, constraint=self.code,
                        message=f"Room {candidate.room_id} already occupied at {a.day} slot {a.slot_index}",
                    )
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(self, assignments: List[ScheduleAssignment], config: dict) -> List[ConstraintResult]:
        results = []
        for i, a in enumerate(assignments):
            for b in assignments[i + 1:]:
                if a.room_id == b.room_id and a.day == b.day:
                    a_slots = set(range(a.slot_index, a.slot_index + a.duration))
                    b_slots = set(range(b.slot_index, b.slot_index + b.duration))
                    if a_slots & b_slots:
                        results.append(ConstraintResult(
                            valid=False, constraint=self.code,
                            message=f"Room {a.room_id} double-booked on {a.day} slot {a.slot_index}",
                        ))
        return results
