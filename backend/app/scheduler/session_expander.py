"""Phase 8: Expand courses into individual scheduling sessions."""
from collections import defaultdict
from typing import Dict, List
from app.scheduler.domain import SchedulingSession


def expand_sessions(courses: list) -> List[SchedulingSession]:
    """
    Expand courses into individual sessions.
    Each course with weekly_sessions=N becomes N separate SchedulingSession objects.
    courses: list of dicts or objects with course attributes.
    """
    sessions = []
    for c in courses:
        if isinstance(c, dict):
            cid = c["id"]
            code = c.get("course_code", "")
            name = c.get("course_name", "")
            ctype = c["course_type"]
            weekly = c["weekly_sessions"]
            dur = c.get("duration", 1)
            sec_id = c["section_id"]
            tid = c["teacher_id"]
            rroom = c["required_room_type"]
            strength = c.get("section_strength", 0)
            ftype = c.get("faculty_type", "regular")
            priority = c.get("priority", 5)
            link_group = c.get("link_group")
        else:
            cid = c.id
            code = getattr(c, "course_code", "")
            name = getattr(c, "course_name", "")
            ctype = c.course_type if isinstance(c.course_type, str) else c.course_type.value
            weekly = c.weekly_sessions
            dur = c.duration
            sec_id = c.section_id
            tid = c.teacher_id
            rroom = c.required_room_type if isinstance(c.required_room_type, str) else c.required_room_type.value
            strength = getattr(c, "section_strength", 0)
            ftype = getattr(c, "faculty_type", "regular")
            if not isinstance(ftype, str):
                ftype = ftype.value
            priority = getattr(c, "priority", 5)
            link_group = getattr(c, "link_group", None)

        for sn in range(1, weekly + 1):
            # Instance sn of a grouped course is tied to instance sn of every
            # other course in the same (section, link_group) — e.g. the 1st
            # weekly occurrence of DPD, ECOM and IDPS all land on one slot
            # together, the 2nd occurrence on another shared slot, etc.
            link_group_id = f"{sec_id}:{link_group}:{sn}" if link_group else None

            sessions.append(SchedulingSession(
                session_id=f"{code}-{ctype}-S{sec_id}-{sn}",
                course_id=cid,
                section_id=sec_id,
                teacher_id=tid,
                duration=dur,
                course_type=ctype,
                required_room_type=rroom,
                section_strength=strength,
                faculty_type=ftype,
                priority=priority,
                session_number=sn,
                course_name=name,
                course_code=code,
                link_group_id=link_group_id,
            ))
    return sessions


def group_sessions(sessions: List[SchedulingSession]) -> List[List[SchedulingSession]]:
    """Collect sessions into scheduling 'units': a unit is either a single
    ungrouped session, or every session sharing the same link_group_id.
    All members of a real group are assumed to share the same section_id
    and duration (the solver places them together on one day/slot); this
    is validated at solve time, not here.
    """
    grouped: Dict[str, List[SchedulingSession]] = defaultdict(list)
    units: List[List[SchedulingSession]] = []
    for s in sessions:
        if s.link_group_id:
            grouped[s.link_group_id].append(s)
        else:
            units.append([s])
    units.extend(grouped.values())
    return units
