"""Coordinator edit layer: validate and apply single-session moves/swaps on a published timetable.

Every edit is checked against the SAME 20 hard constraints the solver uses,
via the shared validate_schedule() checker. Edits are rejected with precise
codes/messages so the UI can show a preview before committing.
"""
from __future__ import annotations

from datetime import datetime, time
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Course, Room, Section, Teacher, Timeslot, TeacherAvailability, ReservedSlot
from app.models.timetable import GeneratedSchedule, TimetableSession, ScheduleStatus
from app.models.timeslot import DayOfWeek
from app.scheduler.constraints.base import ScheduleAssignment
from app.scheduler.conflict_checker import validate_schedule
from app.services.constraint_profiles import get_current_profile


def _constraint_config(db: Session) -> Tuple[dict, List[str], int]:
    timeslots = db.query(Timeslot).all()
    reserved = db.query(ReservedSlot).all()
    avail = db.query(TeacherAvailability).all()

    constraint_profile = get_current_profile(db)
    constraint_values = dict(constraint_profile.config)

    slots_per_day = 8
    if timeslots:
        max_slot = max(ts.slot_index for ts in timeslots)
        slots_per_day = max_slot + 1

    days_set = set()
    for ts in timeslots:
        day_val = ts.day.value if hasattr(ts.day, "value") else ts.day
        days_set.add(day_val)
    days = sorted(days_set, key=lambda d: ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"].index(d)) if days_set else ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]

    teacher_unavailable = set()
    for a in avail:
        if not a.is_available:
            day_val = a.day.value if hasattr(a.day, "value") else a.day
            teacher_unavailable.add((a.teacher_id, day_val, a.slot_index))

    def is_break_reason(reason):
        normalized = (reason or "").strip().upper()
        return "RECESS" in normalized or "LUNCH" in normalized

    sections_all = db.query(Section).all()
    reserved_slots = set()
    recess_slots = set()
    allowed_break_slots = set()
    honours_slots = set()
    for r in reserved:
        day_val = r.day.value if hasattr(r.day, "value") else r.day
        slot = (day_val, r.slot_index)
        is_break = is_break_reason(r.reason)
        if r.section_id is not None and is_break:
            recess_slots.add((r.section_id, day_val, r.slot_index))
            allowed_break_slots.add((r.section_id, day_val, r.slot_index))
        elif is_break:
            section_breaks = {(section.id, day_val, r.slot_index) for section in sections_all}
            recess_slots.update(section_breaks)
            allowed_break_slots.update(section_breaks)
        else:
            reserved_slots.add(slot)
    for ts in timeslots:
        if ts.is_reserved:
            day_val = ts.day.value if hasattr(ts.day, "value") else ts.day
            slot = (day_val, ts.slot_index)
            if is_break_reason(ts.reservation_reason):
                section_breaks = {(section.id, day_val, ts.slot_index) for section in sections_all}
                recess_slots.update(section_breaks)
                allowed_break_slots.update(section_breaks)
            else:
                reserved_slots.add(slot)

    rooms_db = db.query(Room).filter(Room.active == True).all()
    valid_room_ids = {r.id for r in rooms_db if r.active}

    latest_start_time = time.fromisoformat(
        constraint_values.get("LATEST_SECTION_START_TIME", settings.MAX_SECTION_START_TIME)
    )
    latest_start_slot_by_day: Dict[str, int] = {}
    for ts in timeslots:
        start = ts.start_time
        if isinstance(start, str):
            try:
                hour, minute = (int(part) for part in start.split(":")[:2])
                start = time(hour, minute)
            except (TypeError, ValueError):
                continue
        if start <= latest_start_time:
            day_val = ts.day.value if hasattr(ts.day, "value") else ts.day
            latest_start_slot_by_day[day_val] = max(latest_start_slot_by_day.get(day_val, -1), ts.slot_index)
    for day in days:
        latest_start_slot_by_day.setdefault(day, -1)

    config = {
        "reserved_slots": reserved_slots,
        "recess_slots": recess_slots,
        "allowed_break_slots": allowed_break_slots,
        "honours_slots": honours_slots,
        "HONOURS_RESERVED_ENABLED": settings.HONOURS_RESERVED_ENABLED,
        "teacher_unavailable": teacher_unavailable,
        "MAX_CONSECUTIVE_PERIODS": constraint_values.get("MAX_CONSECUTIVE_PERIODS", settings.MAX_CONSECUTIVE_PERIODS),
        "MAX_SECTION_DAILY_HOURS": constraint_values.get("MAX_SECTION_DAILY_HOURS", settings.MAX_SECTION_DAILY_HOURS),
        "MAX_LECTURE_PERIODS_PER_DAY": constraint_values.get("MAX_LECTURE_PERIODS_PER_DAY", settings.MAX_LECTURE_PERIODS_PER_DAY),
        "MAX_TEACHER_DAILY_HOURS": constraint_values.get("MAX_TEACHER_DAILY_HOURS", settings.MAX_TEACHER_DAILY_HOURS),
        "MAX_SECTION_START_SLOT": settings.MAX_SECTION_START_SLOT,
        "MAX_SECTION_START_SLOT_BY_DAY": latest_start_slot_by_day,
        "max_slot_index": slots_per_day - 1,
        "SENIOR_FACULTY_CONSTRAINT_MODE": settings.SENIOR_FACULTY_CONSTRAINT_MODE,
        "expected_sessions_per_course": {},  # filled per-edit when needed
        "valid_room_ids": valid_room_ids,
    }
    return config, days, slots_per_day


def _assignments_for_schedule(db: Session, schedule: GeneratedSchedule) -> Tuple[List[ScheduleAssignment], Dict[int, TimetableSession]]:
    sessions: List[TimetableSession] = db.query(TimetableSession).filter(
        TimetableSession.generated_schedule_id == schedule.id
    ).all()
    course_ids = {s.course_id for s in sessions}
    courses = {c.id: c for c in db.query(Course).filter(Course.id.in_(course_ids)).all()} if course_ids else {}
    section_ids = {s.section_id for s in sessions}
    sections = {sec.id: sec for sec in db.query(Section).filter(Section.id.in_(section_ids)).all()} if section_ids else {}
    teacher_ids = {s.teacher_id for s in sessions}
    teachers = {t.id: t for t in db.query(Teacher).filter(Teacher.id.in_(teacher_ids)).all()} if teacher_ids else {}
    room_ids = {s.room_id for s in sessions}
    rooms = {r.id: r for r in db.query(Room).filter(Room.id.in_(room_ids)).all()} if room_ids else {}
    timeslots = {ts.id: ts for ts in db.query(Timeslot).all()}

    assignments: List[ScheduleAssignment] = []
    session_map: Dict[int, TimetableSession] = {}
    for s in sessions:
        course = courses.get(s.course_id)
        sec = sections.get(s.section_id)
        tch = teachers.get(s.teacher_id)
        room = rooms.get(s.room_id)
        ts = timeslots.get(s.timeslot_id)
        # Derive slot_index from timeslot when possible (authoritative), else from day/slot mapping
        slot_index = ts.slot_index if ts is not None else 0
        # Fallback if ts missing: try to infer from start_time hour offset 8
        if ts is None and s.start_time is not None:
            try:
                st = s.start_time
                hour = st.hour if hasattr(st, "hour") else int(str(st).split(":")[0])
                slot_index = max(0, hour - 8)
            except Exception:
                slot_index = 0
        day_val = s.day.value if hasattr(s.day, "value") else s.day
        duration = course.duration if course is not None else 1
        course_type = (course.course_type.value if course and hasattr(course.course_type, "value") else getattr(course, "course_type", "lecture")) if course else "lecture"
        required_room_type = (course.required_room_type.value if course and hasattr(course.required_room_type, "value") else getattr(course, "required_room_type", "lecture")) if course else "lecture"
        faculty_type = (tch.faculty_type.value if tch and hasattr(tch.faculty_type, "value") else getattr(tch, "faculty_type", "regular")) if tch else "regular"
        room_type = (room.room_type.value if room and hasattr(room.room_type, "value") else getattr(room, "room_type", "lecture")) if room else "lecture"
        room_capacity = room.capacity if room else 0
        section_strength = sec.strength if sec else 0
        assignments.append(ScheduleAssignment(
            session_id=str(s.id),
            course_id=s.course_id,
            section_id=s.section_id,
            teacher_id=s.teacher_id,
            room_id=s.room_id,
            day=day_val,
            slot_index=slot_index,
            duration=int(duration),
            room_type=str(room_type),
            room_capacity=int(room_capacity or 0),
            section_strength=int(section_strength or 0),
            course_type=str(course_type),
            required_room_type=str(required_room_type),
            faculty_type=str(faculty_type),
            link_group_id=getattr(course, "link_group", None) if course else None,
        ))
        session_map[s.id] = s
    return assignments, session_map


def latest_valid_schedule(db: Session) -> Optional[GeneratedSchedule]:
    return db.query(GeneratedSchedule).filter(
        GeneratedSchedule.status == ScheduleStatus.VALID
    ).order_by(GeneratedSchedule.generated_at.desc()).first()


def _find_timeslot(db: Session, day: str, slot_index: int) -> Optional[Timeslot]:
    # Timeslot is mastered per (day, slot_index). Prefer exact match; fallback to any matching slot_index.
    ts = db.query(Timeslot).filter(Timeslot.day == day, Timeslot.slot_index == slot_index).first()
    if ts:
        return ts
    return db.query(Timeslot).filter(Timeslot.slot_index == slot_index).first()


def preview_move(
    db: Session, schedule: GeneratedSchedule, session_id: int, new_day: str, new_slot_index: int, new_room_id: Optional[int]
) -> dict:
    """Return {valid, violations:[{constraint,message}]} without writing."""
    assignments, session_map = _assignments_for_schedule(db, schedule)
    if session_id not in session_map:
        return {"valid": False, "violations": [{"constraint": "EXISTS", "message": f"Session {session_id} not found in schedule {schedule.id}."}]}
    target_session = session_map[session_id]
    config, days, slots_per_day = _constraint_config(db)

    if new_day not in days:
        return {"valid": False, "violations": [{"constraint": "C07", "message": f"Unknown day '{new_day}'. Available: {', '.join(days)}"}]}
    if not (0 <= new_slot_index <= slots_per_day - 1):
        return {"valid": False, "violations": [{"constraint": "C07", "message": f"Slot {new_slot_index} out of range 0–{slots_per_day-1}."}]}

    # Duration comes from course; multi-period lab must stay contiguous and within day.
    course = db.query(Course).get(target_session.course_id)
    duration = int(course.duration) if course else 1
    if new_slot_index + duration > slots_per_day:
        return {"valid": False, "violations": [{"constraint": "C07", "message": f"Lab duration {duration} does not fit starting at slot {new_slot_index} (max {slots_per_day})."}]}

    # Room handling: if caller passes room, validate; otherwise keep current if still compatible, else pick best-fit.
    rooms = db.query(Room).filter(Room.active == True).all()
    room_by_id = {r.id: r for r in rooms}
    if new_room_id is not None:
        room = room_by_id.get(new_room_id)
        if not room:
            return {"valid": False, "violations": [{"constraint": "C16", "message": f"Room {new_room_id} not found."}]}
        if not room.active:
            return {"valid": False, "violations": [{"constraint": "C16", "message": f"Room {room.room_number} is inactive."}]}
    else:
        # keep
        room = room_by_id.get(target_session.room_id)

    # Linked groups: if this course has a link_group, moving one instance should move its whole bundle
    # (e.g. elective cluster). For a preview we validate the full mutated schedule.
    link_group = getattr(course, "link_group", None)
    section_id = target_session.section_id
    # Find sibling session ids that share (section_id, link_group) and same weekly occurrence number?
    # Simplest: if link_group is set, treat the bundle as all sessions in this schedule with same link_group and section_id
    # that currently share the same (day, slot_index). Move them together.
    bundle_ids = [session_id]
    if link_group:
        cur_day = target_session.day.value if hasattr(target_session.day, "value") else target_session.day
        cur_ts = db.query(Timeslot).get(target_session.timeslot_id)
        cur_slot = cur_ts.slot_index if cur_ts else None
        # Find schedule siblings with same link_group
        siblings = [s for s in session_map.values() if s.section_id == section_id and (db.query(Course).get(s.course_id).link_group == link_group if db.query(Course).get(s.course_id) else False)]
        # Narrow to those sharing current day/slot (same occurrence)
        same_slot = []
        for sib in siblings:
            sd = sib.day.value if hasattr(sib.day, "value") else sib.day
            st = db.query(Timeslot).get(sib.timeslot_id)
            ss = st.slot_index if st else None
            if sd == cur_day and ss == cur_slot:
                same_slot.append(sib.id)
        if same_slot:
            bundle_ids = same_slot

    # Build mutated assignments: shift every bundle member to new_day/new_slot (same room unless overridden)
    bundle_set = set(bundle_ids)
    mutated: List[ScheduleAssignment] = []
    for a in assignments:
        # assignments are ordered same as session_map keys; correlate via session_id string == db id
        try:
            sid = int(a.session_id)
        except ValueError:
            sid = None
        if sid in bundle_set:
            # override day/slot/room
            # For distinct-room bundles (lab parallel), keep each member's original room unless caller forced one room (then reject)
            if len(bundle_ids) > 1 and new_room_id is not None:
                return {"valid": False, "violations": [{"constraint": "C03", "message": "A linked group needs distinct rooms — move without forcing a single room."}]}
            # pick room per member
            member_room_id = new_room_id if (new_room_id is not None and len(bundle_ids) == 1) else a.room_id
            member_room = room_by_id.get(member_room_id, room)
            mutated.append(ScheduleAssignment(
                session_id=a.session_id,
                course_id=a.course_id,
                section_id=a.section_id,
                teacher_id=a.teacher_id,
                room_id=member_room.id if member_room else a.room_id,
                day=new_day,
                slot_index=new_slot_index,
                duration=a.duration,
                room_type=(member_room.room_type.value if member_room and hasattr(member_room.room_type, "value") else str(getattr(member_room, "room_type", a.room_type))) if member_room else a.room_type,
                room_capacity=int(member_room.capacity) if member_room else a.room_capacity,
                section_strength=a.section_strength,
                course_type=a.course_type,
                required_room_type=a.required_room_type,
                faculty_type=a.faculty_type,
                link_group_id=a.link_group_id,
            ))
        else:
            mutated.append(a)

    violations = validate_schedule(mutated, config)
    # Also surface any early room-type/capacity issues that validate_schedule consolidates into C04/C05/C16
    result_violations = [{"constraint": v.constraint, "message": v.message} for v in violations]
    return {"valid": len(result_violations) == 0, "violations": result_violations, "bundle_ids": bundle_ids}


def apply_move(
    db: Session, schedule: GeneratedSchedule, session_id: int, new_day: str, new_slot_index: int, new_room_id: Optional[int]
) -> dict:
    preview = preview_move(db, schedule, session_id, new_day, new_slot_index, new_room_id)
    if not preview["valid"]:
        return preview
    bundle_ids = preview.get("bundle_ids", [session_id])
    ts = _find_timeslot(db, new_day, new_slot_index)
    if not ts:
        return {"valid": False, "violations": [{"constraint": "C07", "message": f"No Timeslot for {new_day} slot {new_slot_index}. Create it on the Timeslots page first."}]}
    # Persist each bundle member
    for sid in bundle_ids:
        sess = db.query(TimetableSession).get(sid)
        if not sess:
            continue
        sess.day = new_day  # type: ignore[assignment]
        sess.timeslot_id = ts.id
        sess.start_time = ts.start_time
        sess.end_time = ts.end_time
        if new_room_id is not None and len(bundle_ids) == 1:
            sess.room_id = new_room_id
        # For linked lab bundle each member keeps its own room (already validated distinct)
    db.commit()
    refresh_vacancy_cache(db, schedule)
    return {"valid": True, "violations": [], "bundle_ids": bundle_ids, "timeslot_id": ts.id}


def preview_swap(db: Session, schedule: GeneratedSchedule, a_id: int, b_id: int) -> dict:
    assignments, session_map = _assignments_for_schedule(db, schedule)
    if a_id not in session_map or b_id not in session_map:
        return {"valid": False, "violations": [{"constraint": "EXISTS", "message": "One or both session ids not found in this schedule."}]}
    if a_id == b_id:
        return {"valid": False, "violations": [{"constraint": "EXISTS", "message": "Pick two different sessions to swap."}]}
    config, _, _ = _constraint_config(db)
    a_row = session_map[a_id]
    b_row = session_map[b_id]
    a_ts = db.query(Timeslot).get(a_row.timeslot_id)
    b_ts = db.query(Timeslot).get(b_row.timeslot_id)
    a_day = a_row.day.value if hasattr(a_row.day, "value") else a_row.day
    b_day = b_row.day.value if hasattr(b_row.day, "value") else b_row.day
    a_slot = a_ts.slot_index if a_ts else 0
    b_slot = b_ts.slot_index if b_ts else 0
    # Swap by rebuilding mutated assignments (keep rooms with their session, not with the slot)
    mutated: List[ScheduleAssignment] = []
    for ass in assignments:
        try:
            sid = int(ass.session_id)
        except ValueError:
            mutated.append(ass)
            continue
        if sid == a_id:
            mutated.append(ScheduleAssignment(**{**ass.__dict__, "day": b_day, "slot_index": b_slot}))
        elif sid == b_id:
            mutated.append(ScheduleAssignment(**{**ass.__dict__, "day": a_day, "slot_index": a_slot}))
        else:
            mutated.append(ass)
    violations = validate_schedule(mutated, config)
    # Duration-fit guard: a 2-period lab swapped onto a slot that overflows the day is caught by C07 but also surface early
    return {"valid": len(violations) == 0, "violations": [{"constraint": v.constraint, "message": v.message} for v in violations]}


def apply_swap(db: Session, schedule: GeneratedSchedule, a_id: int, b_id: int) -> dict:
    preview = preview_swap(db, schedule, a_id, b_id)
    if not preview["valid"]:
        return preview
    a_row = db.query(TimetableSession).get(a_id)
    b_row = db.query(TimetableSession).get(b_id)
    if not a_row or not b_row:
        return preview
    # swap timeslot/day/start/end, keep each session's own room (so room moves with class, no double-book surprise)
    a_day, a_ts_id, a_start, a_end = a_row.day, a_row.timeslot_id, a_row.start_time, a_row.end_time
    b_day, b_ts_id, b_start, b_end = b_row.day, b_row.timeslot_id, b_row.start_time, b_row.end_time
    a_row.day, a_row.timeslot_id, a_row.start_time, a_row.end_time = b_day, b_ts_id, b_start, b_end
    b_row.day, b_row.timeslot_id, b_row.start_time, b_row.end_time = a_day, a_ts_id, a_start, a_end
    db.commit()
    refresh_vacancy_cache(db, schedule)
    return {"valid": True, "violations": []}


def refresh_vacancy_cache(db: Session, schedule: GeneratedSchedule) -> None:
    """Rebuild the in-memory vacancy cache from the current schedule."""
    try:
        from app.vacancy.cache import occupancy_cache
        from app.models import Room as RoomModel
        rooms = db.query(RoomModel).filter(RoomModel.active == True).all()
        occupancy_cache.load_rooms([
            {"room_id": r.id, "room_number": r.room_number, "room_type": r.room_type.value if hasattr(r.room_type, "value") else r.room_type, "capacity": r.capacity}
            for r in rooms
        ])
        sessions = db.query(TimetableSession).filter(TimetableSession.generated_schedule_id == schedule.id).all()
        # Join course/section/teacher names for cache display
        course_map = {c.id: c for c in db.query(Course).all()}
        section_map = {s.id: s for s in db.query(Section).all()}
        teacher_map = {t.id: t for t in db.query(Teacher).all()}
        cache_rows = []
        for s in sessions:
            c = course_map.get(s.course_id)
            sec = section_map.get(s.section_id)
            tch = teacher_map.get(s.teacher_id)
            day_val = s.day.value if hasattr(s.day, "value") else s.day
            st = s.start_time
            en = s.end_time
            # normalize to string HH:MM for cache comparison
            def _t(v):
                if hasattr(v, "strftime"):
                    return v.strftime("%H:%M")
                return str(v)[:5]
            cache_rows.append({
                "room_id": s.room_id,
                "day": day_val,
                "start_time": _t(st),
                "end_time": _t(en),
                "course_name": getattr(c, "course_name", ""),
                "section_name": getattr(sec, "name", ""),
                "teacher_name": getattr(tch, "name", ""),
            })
        # Patch cache to compare against string times (cache expects time objects, but also handles strings via duck-typing if we convert)
        # Convert to time objects for cache's update_current comparison
        from datetime import time as dtime
        for row in cache_rows:
            for k in ("start_time", "end_time"):
                v = row[k]
                if isinstance(v, str):
                    try:
                        h, m = (int(x) for x in v.split(":")[:2])
                        row[k] = dtime(h, m)
                    except Exception:
                        row[k] = dtime(9, 0)
        occupancy_cache.load_schedule(cache_rows)
        occupancy_cache.update_current(datetime.now())
        # broadcast if anyone listening (best-effort)
        try:
            from app.websocket.manager import ws_manager
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(ws_manager.broadcast({"event": "SCHEDULE_UPDATED", "schedule_id": schedule.id}))
            except RuntimeError:
                pass
        except Exception:
            pass
    except Exception:
        # never fail the edit because vacancy refresh had an issue
        pass
