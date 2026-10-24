"""Base constraint interface for the scheduling engine."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Any


@dataclass
class ConstraintResult:
    valid: bool
    constraint: str
    message: str = ""
    details: Optional[Any] = None


@dataclass
class ScheduleAssignment:
    """Represents a single session assignment in the timetable."""
    session_id: str
    course_id: int
    section_id: int
    teacher_id: int
    room_id: int
    day: str
    slot_index: int
    duration: int = 1
    room_type: str = "lecture"
    room_capacity: int = 0
    section_strength: int = 0
    course_type: str = "lecture"
    required_room_type: str = "lecture"
    faculty_type: str = "regular"
    link_group_id: Optional[str] = None
    shared_room_group_id: Optional[str] = None
    required_capacity: int = 0
    program_elective_group_id: Optional[int] = None
    program_elective_student_count: int = 0
    room_number: str = ""
    session_number: int = 1
    batch_label: Optional[str] = None
    teacher_ids: List[int] = field(default_factory=list)
    teacher_faculty_types: dict[int, str] = field(default_factory=dict)


class Constraint(ABC):
    """Base class for all scheduling constraints."""

    code: str = ""
    name: str = ""
    severity: str = "HARD"  # HARD | SOFT | DISABLED

    @abstractmethod
    def check(
        self,
        candidate: ScheduleAssignment,
        existing: List[ScheduleAssignment],
        config: dict,
    ) -> ConstraintResult:
        """Check if a candidate assignment is valid given existing assignments."""
        ...

    @abstractmethod
    def validate_full(
        self,
        assignments: List[ScheduleAssignment],
        config: dict,
    ) -> List[ConstraintResult]:
        """Validate all assignments for this constraint (post-generation)."""
        ...

    def is_enabled(self, config: dict) -> bool:
        mode = config.get(f"{self.code}_MODE", self.severity)
        return mode != "DISABLED"

    def is_hard(self, config: dict) -> bool:
        mode = config.get(f"{self.code}_MODE", self.severity)
        return mode == "HARD"
