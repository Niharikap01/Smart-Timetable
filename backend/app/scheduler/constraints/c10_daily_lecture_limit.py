from typing import List
from collections import defaultdict
from .base import Constraint, ConstraintResult, ScheduleAssignment


class DailyLectureLimitConstraint(Constraint):
    """Configurable: MAX_LECTURE_PERIODS_PER_DAY (pending confirmation)."""
    code = "C10"
    name = "Maximum lecture periods per day"

    def check(self, candidate: ScheduleAssignment, existing: List[ScheduleAssignment], config: dict) -> ConstraintResult:
        limit = config.get("MAX_LECTURE_PERIODS_PER_DAY", 5)
        if candidate.course_type != "lecture":
            return ConstraintResult(valid=True, constraint=self.code)
        count = sum(
            a.duration for a in existing
            if a.section_id == candidate.section_id and a.day == candidate.day and a.course_type == "lecture"
        )
        if count + candidate.duration > limit:
            return ConstraintResult(
                valid=False, constraint=self.code,
                message=f"Section {candidate.section_id} would exceed {limit} lecture periods on {candidate.day}",
            )
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(self, assignments: List[ScheduleAssignment], config: dict) -> List[ConstraintResult]:
        limit = config.get("MAX_LECTURE_PERIODS_PER_DAY", 5)
        by_section_day: dict = defaultdict(int)
        for a in assignments:
            if a.course_type == "lecture":
                by_section_day[(a.section_id, a.day)] += a.duration
        return [
            ConstraintResult(
                valid=False, constraint=self.code,
                message=f"Section {sid} has {cnt} lecture periods on {day} (limit {limit})",
            )
            for (sid, day), cnt in by_section_day.items() if cnt > limit
        ]
