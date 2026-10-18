"""Phase 10: Bitmask-based O(1) occupancy tracking."""
from __future__ import annotations
from collections import defaultdict
from typing import Dict, Tuple


class OccupancyTracker:
    """Tracks occupancy using integer bitmasks for O(1) conflict detection.
    
    Each (entity, day) maps to an integer where bit i represents slot i.
    """

    def __init__(self) -> None:
        self._teacher: Dict[Tuple[int, str], int] = defaultdict(int)
        self._section: Dict[Tuple[int, str], int] = defaultdict(int)
        self._room: Dict[Tuple[int, str], int] = defaultdict(int)

    def _slot_mask(self, slot_index: int, duration: int) -> int:
        return ((1 << duration) - 1) << slot_index

    def has_teacher_conflict(self, teacher_id: int, day: str, slot_index: int, duration: int) -> bool:
        mask = self._slot_mask(slot_index, duration)
        return bool(self._teacher[(teacher_id, day)] & mask)

    def has_section_conflict(self, section_id: int, day: str, slot_index: int, duration: int) -> bool:
        mask = self._slot_mask(slot_index, duration)
        return bool(self._section[(section_id, day)] & mask)

    def has_room_conflict(self, room_id: int, day: str, slot_index: int, duration: int) -> bool:
        mask = self._slot_mask(slot_index, duration)
        return bool(self._room[(room_id, day)] & mask)

    def has_any_conflict(self, teacher_id: int, section_id: int, room_id: int,
                         day: str, slot_index: int, duration: int) -> bool:
        mask = self._slot_mask(slot_index, duration)
        return bool(
            (self._teacher[(teacher_id, day)] & mask)
            | (self._section[(section_id, day)] & mask)
            | (self._room[(room_id, day)] & mask)
        )

    def assign(self, teacher_id: int, section_id: int, room_id: int,
               day: str, slot_index: int, duration: int) -> None:
        mask = self._slot_mask(slot_index, duration)
        self._teacher[(teacher_id, day)] |= mask
        self._section[(section_id, day)] |= mask
        self._room[(room_id, day)] |= mask

    def unassign(self, teacher_id: int, section_id: int, room_id: int,
                 day: str, slot_index: int, duration: int) -> None:
        mask = self._slot_mask(slot_index, duration)
        self._teacher[(teacher_id, day)] &= ~mask
        self._section[(section_id, day)] &= ~mask
        self._room[(room_id, day)] &= ~mask

    def teacher_load_on_day(self, teacher_id: int, day: str) -> int:
        return bin(self._teacher[(teacher_id, day)]).count("1")

    def section_load_on_day(self, section_id: int, day: str) -> int:
        return bin(self._section[(section_id, day)]).count("1")

    def has_unit_conflict(
        self, members: list, section_id: int, day: str, slot_index: int, duration: int,
    ) -> bool:
        """Group-aware check: each member's own teacher+room must be free,
        but the section is checked/occupied ONCE for the whole unit — members
        of the same group are *meant* to share the section's slot.
        `members` is a list of (teacher_id, room_id) tuples.
        """
        mask = self._slot_mask(slot_index, duration)
        if self._section[(section_id, day)] & mask:
            return True
        for teacher_id, room_id in members:
            if self._teacher[(teacher_id, day)] & mask:
                return True
            if self._room[(room_id, day)] & mask:
                return True
        return False

    def assign_unit(
        self, members: list, section_id: int, day: str, slot_index: int, duration: int,
    ) -> None:
        mask = self._slot_mask(slot_index, duration)
        self._section[(section_id, day)] |= mask
        for teacher_id, room_id in members:
            self._teacher[(teacher_id, day)] |= mask
            self._room[(room_id, day)] |= mask

    def unassign_unit(
        self, members: list, section_id: int, day: str, slot_index: int, duration: int,
    ) -> None:
        mask = self._slot_mask(slot_index, duration)
        self._section[(section_id, day)] &= ~mask
        for teacher_id, room_id in members:
            self._teacher[(teacher_id, day)] &= ~mask
            self._room[(room_id, day)] &= ~mask

    def section_consecutive_max(self, section_id: int, day: str) -> int:
        bits = self._section[(section_id, day)]
        if not bits:
            return 0
        max_run = 0
        run = 0
        pos = 0
        while bits >> pos:
            if (bits >> pos) & 1:
                run += 1
                max_run = max(max_run, run)
            else:
                run = 0
            pos += 1
        return max_run
