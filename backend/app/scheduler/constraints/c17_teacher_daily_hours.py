from typing import List
from collections import defaultdict
from .base import Constraint, ConstraintResult, ScheduleAssignment


class TeacherDailyHoursConstraint(Constraint):
    code = "C17"
    name = "Faculty working hours must not exceed limit per day"

    def check(self, candidate: ScheduleAssignment, existing: List[ScheduleAssignment], config: dict) -> ConstraintResult:
        limit = config.get("MAX_TEACHER_DAILY_HOURS", 7)
        total = sum(
            a.duration for a in existing
            if a.teacher_id == candidate.teacher_id and a.day == candidate.day
        )
        if total + candidate.duration > limit:
            return ConstraintResult(
                valid=False, constraint=self.code,
                message=f"Teacher {candidate.teacher_id} would have {total + candidate.duration} hours on {candidate.day} (limit {limit})",
            )
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(self, assignments: List[ScheduleAssignment], config: dict) -> List[ConstraintResult]:
        limit = config.get("MAX_TEACHER_DAILY_HOURS", 7)
        by_teacher_day: dict = defaultdict(int)
        for a in assignments:
            by_teacher_day[(a.teacher_id, a.day)] += a.duration
        return [
            ConstraintResult(
                valid=False, constraint=self.code,
                message=f"Teacher {tid} has {hrs} hours on {day} (limit {limit})",
            )
            for (tid, day), hrs in by_teacher_day.items() if hrs > limit
        ]
