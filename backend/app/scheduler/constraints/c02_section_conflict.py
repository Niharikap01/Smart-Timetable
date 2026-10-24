from typing import List
from .base import Constraint, ConstraintResult, ScheduleAssignment
from app.scheduler.batches import assignments_share_students


class SectionConflictConstraint(Constraint):
    code = "C02"
    name = "No section double-booking"

    def check(self, candidate: ScheduleAssignment, existing: List[ScheduleAssignment], config: dict) -> ConstraintResult:
        for a in existing:
            if assignments_share_students(a, candidate) and a.day == candidate.day:
                # Same link_group (both set, and equal) means these are
                # intentionally-parallel offerings (elective split / lab
                # pair) sharing the section's slot on purpose — not a clash.
                if candidate.link_group_id is not None and a.link_group_id == candidate.link_group_id:
                    continue
                cand_slots = set(range(candidate.slot_index, candidate.slot_index + candidate.duration))
                exist_slots = set(range(a.slot_index, a.slot_index + a.duration))
                if cand_slots & exist_slots:
                    return ConstraintResult(
                        valid=False, constraint=self.code,
                        message=f"Section {candidate.section_id} already has a session at {a.day} slot {a.slot_index}",
                    )
        return ConstraintResult(valid=True, constraint=self.code)

    def validate_full(self, assignments: List[ScheduleAssignment], config: dict) -> List[ConstraintResult]:
        results = []
        for i, a in enumerate(assignments):
            for b in assignments[i + 1:]:
                if assignments_share_students(a, b) and a.day == b.day:
                    if a.link_group_id is not None and a.link_group_id == b.link_group_id:
                        continue
                    a_slots = set(range(a.slot_index, a.slot_index + a.duration))
                    b_slots = set(range(b.slot_index, b.slot_index + b.duration))
                    if a_slots & b_slots:
                        results.append(ConstraintResult(
                            valid=False, constraint=self.code,
                            message=f"Section {a.section_id} double-booked on {a.day} slot {a.slot_index}",
                        ))
        return results
