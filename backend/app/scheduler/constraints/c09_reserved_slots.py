from typing import List, Set, Tuple
from .base import Constraint, ConstraintResult, ScheduleAssignment


class ReservedSlotsConstraint(Constraint):
    code = "C09"
    name = "Reserved slots must never contain sessions"

    def check(self, candidate: ScheduleAssignment, existing: List[ScheduleAssignment], config: dict) -> ConstraintResult:
        reserved: Set[Tuple[str, int]] = config.get("reserved_slots", set())
        for s in range(candidate.slot_index, candidate.slot_index + candidate.duration):
            if (candidate.day, s) in reserved:
                return ConstraintResult(
                    valid=False, constraint=self.code,
                    message=f"Slot ({candidate.day}, {s}) is reserved",
                )
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(self, assignments: List[ScheduleAssignment], config: dict) -> List[ConstraintResult]:
        reserved: Set[Tuple[str, int]] = config.get("reserved_slots", set())
        results = []
        for a in assignments:
            for s in range(a.slot_index, a.slot_index + a.duration):
                if (a.day, s) in reserved:
                    results.append(ConstraintResult(
                        valid=False, constraint=self.code,
                        message=f"Session {a.session_id} placed in reserved slot ({a.day}, {s})",
                    ))
        return results
