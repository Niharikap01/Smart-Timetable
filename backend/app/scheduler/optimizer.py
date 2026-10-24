"""Batch-aware soft-quality scoring for generated timetables."""
from collections import defaultdict
from typing import Dict, Iterable, List

from app.scheduler.batches import batch_indices, teacher_ids
from app.scheduler.constraints.base import ScheduleAssignment


DEFAULT_WEIGHTS = {
    "S1_SECTION_IDLE_GAPS": 1.0,
    "S2_TEACHER_IDLE_GAPS": 1.0,
    "S3_COURSE_SPREAD": 1.0,
    "S4_HEAVY_STACKING": 1.0,
    "S5_DAILY_BALANCE": 1.0,
    "S6_ROOM_LOCALITY": 0.5,
    "S7_ROOM_COUNT": 0.5,
}
DEFAULT_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def compute_soft_score(
    assignments: List[ScheduleAssignment],
    weights: Dict[str, float] = None,
    config: dict = None,
) -> float:
    """Return a comparable 0–100 quality score instead of subtracting raw counts.

    The previous score subtracted every gap and repeated session directly from
    100, so any realistic schedule quickly saturated at zero. Each component
    here is normalized to 0–1 before its configured weight is applied.
    """
    if not assignments:
        return 100.0
    w = weights or DEFAULT_WEIGHTS
    config = config or {}
    penalties = {
        "S1_SECTION_IDLE_GAPS": _section_idle_gaps(assignments, config),
        "S2_TEACHER_IDLE_GAPS": _teacher_idle_gaps(assignments, config),
        "S3_COURSE_SPREAD": _course_spread_penalty(assignments),
        "S4_HEAVY_STACKING": _heavy_stacking(assignments, config),
        "S5_DAILY_BALANCE": _daily_balance(assignments, config),
        "S6_ROOM_LOCALITY": _room_locality(assignments),
        "S7_ROOM_COUNT": _room_count(assignments),
    }
    total_weight = sum(max(0.0, w.get(name, default)) for name, default in DEFAULT_WEIGHTS.items())
    if total_weight <= 0:
        return 100.0
    weighted_penalty = sum(
        max(0.0, w.get(name, default)) * min(1.0, max(0.0, penalties[name]))
        for name, default in DEFAULT_WEIGHTS.items()
    )
    return round(100.0 * (1.0 - weighted_penalty / total_weight), 1)


def _cohort_occupancy(assignments: Iterable[ScheduleAssignment]) -> Dict[tuple, set]:
    occupied: Dict[tuple, set] = defaultdict(set)
    for assignment in assignments:
        for batch in batch_indices(assignment.batch_label):
            key = (assignment.section_id, batch, assignment.day)
            occupied[key].update(range(assignment.slot_index, assignment.slot_index + assignment.duration))
    return occupied


def _day_count(assignments: List[ScheduleAssignment], config: dict) -> int:
    return max(1, len(config.get("days") or {assignment.day for assignment in assignments}))


def _registered_break_slots(config: dict, section_id: int | None = None) -> set:
    result = set()
    for slot in config.get("allowed_break_slots", ()):
        if len(slot) == 3:
            sec_id, day, index = slot
            if section_id is None or sec_id == section_id:
                result.add((day, index))
        elif len(slot) == 2:
            result.add(tuple(slot))
    return result


def _idle_gap_ratio(slots: set, day_slots: int, ignored: set = None) -> float:
    if len(slots) < 2:
        return 0.0
    ignored = ignored or set()
    start, end = min(slots), max(slots)
    internal_gaps = [index for index in range(start + 1, end) if index not in slots and index not in ignored]
    return min(1.0, len(internal_gaps) / max(1, day_slots - 1))


def _section_idle_gaps(assignments: List[ScheduleAssignment], config: dict = None) -> float:
    config = config or {}
    occupied = _cohort_occupancy(assignments)
    day_slots = int(config.get("max_slot_index", max(
        assignment.slot_index + assignment.duration - 1 for assignment in assignments
    ))) + 1
    penalties = [
        _idle_gap_ratio(slots, day_slots, _registered_break_slots(config, section_id))
        for (section_id, _batch, _day), slots in occupied.items()
    ]
    return sum(penalties) / len(penalties) if penalties else 0.0


def _teacher_idle_gaps(assignments: List[ScheduleAssignment], config: dict = None) -> float:
    config = config or {}
    by_teacher_day: Dict[tuple, set] = defaultdict(set)
    break_slots = _registered_break_slots(config)
    for assignment in assignments:
        slots = range(assignment.slot_index, assignment.slot_index + assignment.duration)
        for teacher_id in teacher_ids(assignment.teacher_id, assignment.teacher_ids):
            by_teacher_day[(teacher_id, assignment.day)].update(slots)
    day_slots = int(config.get("max_slot_index", max(
        assignment.slot_index + assignment.duration - 1 for assignment in assignments
    ))) + 1
    penalties = [
        _idle_gap_ratio(slots, day_slots, break_slots)
        for slots in by_teacher_day.values()
    ]
    return sum(penalties) / len(penalties) if penalties else 0.0


def _course_spread_penalty(assignments: List[ScheduleAssignment]) -> float:
    by_course: Dict[tuple, List[ScheduleAssignment]] = defaultdict(list)
    for assignment in assignments:
        by_course[(assignment.course_id, assignment.section_id)].append(assignment)
    penalties = []
    for course_sessions in by_course.values():
        count = len(course_sessions)
        if count > 1:
            distinct_days = len({assignment.day for assignment in course_sessions})
            penalties.append((count - distinct_days) / (count - 1))
    return sum(penalties) / len(penalties) if penalties else 0.0


def _heavy_stacking(assignments: List[ScheduleAssignment], config: dict = None) -> float:
    config = config or {}
    occupied = _cohort_occupancy(assignments)
    target = max(1, min(4, int(config.get("MAX_SECTION_DAILY_HOURS", 5))))
    total_overage = sum(max(0, len(slots) - target) for slots in occupied.values())
    normalization = max(1, len(occupied) * target)
    return min(1.0, total_overage / normalization)


def _daily_balance(assignments: List[ScheduleAssignment], config: dict = None) -> float:
    config = config or {}
    occupied = _cohort_occupancy(assignments)
    days = list(config.get("days") or DEFAULT_DAYS)
    cohorts = {(section_id, batch) for section_id, batch, _day in occupied}
    penalties = []
    for section_id, batch in cohorts:
        loads = [
            len(occupied.get((section_id, batch, day), ()))
            for day in days
        ]
        total = sum(loads)
        if total:
            average = total / len(loads)
            penalties.append(sum(abs(load - average) for load in loads) / (2.0 * total))
    return sum(penalties) / len(penalties) if penalties else 0.0


def _room_locality(assignments: List[ScheduleAssignment]) -> float:
    by_cohort_day: Dict[tuple, set] = defaultdict(set)
    by_cohort_slots: Dict[tuple, set] = defaultdict(set)
    for assignment in assignments:
        for batch in batch_indices(assignment.batch_label):
            key = (assignment.section_id, batch, assignment.day)
            by_cohort_day[key].add(assignment.room_id)
            by_cohort_slots[key].update(range(assignment.slot_index, assignment.slot_index + assignment.duration))
    penalties = [
        (len(rooms) - 1) / max(1, len(by_cohort_slots[key]) - 1)
        for key, rooms in by_cohort_day.items() if len(rooms) > 1
    ]
    return min(1.0, sum(penalties) / len(by_cohort_day)) if by_cohort_day else 0.0


def _room_count(assignments: List[ScheduleAssignment]) -> float:
    by_cohort_rooms: Dict[tuple, set] = defaultdict(set)
    by_cohort_sessions: Dict[tuple, set] = defaultdict(set)
    for assignment in assignments:
        for batch in batch_indices(assignment.batch_label):
            key = (assignment.section_id, batch)
            by_cohort_rooms[key].add(assignment.room_id)
            by_cohort_sessions[key].add(assignment.session_id)
    penalties = [
        max(0, len(rooms) - 2) / max(1, len(by_cohort_sessions[key]) - 2)
        for key, rooms in by_cohort_rooms.items()
    ]
    return min(1.0, sum(penalties) / len(penalties)) if penalties else 0.0
