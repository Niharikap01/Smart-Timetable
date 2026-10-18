"""Prevent a section's first class from beginning too late in the day."""
from collections import defaultdict
from typing import List

from .base import Constraint, ConstraintResult, ScheduleAssignment


class SectionStartTimeConstraint(Constraint):
    code = "C20"
    name = "A section must start by the configured latest period"

    @staticmethod
    def _first_slot(assignments: List[ScheduleAssignment], section_id: int, day: str) -> int | None:
        slots = [assignment.slot_index for assignment in assignments if assignment.section_id == section_id and assignment.day == day]
        return min(slots) if slots else None

    def check(self, candidate: ScheduleAssignment, existing: List[ScheduleAssignment], config: dict) -> ConstraintResult:
        latest_start = config.get("MAX_SECTION_START_SLOT_BY_DAY", {}).get(
            candidate.day, config.get("MAX_SECTION_START_SLOT", 3),
        )
        first_slot = self._first_slot([*existing, candidate], candidate.section_id, candidate.day)
        if first_slot is not None and first_slot > latest_start:
            return ConstraintResult(
                valid=False,
                constraint=self.code,
                message=f"Section {candidate.section_id} would start at period {first_slot}; it must start by period {latest_start}",
            )
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(self, assignments: List[ScheduleAssignment], config: dict) -> List[ConstraintResult]:
        latest_by_day = config.get("MAX_SECTION_START_SLOT_BY_DAY", {})
        default_latest = config.get("MAX_SECTION_START_SLOT", 3)
        starts: dict[tuple[int, str], int] = {}
        for assignment in assignments:
            key = (assignment.section_id, assignment.day)
            starts[key] = min(starts.get(key, assignment.slot_index), assignment.slot_index)
        return [
            ConstraintResult(
                valid=False,
                constraint=self.code,
                message=f"Section {section_id} starts at period {start} on {day}; it must start by period {latest_by_day.get(day, default_latest)}",
            )
            for (section_id, day), start in starts.items()
            if start > latest_by_day.get(day, default_latest)
        ]
