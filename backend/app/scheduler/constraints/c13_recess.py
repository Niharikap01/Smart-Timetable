from typing import List, Set, Tuple
from .base import Constraint, ConstraintResult, ScheduleAssignment


class RecessConstraint(Constraint):
    """Configurable: RECESS slots within 11AM-3PM window (pending confirmation)."""
    code = "C13"
    name = "Recess must fall within configured window"

    def check(self, candidate: ScheduleAssignment, existing: List[ScheduleAssignment], config: dict) -> ConstraintResult:
        recess_slots: Set[Tuple[int, str, int]] = config.get("recess_slots", set())
        for s in range(candidate.slot_index, candidate.slot_index + candidate.duration):
            # Section-specific recesses use (section_id, day, slot).  The
            # two-part form remains supported for global lunch/recess data and
            # older templates/tests.
            if (candidate.section_id, candidate.day, s) in recess_slots or (candidate.day, s) in recess_slots:
                return ConstraintResult(
                    valid=False, constraint=self.code,
                    message=f"Slot ({candidate.day}, {s}) is a recess slot",
                )
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(self, assignments: List[ScheduleAssignment], config: dict) -> List[ConstraintResult]:
        recess_slots: Set[Tuple[int, str, int]] = config.get("recess_slots", set())
        results = []
        for a in assignments:
            for s in range(a.slot_index, a.slot_index + a.duration):
                if (a.section_id, a.day, s) in recess_slots or (a.day, s) in recess_slots:
                    results.append(ConstraintResult(
                        valid=False, constraint=self.code,
                        message=f"Session {a.session_id} placed in recess slot ({a.day}, {s})",
                    ))
        return results
