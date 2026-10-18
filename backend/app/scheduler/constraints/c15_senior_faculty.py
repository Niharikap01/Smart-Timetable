from typing import List, Set, Tuple
from .base import Constraint, ConstraintResult, ScheduleAssignment


class SeniorFacultyConstraint(Constraint):
    """Configurable severity: HARD | SOFT | DISABLED (pending confirmation)."""
    code = "C15"
    name = "Senior faculty timing preferences"
    severity = "SOFT"

    def check(self, candidate: ScheduleAssignment, existing: List[ScheduleAssignment], config: dict) -> ConstraintResult:
        mode = config.get("SENIOR_FACULTY_CONSTRAINT_MODE", self.severity)
        if mode == "DISABLED" or candidate.faculty_type != "senior":
            return ConstraintResult(valid=True, constraint=self.code)
        prefs: Set[Tuple[int, str, int]] = config.get("senior_preferred_slots", set())
        if not prefs:
            return ConstraintResult(valid=True, constraint=self.code)
        teacher_prefs = {(d, s) for (tid, d, s) in prefs if tid == candidate.teacher_id}
        if not teacher_prefs:
            return ConstraintResult(valid=True, constraint=self.code)
        for s in range(candidate.slot_index, candidate.slot_index + candidate.duration):
            if (candidate.day, s) not in teacher_prefs:
                return ConstraintResult(
                    valid=False, constraint=self.code,
                    message=f"Senior faculty {candidate.teacher_id} prefers different slots on {candidate.day}",
                )
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(self, assignments: List[ScheduleAssignment], config: dict) -> List[ConstraintResult]:
        mode = config.get("SENIOR_FACULTY_CONSTRAINT_MODE", self.severity)
        if mode == "DISABLED":
            return []
        prefs: Set[Tuple[int, str, int]] = config.get("senior_preferred_slots", set())
        results = []
        for a in assignments:
            if a.faculty_type != "senior":
                continue
            teacher_prefs = {(d, s) for (tid, d, s) in prefs if tid == a.teacher_id}
            if not teacher_prefs:
                continue
            for s in range(a.slot_index, a.slot_index + a.duration):
                if (a.day, s) not in teacher_prefs:
                    results.append(ConstraintResult(
                        valid=False, constraint=self.code,
                        message=f"Senior faculty {a.teacher_id} preference violated on {a.day} slot {s}",
                    ))
                    break
        return results
