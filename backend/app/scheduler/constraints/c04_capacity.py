from typing import List
from .base import Constraint, ConstraintResult, ScheduleAssignment
from app.scheduler.batches import group_capacity


class CapacityConstraint(Constraint):
    code = "C04"
    name = "Room capacity >= section strength"

    def check(self, candidate: ScheduleAssignment, existing: List[ScheduleAssignment], config: dict) -> ConstraintResult:
        if candidate.program_elective_group_id is not None:
            large_room_names = {"DT-301", "DT-701", "DT-702"}
            room_number = (candidate.room_number or "").replace(" ", "").upper()
            room_is_large = room_number in large_room_names
            group_is_large = candidate.program_elective_student_count > 70
            if room_is_large != group_is_large:
                policy = "DT-301, DT-701, or DT-702" if group_is_large else "a standard lecture room"
                return ConstraintResult(
                    valid=False, constraint=self.code,
                    message=f"Program elective enrollment requires {policy}; room {candidate.room_number or candidate.room_id} does not match.",
                )
        required_capacity = candidate.required_capacity or group_capacity(candidate.section_strength, candidate.batch_label)
        if candidate.room_capacity < required_capacity:
            return ConstraintResult(
                valid=False, constraint=self.code,
                message=f"Room capacity {candidate.room_capacity} < required enrollment {required_capacity}",
            )
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(self, assignments: List[ScheduleAssignment], config: dict) -> List[ConstraintResult]:
        violations = [
            ConstraintResult(
                valid=False, constraint=self.code,
                message=f"Session {a.session_id}: room capacity {a.room_capacity} < required enrollment {a.required_capacity or group_capacity(a.section_strength, a.batch_label)}",
            )
            for a in assignments if a.room_capacity < (a.required_capacity or group_capacity(a.section_strength, a.batch_label))
        ]
        large_room_names = {"DT-301", "DT-701", "DT-702"}
        for assignment in assignments:
            if assignment.program_elective_group_id is None:
                continue
            room_number = (assignment.room_number or "").replace(" ", "").upper()
            room_is_large = room_number in large_room_names
            group_is_large = assignment.program_elective_student_count > 70
            if room_is_large != group_is_large:
                policy = "DT-301, DT-701, or DT-702" if group_is_large else "a standard lecture room"
                violations.append(ConstraintResult(
                    valid=False,
                    constraint=self.code,
                    message=f"Session {assignment.session_id}: program elective enrollment requires {policy}; room {assignment.room_number or assignment.room_id} does not match.",
                ))
        return violations
