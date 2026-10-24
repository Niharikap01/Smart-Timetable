from collections import defaultdict
from typing import List

from .base import Constraint, ConstraintResult, ScheduleAssignment


class NoRepeatLecturePerDayConstraint(Constraint):
    """A lecture course may meet at most once per section on any day."""

    code = "C22"
    name = "A lecture course may be scheduled only once per day per section"

    def check(
        self,
        candidate: ScheduleAssignment,
        existing: List[ScheduleAssignment],
        config: dict,
    ) -> ConstraintResult:
        is_lecture = str(getattr(candidate.course_type, "value", candidate.course_type)).lower() == "lecture"
        if not is_lecture:
            return ConstraintResult(valid=True, constraint=self.code)

        duplicate = any(
            str(getattr(assignment.course_type, "value", assignment.course_type)).lower() == "lecture"
            and assignment.course_id == candidate.course_id
            and assignment.section_id == candidate.section_id
            and assignment.day == candidate.day
            for assignment in existing
        )
        return ConstraintResult(
            valid=not duplicate,
            constraint=self.code,
            message=(
                f"Lecture course {candidate.course_id} is scheduled more than once "
                f"for section {candidate.section_id} on {candidate.day}."
                if duplicate else ""
            ),
        )

    def validate_full(
        self,
        assignments: List[ScheduleAssignment],
        config: dict,
    ) -> List[ConstraintResult]:
        occurrences = defaultdict(list)
        for assignment in assignments:
            if str(getattr(assignment.course_type, "value", assignment.course_type)).lower() != "lecture":
                continue
            occurrences[(assignment.course_id, assignment.section_id, assignment.day)].append(assignment)

        return [
            ConstraintResult(
                valid=False,
                constraint=self.code,
                message=(
                    f"Lecture course {course_id} is scheduled {len(sessions)} times "
                    f"for section {section_id} on {day}."
                ),
            )
            for (course_id, section_id, day), sessions in occurrences.items()
            if len(sessions) > 1
        ]
