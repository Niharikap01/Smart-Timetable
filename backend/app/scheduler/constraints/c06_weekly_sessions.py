from typing import List, Dict
from collections import Counter
from .base import Constraint, ConstraintResult, ScheduleAssignment


class WeeklySessionsConstraint(Constraint):
    code = "C06"
    name = "Every course must receive exactly its required weekly sessions"

    def check(self, candidate: ScheduleAssignment, existing: List[ScheduleAssignment], config: dict) -> ConstraintResult:
        # This constraint is only meaningful in full validation
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(self, assignments: List[ScheduleAssignment], config: dict) -> List[ConstraintResult]:
        results = []
        expected: Dict[int, int] = config.get("expected_sessions_per_course", {})
        actual: Dict[int, int] = Counter(a.course_id for a in assignments)
        for course_id, expected_count in expected.items():
            actual_count = actual.get(course_id, 0)
            if actual_count != expected_count:
                results.append(ConstraintResult(
                    valid=False, constraint=self.code,
                    message=f"Course {course_id}: expected {expected_count} sessions, got {actual_count}",
                ))
        return results
