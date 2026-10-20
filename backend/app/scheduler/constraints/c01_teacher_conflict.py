from typing import List
from .base import Constraint, ConstraintResult, ScheduleAssignment


class TeacherConflictConstraint(Constraint):
    code = "C01"
    name = "No teacher double-booking"

    def check(self, candidate: ScheduleAssignment, existing: List[ScheduleAssignment], config: dict) -> ConstraintResult:
        for a in existing:
            if a.teacher_id == candidate.teacher_id and a.day == candidate.day:
                if candidate.shared_room_group_id and a.shared_room_group_id == candidate.shared_room_group_id:
                    continue
                cand_slots = set(range(candidate.slot_index, candidate.slot_index + candidate.duration))
                exist_slots = set(range(a.slot_index, a.slot_index + a.duration))
                if cand_slots & exist_slots:
                    return ConstraintResult(
                        valid=False, constraint=self.code,
                        message=f"Teacher {candidate.teacher_id} already assigned at {a.day} slot {a.slot_index}",
                    )
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(self, assignments: List[ScheduleAssignment], config: dict) -> List[ConstraintResult]:
        results = []
        for i, a in enumerate(assignments):
            for b in assignments[i + 1:]:
                if a.teacher_id == b.teacher_id and a.day == b.day:
                    if a.shared_room_group_id and a.shared_room_group_id == b.shared_room_group_id:
                        continue
                    a_slots = set(range(a.slot_index, a.slot_index + a.duration))
                    b_slots = set(range(b.slot_index, b.slot_index + b.duration))
                    if a_slots & b_slots:
                        results.append(ConstraintResult(
                            valid=False, constraint=self.code,
                            message=f"Teacher {a.teacher_id} double-booked on {a.day} slot {a.slot_index}",
                        ))
        return results
