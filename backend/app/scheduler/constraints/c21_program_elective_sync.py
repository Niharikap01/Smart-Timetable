"""Require every section in a program-elective group to share one class."""
from collections import defaultdict
from typing import List

from .base import Constraint, ConstraintResult, ScheduleAssignment


class ProgramElectiveSynchronizationConstraint(Constraint):
    code = "C21"
    name = "Program elective sections share the same time and room"

    @staticmethod
    def _placement(assignment: ScheduleAssignment) -> tuple:
        return (
            assignment.day,
            assignment.slot_index,
            assignment.duration,
            assignment.room_id,
            assignment.teacher_id,
        )

    def check(
        self,
        candidate: ScheduleAssignment,
        existing: List[ScheduleAssignment],
        config: dict,
    ) -> ConstraintResult:
        group_id = candidate.program_elective_group_id
        if group_id is None:
            return ConstraintResult(valid=True, constraint=self.code)

        for other in existing:
            if (
                other.program_elective_group_id == group_id
                and other.session_number == candidate.session_number
                and self._placement(other) != self._placement(candidate)
            ):
                return ConstraintResult(
                    valid=False,
                    constraint=self.code,
                    message=(
                        f"Program elective group {group_id}, occurrence {candidate.session_number}, "
                        "must use the same day, time, duration, room, and teacher for every section."
                    ),
                )
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(
        self,
        assignments: List[ScheduleAssignment],
        config: dict,
    ) -> List[ConstraintResult]:
        expected_sections = config.get("program_elective_group_sections", {})
        expected_sessions = config.get("program_elective_weekly_sessions", {})
        grouped = defaultdict(lambda: defaultdict(list))
        scheduled_sections = {assignment.section_id for assignment in assignments}
        for assignment in assignments:
            if assignment.program_elective_group_id is not None:
                grouped[assignment.program_elective_group_id][
                    (assignment.section_id, assignment.session_number)
                ].append(assignment)

        results = []
        # The editor can validate schedules covering one semester while the
        # database has configured elective groups for several semesters.
        # Only expect groups that touch a section present in this schedule.
        expected_in_scope = {
            group_id
            for group_id, section_ids in expected_sections.items()
            if set(section_ids) & scheduled_sections
        }
        group_ids = set(grouped) | expected_in_scope
        for group_id in group_ids:
            group_assignments = grouped[group_id]
            sections = set(expected_sections.get(group_id, ()))
            if not sections:
                sections = {section_id for section_id, _ in group_assignments}
            weekly_count = int(expected_sessions.get(group_id, 0))
            if weekly_count <= 0:
                weekly_count = max(
                    (session_number for _section_id, session_number in group_assignments),
                    default=1,
                )

            reference_placements = {}
            for section_id in sorted(sections):
                for session_number in range(1, weekly_count + 1):
                    members = group_assignments.get((section_id, session_number), [])
                    if len(members) != 1:
                        results.append(ConstraintResult(
                            valid=False,
                            constraint=self.code,
                            message=(
                                f"Program elective group {group_id} requires exactly one row for "
                                f"section {section_id}, occurrence {session_number}; found {len(members)}."
                            ),
                        ))
                        continue

                    placement = self._placement(members[0])
                    if session_number not in reference_placements:
                        reference_placements[session_number] = (section_id, placement)
                    else:
                        reference_section, reference = reference_placements[session_number]
                        if placement != reference:
                            results.append(ConstraintResult(
                                valid=False,
                                constraint=self.code,
                                message=(
                                    f"Program elective group {group_id}, occurrence {session_number}, "
                                    f"does not match between sections {reference_section} and {section_id}."
                                ),
                            ))

            unexpected_sections = {
                section_id for section_id, _session_number in group_assignments
            } - sections
            if unexpected_sections:
                results.append(ConstraintResult(
                    valid=False,
                    constraint=self.code,
                    message=(
                        f"Program elective group {group_id} has unexpected section rows: "
                        + ", ".join(map(str, sorted(unexpected_sections)))
                        + "."
                    ),
                ))

        return results
