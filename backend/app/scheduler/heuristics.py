"""Phase 11: MRV + degree heuristic for variable ordering."""
from typing import List, Dict
from app.scheduler.domain import SchedulingSession, Candidate, GroupCandidate


DAY_ORDER = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
}


def unit_key(unit: List[SchedulingSession]) -> str:
    """Stable key for a scheduling unit (single session or link-group)."""
    return unit[0].link_group_id or unit[0].session_id


def select_next_unit(
    unassigned: List[List[SchedulingSession]],
    domains: Dict[str, List[GroupCandidate]],
) -> List[SchedulingSession]:
    """MRV over units: pick the unit with fewest remaining GroupCandidates.
    Tie-break by highest priority among the unit's members (more constrained
    courses, e.g. labs, go first).
    """
    best = None
    best_size = float("inf")
    best_priority = -1

    for unit in unassigned:
        domain = domains.get(unit_key(unit), [])
        size = len(domain)
        prio = max(m.priority for m in unit)
        if size < best_size or (size == best_size and prio > best_priority):
            best = unit
            best_size = size
            best_priority = prio

    return best


def order_group_candidates(candidates: List[GroupCandidate]) -> List[GroupCandidate]:
    """Put the static domain in calendar order.

    The solver applies a second, *dynamic* academic-balance ordering while it
    schedules.  This fallback keeps the result stable when candidates tie and
    avoids the accidental alphabetical order (Friday, Monday, Saturday, ...)
    that previously encouraged badly clustered weeks.
    """
    return sorted(candidates, key=lambda c: (DAY_ORDER.get(c.day, 99), c.slot_index))


def select_next_session(
    unassigned: List[SchedulingSession],
    domains: Dict[str, List[Candidate]],
) -> SchedulingSession:
    """MRV: pick session with fewest remaining candidates. Tie-break by degree (priority)."""
    best = None
    best_size = float("inf")
    best_priority = -1

    for session in unassigned:
        domain = domains.get(session.session_id, [])
        size = len(domain)
        # Higher priority value = more constrained (tie-break)
        prio = session.priority
        if size < best_size or (size == best_size and prio > best_priority):
            best = session
            best_size = size
            best_priority = prio

    return best


def order_candidates(
    candidates: List[Candidate],
    session: SchedulingSession,
    domains: Dict[str, List[Candidate]],
    unassigned: List[SchedulingSession],
) -> List[Candidate]:
    """LCV: order candidates by least constraining value (simple heuristic)."""
    # For efficiency, just sort by day spread + room_capacity closeness
    # A full LCV would count remaining domain sizes for each candidate
    return sorted(candidates, key=lambda c: (c.day, c.slot_index, c.room_capacity - session.section_strength))
