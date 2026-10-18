"""Independently testable conflict checker for timetable validation."""
from typing import List
from app.scheduler.constraints import (
    ALL_CONSTRAINTS, ConstraintResult, ScheduleAssignment, get_hard_constraints,
)


def check_candidate(
    candidate: ScheduleAssignment,
    existing: List[ScheduleAssignment],
    config: dict,
) -> List[ConstraintResult]:
    """Check a candidate assignment against all hard constraints. Returns list of violations."""
    violations = []
    for c in get_hard_constraints(config):
        result = c.check(candidate, existing, config)
        if not result.valid:
            violations.append(result)
    return violations


def validate_schedule(
    assignments: List[ScheduleAssignment],
    config: dict,
) -> List[ConstraintResult]:
    """Full post-generation validation of entire schedule."""
    violations = []
    for c in get_hard_constraints(config):
        violations.extend(c.validate_full(assignments, config))
    return violations


def is_candidate_valid(
    candidate: ScheduleAssignment,
    existing: List[ScheduleAssignment],
    config: dict,
) -> bool:
    """Quick boolean check for CSP solver."""
    for c in get_hard_constraints(config):
        result = c.check(candidate, existing, config)
        if not result.valid:
            return False
    return True
