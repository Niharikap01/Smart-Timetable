from typing import List
from collections import defaultdict
from .base import Constraint, ConstraintResult, ScheduleAssignment


class TeacherDailyHoursConstraint(Constraint):
    code = "C17"
    name = "Faculty working hours must not exceed limit per day"

    def check(self, candidate: ScheduleAssignment, existing: List[ScheduleAssignment], config: dict) -> ConstraintResult:
        limit = config.get("MAX_TEACHER_DAILY_HOURS", 7)
        groups = {}
        for assignment in existing:
            if assignment.teacher_id != candidate.teacher_id or assignment.day != candidate.day:
                continue
            key = assignment.shared_room_group_id or assignment.session_id
            groups[key] = max(groups.get(key, 0), assignment.duration)
        same_shared_class = bool(candidate.shared_room_group_id and candidate.shared_room_group_id in groups)
        total = sum(groups.values())
        extra = 0 if same_shared_class else candidate.duration
        if total + extra > limit:
            return ConstraintResult(
                valid=False, constraint=self.code,
                message=f"Teacher {candidate.teacher_id} would have {total + extra} hours on {candidate.day} (limit {limit})",
            )
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(self, assignments: List[ScheduleAssignment], config: dict) -> List[ConstraintResult]:
        limit = config.get("MAX_TEACHER_DAILY_HOURS", 7)
        by_teacher_day: dict = defaultdict(dict)
        for a in assignments:
            key = a.shared_room_group_id or a.session_id
            group = by_teacher_day[(a.teacher_id, a.day)]
            group[key] = max(group.get(key, 0), a.duration)
        return [
            ConstraintResult(
                valid=False, constraint=self.code,
                message=f"Teacher {tid} has {sum(groups.values())} hours on {day} (limit {limit})",
            )
            for (tid, day), groups in by_teacher_day.items() if sum(groups.values()) > limit
        ]
