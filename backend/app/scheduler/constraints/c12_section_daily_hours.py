from typing import List
from collections import defaultdict
from .base import Constraint, ConstraintResult, ScheduleAssignment


class SectionDailyHoursConstraint(Constraint):
    code = "C12"
    name = "Maximum scheduled hours per day for a section"

    def check(self, candidate: ScheduleAssignment, existing: List[ScheduleAssignment], config: dict) -> ConstraintResult:
        limit = config.get("MAX_SECTION_DAILY_HOURS", 6)
        total = sum(
            a.duration for a in existing
            if a.section_id == candidate.section_id and a.day == candidate.day
        )
        if total + candidate.duration > limit:
            return ConstraintResult(
                valid=False, constraint=self.code,
                message=f"Section {candidate.section_id} would have {total + candidate.duration} hours on {candidate.day} (limit {limit})",
            )
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(self, assignments: List[ScheduleAssignment], config: dict) -> List[ConstraintResult]:
        limit = config.get("MAX_SECTION_DAILY_HOURS", 6)
        by_section_day: dict = defaultdict(int)
        for a in assignments:
            by_section_day[(a.section_id, a.day)] += a.duration
        return [
            ConstraintResult(
                valid=False, constraint=self.code,
                message=f"Section {sid} has {hrs} hours on {day} (limit {limit})",
            )
            for (sid, day), hrs in by_section_day.items() if hrs > limit
        ]
