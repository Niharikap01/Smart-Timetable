from typing import List, Set, Tuple
from .base import Constraint, ConstraintResult, ScheduleAssignment


class HonoursSlotConstraint(Constraint):
    """Configurable: Honours reserved slot across sections (pending confirmation)."""
    code = "C18"
    name = "Honours-program shared reserved slot"
    severity = "HARD"

    def check(self, candidate: ScheduleAssignment, existing: List[ScheduleAssignment], config: dict) -> ConstraintResult:
        if not config.get("HONOURS_RESERVED_ENABLED", False):
            return ConstraintResult(valid=True, constraint=self.code)
        honours_slots: Set[Tuple[str, int]] = config.get("honours_slots", set())
        for s in range(candidate.slot_index, candidate.slot_index + candidate.duration):
            if (candidate.day, s) in honours_slots:
                return ConstraintResult(
                    valid=False, constraint=self.code,
                    message=f"Slot ({candidate.day}, {s}) is reserved for Honours program",
                )
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(self, assignments: List[ScheduleAssignment], config: dict) -> List[ConstraintResult]:
        if not config.get("HONOURS_RESERVED_ENABLED", False):
            return []
        honours_slots: Set[Tuple[str, int]] = config.get("honours_slots", set())
        results = []
        for a in assignments:
            for s in range(a.slot_index, a.slot_index + a.duration):
                if (a.day, s) in honours_slots:
                    results.append(ConstraintResult(
                        valid=False, constraint=self.code,
                        message=f"Session {a.session_id} placed in Honours reserved slot ({a.day}, {s})",
                    ))
        return results
