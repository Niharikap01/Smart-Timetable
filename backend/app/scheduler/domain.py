"""Domain objects for the CSP scheduling engine."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional


@dataclass
class SchedulingSession:
    """A single session to be scheduled (expanded from a course)."""
    session_id: str
    course_id: int
    section_id: int
    teacher_id: int
    duration: int  # number of contiguous periods
    course_type: str  # lecture, lab, tutorial
    required_room_type: str  # lecture, lab
    section_strength: int
    faculty_type: str  # regular, visiting, senior, contract
    priority: int = 5
    session_number: int = 1
    course_name: str = ""
    course_code: str = ""
    # Phase 14: sessions that must share the same (day, slot_index) but get
    # their own teacher/room — e.g. DPD/ECOM/IDPS elective split, or a lab
    # pair (SE Lab batches 1/2 + DP Lab batches 3/4) running in parallel.
    # None means "not part of any group" (the common case).
    link_group_id: Optional[str] = None
    program_elective_group_id: Optional[int] = None
    program_elective_student_count: int = 0
    shared_room_group_id: Optional[str] = None
    batch_label: Optional[str] = None
    teacher_ids: Tuple[int, ...] = ()
    teacher_faculty_types: Dict[int, str] = field(default_factory=dict)


@dataclass
class RoomInfo:
    room_id: int
    room_number: str
    room_type: str
    capacity: int


@dataclass
class SlotInfo:
    day: str
    slot_index: int


@dataclass
class Candidate:
    """A (timeslot, room) pair that a session could be assigned to."""
    day: str
    slot_index: int
    room_id: int
    room_type: str
    room_capacity: int
    room_number: str = ""

    @property
    def key(self) -> Tuple[str, int, int]:
        return (self.day, self.slot_index, self.room_id)


@dataclass
class GroupCandidate:
    """A (day, slot) placement for a whole unit (one session, or a linked
    group of sessions). Every unit — even a lone session — is represented
    this way so the solver only has one code path.
    room_assignments maps session_id -> RoomInfo, one entry per member.
    """
    day: str
    slot_index: int
    room_assignments: Dict[str, "RoomInfo"]
