"""Phase 9: Generate candidate (timeslot, room) pairs with pre-filtering."""
from typing import Dict, List, Optional, Set, Tuple
from app.scheduler.domain import SchedulingSession, RoomInfo, Candidate, GroupCandidate

# A college building can contain many interchangeable lecture rooms.  Giving
# the solver all 90 DT classrooms for every one-hour lecture creates hundreds
# of thousands of equivalent choices without improving timetable quality.
# Keeping a representative, best-fitting pool removes this symmetry while
# still leaving substantially more concurrent rooms than a semester needs.
MAX_CANDIDATE_ROOMS_PER_TYPE = 16


def _best_fitting_rooms(
    session: SchedulingSession,
    rooms: List[RoomInfo],
    room_limits: Optional[Dict[str, int]] = None,
) -> List[RoomInfo]:
    matching = [
        room for room in rooms
        if room.room_type == session.required_room_type
        and room.capacity >= session.section_strength
    ]
    limit = (room_limits or {}).get(session.required_room_type, MAX_CANDIDATE_ROOMS_PER_TYPE)
    return sorted(
        matching,
        key=lambda room: (room.capacity - session.section_strength, room.room_id),
    )[:min(MAX_CANDIDATE_ROOMS_PER_TYPE, max(1, limit))]


def generate_candidates(
    session: SchedulingSession,
    rooms: List[RoomInfo],
    days: List[str],
    slots_per_day: int,
    reserved_slots: Set[Tuple[str, int]],
    recess_slots: Set[Tuple[str, int]],
    honours_slots: Set[Tuple[str, int]],
    honours_enabled: bool,
    teacher_unavailable: Set[Tuple[int, str, int]],
    room_limits: Optional[Dict[str, int]] = None,
) -> List[Candidate]:
    """Pre-filter rooms and timeslots to create valid candidates for a session."""
    # Room pre-filtering: type match + capacity
    valid_rooms = _best_fitting_rooms(session, rooms, room_limits)

    candidates = []
    for day in days:
        for start_slot in range(slots_per_day):
            end_slot = start_slot + session.duration
            if end_slot > slots_per_day:
                continue

            # Check all slots in the range
            slot_range = range(start_slot, end_slot)
            blocked = False
            for s in slot_range:
                if (day, s) in reserved_slots:
                    blocked = True
                    break
                if _is_recess_slot(recess_slots, session.section_id, day, s):
                    blocked = True
                    break
                if honours_enabled and (day, s) in honours_slots:
                    blocked = True
                    break
                if (session.teacher_id, day, s) in teacher_unavailable:
                    blocked = True
                    break
            if blocked:
                continue

            for room in valid_rooms:
                candidates.append(Candidate(
                    day=day,
                    slot_index=start_slot,
                    room_id=room.room_id,
                    room_type=room.room_type,
                    room_capacity=room.capacity,
                ))

    return candidates


def _slot_blocked(
    day: str,
    start_slot: int,
    duration: int,
    slots_per_day: int,
    reserved_slots: Set[Tuple[str, int]],
    recess_slots: Set[Tuple[str, int]],
    honours_slots: Set[Tuple[str, int]],
    honours_enabled: bool,
    section_id: int,
    teacher_id: int,
    teacher_unavailable: Set[Tuple[int, str, int]],
) -> bool:
    end_slot = start_slot + duration
    if end_slot > slots_per_day:
        return True
    for s in range(start_slot, end_slot):
        if (day, s) in reserved_slots:
            return True
        if _is_recess_slot(recess_slots, section_id, day, s):
            return True
        if honours_enabled and (day, s) in honours_slots:
            return True
        if (teacher_id, day, s) in teacher_unavailable:
            return True
    return False


def _is_recess_slot(recess_slots: Set[Tuple], section_id: int, day: str, slot_index: int) -> bool:
    """Support both global and section-specific recess registrations.

    The coordinator import stores a section-specific recess as
    ``(section_id, day, slot_index)``.  Older templates use the global
    two-item form ``(day, slot_index)``.  Candidate creation must understand
    both forms; otherwise a later validator would reject a slot that the
    solver was allowed to choose.
    """
    return (
        (section_id, day, slot_index) in recess_slots
        or (day, slot_index) in recess_slots
    )


def _assign_distinct_rooms(
    members: List[SchedulingSession],
    rooms_by_member: List[List[RoomInfo]],
    idx: int = 0,
    used: Optional[Set[int]] = None,
) -> Optional[Dict[str, RoomInfo]]:
    """Small backtracking search: pick one room per member, all rooms
    distinct (members run in parallel, at the same time), each satisfying
    that member's own room-type/capacity requirement. Group sizes are tiny
    (2-4 in practice) so brute force is fine.
    """
    if used is None:
        used = set()
    if idx == len(members):
        return {}
    for room in rooms_by_member[idx]:
        if room.room_id in used:
            continue
        used.add(room.room_id)
        rest = _assign_distinct_rooms(members, rooms_by_member, idx + 1, used)
        if rest is not None:
            rest[members[idx].session_id] = room
            return rest
        used.discard(room.room_id)
    return None


def generate_unit_candidates(
    unit: List[SchedulingSession],
    rooms: List[RoomInfo],
    days: List[str],
    slots_per_day: int,
    reserved_slots: Set[Tuple[str, int]],
    recess_slots: Set[Tuple[str, int]],
    honours_slots: Set[Tuple[str, int]],
    honours_enabled: bool,
    teacher_unavailable: Set[Tuple[int, str, int]],
    room_limits: Optional[Dict[str, int]] = None,
) -> List[GroupCandidate]:
    """Generate (day, slot) candidates for a whole unit. For a lone session
    this is equivalent to generate_candidates, just re-shaped into a
    GroupCandidate. For a real link-group, every member must fit the same
    (day, slot) and get its own distinct room.
    """
    if len(unit) == 1:
        s = unit[0]
        cands = generate_candidates(
            s, rooms, days, slots_per_day, reserved_slots, recess_slots,
            honours_slots, honours_enabled, teacher_unavailable, room_limits,
        )
        return [
            GroupCandidate(
                day=c.day, slot_index=c.slot_index,
                room_assignments={s.session_id: RoomInfo(c.room_id, "", c.room_type, c.room_capacity)},
            )
            for c in cands
        ]

    # Real group: all members must share duration (they occupy the same
    # slot range together) — if they don't, this group can never be placed.
    durations = {m.duration for m in unit}
    if len(durations) != 1:
        return []
    duration = durations.pop()

    rooms_by_member = []
    for m in unit:
        valid = _best_fitting_rooms(m, rooms, room_limits)
        rooms_by_member.append(valid)
        if not valid:
            return []

    out: List[GroupCandidate] = []
    for day in days:
        for start_slot in range(slots_per_day):
            blocked = any(
                _slot_blocked(
                    day, start_slot, duration, slots_per_day,
                    reserved_slots, recess_slots, honours_slots, honours_enabled,
                    m.section_id, m.teacher_id, teacher_unavailable,
                )
                for m in unit
            )
            if blocked:
                continue
            room_assignments = _assign_distinct_rooms(unit, rooms_by_member)
            if room_assignments is None:
                continue
            out.append(GroupCandidate(day=day, slot_index=start_slot, room_assignments=room_assignments))
    return out
