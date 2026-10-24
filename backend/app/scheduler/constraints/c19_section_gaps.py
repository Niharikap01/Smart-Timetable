"""Keep each section's teaching day compact around its registered recess."""
from collections import defaultdict
from typing import Iterable, List, Set, Tuple

from .base import Constraint, ConstraintResult, ScheduleAssignment
from app.scheduler.batches import assignment_batch_keys, batch_indices


class SectionGapsConstraint(Constraint):
    """Students may pause only for a configured one-period recess.

    A timetable is evaluated in occupied *periods*, rather than session rows,
    so a two-period lab and parallel elective members are handled correctly.
    """

    code = "C19"
    name = "Sections may only have their registered one-period recess"

    @staticmethod
    def _occupied(assignments: Iterable[ScheduleAssignment], section_id: int, batch: int, day: str) -> Set[int]:
        slots: Set[int] = set()
        for assignment in assignments:
            if assignment.section_id == section_id and batch in batch_indices(assignment.batch_label) and assignment.day == day:
                slots.update(range(assignment.slot_index, assignment.slot_index + assignment.duration))
        return slots

    @staticmethod
    def _invalid_gap(occupied: Set[int], section_id: int, day: str, allowed_breaks: Set[Tuple[int, str, int]]) -> int | None:
        if len(occupied) < 2:
            return None
        gap_length = 0
        for slot_index in range(min(occupied), max(occupied) + 1):
            if slot_index in occupied:
                gap_length = 0
                continue
            gap_length += 1
            # A break must be both registered as recess/lunch and no longer
            # than one one-hour period.  Two adjacent reserved periods must
            # not silently become a two-hour student gap.
            if (section_id, day, slot_index) not in allowed_breaks or gap_length > 1:
                return slot_index
        return None

    def check(self, candidate: ScheduleAssignment, existing: List[ScheduleAssignment], config: dict) -> ConstraintResult:
        allowed_breaks: Set[Tuple[int, str, int]] = config.get("allowed_break_slots", set())
        for _section_id, batch in assignment_batch_keys(candidate):
            occupied = self._occupied([*existing, candidate], candidate.section_id, batch, candidate.day)
            gap = self._invalid_gap(occupied, candidate.section_id, candidate.day, allowed_breaks)
            if gap is not None:
                return ConstraintResult(valid=False, constraint=self.code,
                    message=f"Section {candidate.section_id} would have an unnecessary gap at ({candidate.day}, {gap})")
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(self, assignments: List[ScheduleAssignment], config: dict) -> List[ConstraintResult]:
        allowed_breaks: Set[Tuple[int, str, int]] = config.get("allowed_break_slots", set())
        per_section_day: dict[tuple[int, int, str], Set[int]] = defaultdict(set)
        for assignment in assignments:
            for section_id, batch in assignment_batch_keys(assignment):
                per_section_day[(section_id, batch, assignment.day)].update(
                    range(assignment.slot_index, assignment.slot_index + assignment.duration)
                )
        results: List[ConstraintResult] = []
        for (section_id, _batch, day), occupied in per_section_day.items():
            gap = self._invalid_gap(occupied, section_id, day, allowed_breaks)
            if gap is not None:
                results.append(ConstraintResult(
                    valid=False,
                    constraint=self.code,
                    message=f"Section {section_id} has an unnecessary gap at ({day}, {gap})",
                ))
        return results
