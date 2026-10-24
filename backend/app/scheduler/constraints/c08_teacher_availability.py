from typing import List, Set, Tuple
from .base import Constraint, ConstraintResult, ScheduleAssignment
from app.scheduler.batches import teacher_ids


class TeacherAvailabilityConstraint(Constraint):
    code = "C08"
    name = "Teacher availability must be respected"

    def check(self, candidate: ScheduleAssignment, existing: List[ScheduleAssignment], config: dict) -> ConstraintResult:
        unavailable: Set[Tuple[int, str, int]] = config.get("teacher_unavailable", set())
        for teacher_id in teacher_ids(candidate.teacher_id, candidate.teacher_ids):
            for s in range(candidate.slot_index, candidate.slot_index + candidate.duration):
                if (teacher_id, candidate.day, s) in unavailable:
                    return ConstraintResult(
                        valid=False, constraint=self.code,
                        message=f"Teacher {teacher_id} unavailable on {candidate.day} slot {s}",
                    )
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(self, assignments: List[ScheduleAssignment], config: dict) -> List[ConstraintResult]:
        unavailable: Set[Tuple[int, str, int]] = config.get("teacher_unavailable", set())
        results = []
        for a in assignments:
            for teacher_id in teacher_ids(a.teacher_id, a.teacher_ids):
                for s in range(a.slot_index, a.slot_index + a.duration):
                    if (teacher_id, a.day, s) in unavailable:
                        results.append(ConstraintResult(
                            valid=False, constraint=self.code,
                            message=f"Teacher {teacher_id} unavailable on {a.day} slot {s}",
                        ))
        return results
