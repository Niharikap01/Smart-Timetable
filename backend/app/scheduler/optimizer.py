"""Soft constraint scoring and optional optimization."""
from typing import List, Dict
from collections import defaultdict
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


def compute_soft_score(
    assignments: List[ScheduleAssignment],
    weights: Dict[str, float] = None,
) -> float:
    w = weights or DEFAULT_WEIGHTS
    score = 100.0  # start from perfect

    score -= w.get("S1_SECTION_IDLE_GAPS", 1.0) * _section_idle_gaps(assignments)
    score -= w.get("S2_TEACHER_IDLE_GAPS", 1.0) * _teacher_idle_gaps(assignments)
    score -= w.get("S3_COURSE_SPREAD", 1.0) * _course_spread_penalty(assignments)
    score -= w.get("S4_HEAVY_STACKING", 1.0) * _heavy_stacking(assignments)
    score -= w.get("S5_DAILY_BALANCE", 1.0) * _daily_balance(assignments)
    score -= w.get("S6_ROOM_LOCALITY", 0.5) * _room_locality(assignments)
    score -= w.get("S7_ROOM_COUNT", 0.5) * _room_count(assignments)

    return max(0.0, score)


def _idle_gaps(slots_by_key: Dict) -> float:
    """Count total idle gaps across all (entity, day) groups."""
    total = 0
    for key, slots in slots_by_key.items():
        if len(slots) < 2:
            continue
        sorted_s = sorted(slots)
        for i in range(1, len(sorted_s)):
            gap = sorted_s[i] - sorted_s[i - 1] - 1
            if gap > 0:
                total += gap
    return total


def _section_idle_gaps(assignments: List[ScheduleAssignment]) -> float:
    by_sec_day: Dict = defaultdict(list)
    for a in assignments:
        for s in range(a.slot_index, a.slot_index + a.duration):
            by_sec_day[(a.section_id, a.day)].append(s)
    return _idle_gaps(by_sec_day)


def _teacher_idle_gaps(assignments: List[ScheduleAssignment]) -> float:
    by_t_day: Dict = defaultdict(list)
    for a in assignments:
        for s in range(a.slot_index, a.slot_index + a.duration):
            by_t_day[(a.teacher_id, a.day)].append(s)
    return _idle_gaps(by_t_day)


def _course_spread_penalty(assignments: List[ScheduleAssignment]) -> float:
    by_course_sec: Dict = defaultdict(set)
    for a in assignments:
        by_course_sec[(a.course_id, a.section_id)].add(a.day)
    penalty = 0
    for key, days in by_course_sec.items():
        # Ideal: sessions spread across max days. Penalty for clustering.
        course_sessions = [a for a in assignments if (a.course_id, a.section_id) == key]
        if len(course_sessions) > len(days):
            penalty += (len(course_sessions) - len(days))
    return penalty


def _heavy_stacking(assignments: List[ScheduleAssignment]) -> float:
    by_sec_day: Dict = defaultdict(int)
    for a in assignments:
        if a.course_type == "lab":
            by_sec_day[(a.section_id, a.day)] += a.duration * 2
        else:
            by_sec_day[(a.section_id, a.day)] += a.duration
    penalty = 0
    for key, load in by_sec_day.items():
        if load > 5:
            penalty += load - 5
    return penalty


def _daily_balance(assignments: List[ScheduleAssignment]) -> float:
    by_sec_day: Dict = defaultdict(int)
    sections = set()
    for a in assignments:
        by_sec_day[(a.section_id, a.day)] += a.duration
        sections.add(a.section_id)
    penalty = 0
    for sec in sections:
        loads = [by_sec_day.get((sec, d), 0) for d in
                 ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]]
        loads = [l for l in loads if l > 0]
        if loads:
            avg = sum(loads) / len(loads)
            penalty += sum(abs(l - avg) for l in loads)
    return penalty


def _room_locality(assignments: List[ScheduleAssignment]) -> float:
    by_sec_day: Dict = defaultdict(set)
    for a in assignments:
        by_sec_day[(a.section_id, a.day)].add(a.room_id)
    return sum(max(0, len(rooms) - 1) for rooms in by_sec_day.values())


def _room_count(assignments: List[ScheduleAssignment]) -> float:
    by_sec: Dict = defaultdict(set)
    for a in assignments:
        by_sec[a.section_id].add(a.room_id)
    return sum(max(0, len(rooms) - 2) for rooms in by_sec.values())
