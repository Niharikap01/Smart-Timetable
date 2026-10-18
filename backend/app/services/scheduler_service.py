"""Service layer connecting the CSP solver to the database and API."""
import logging
from datetime import datetime, time
from typing import Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    Course, Section, Teacher, Room, Timeslot, TeacherAvailability,
    ReservedSlot, GeneratedSchedule, TimetableSession, DayOfWeek,
)
from app.models.timetable import ScheduleStatus
from app.scheduler.csp_solver import CSPSolver, SolverConfig
from app.scheduler.cp_sat_solver import CPSATSolver
from app.scheduler.session_expander import expand_sessions
from app.scheduler.domain import RoomInfo
from app.scheduler.optimizer import compute_soft_score
from app.services.constraint_profiles import get_current_profile
from app.vacancy.cache import occupancy_cache
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)


def run_scheduler(
    db: Session, timeout: int = 30, enable_optimization: bool = False,
    semester: Optional[int] = None,
) -> dict:
    """Load one selected semester (or all), run CSP, and persist results."""
    # Load data
    section_query = db.query(Section).filter(Section.active == True)
    course_query = db.query(Course).filter(Course.active == True)
    if semester is not None:
        section_query = section_query.filter(Section.semester == semester)
        course_query = course_query.join(Section).filter(Section.semester == semester)
    sections = section_query.all()
    courses = course_query.all()
    teachers = db.query(Teacher).filter(Teacher.active == True).all()
    rooms_db = db.query(Room).filter(Room.active == True).all()
    timeslots = db.query(Timeslot).all()
    avail = db.query(TeacherAvailability).all()
    reserved = db.query(ReservedSlot).all()

    if not courses:
        return {"status": "FAILED", "message": "No active courses found"}
    if not rooms_db:
        return {"status": "FAILED", "message": "No active rooms found"}

    scope_label = f"Semester {semester}" if semester is not None else "the full department"
    # Scheduling is valid only when every CSE section in the selected scope
    # has verified teaching data. The coordinator workbook can be completed
    # semester by semester without allowing incomplete records to leak in.
    semester_sections = [s for s in sections if s.program.upper() == "CSE"]
    if not semester_sections:
        return {"status": "FAILED", "message": f"No active CSE sections found for {scope_label}"}
    course_section_ids = {c.section_id for c in courses}
    missing_sections = [s.name for s in semester_sections if s.id not in course_section_ids]
    if missing_sections:
        return {
            "status": "FAILED",
            "message": f"Cannot generate {scope_label} timetable. Missing course/faculty assignment data for: " + ", ".join(missing_sections),
        }
    unknown_strengths = [s.name for s in semester_sections if s.strength <= 0]
    if unknown_strengths:
        return {
            "status": "FAILED",
            "message": f"Cannot generate {scope_label} timetable. Section strengths are required for: " + ", ".join(unknown_strengths),
        }
    if any(room.capacity <= 0 for room in rooms_db):
        return {
            "status": "FAILED",
            "message": "Cannot generate timetable. Official room capacities must be entered before scheduling.",
        }

    section_map = {s.id: s for s in sections}
    teacher_map = {t.id: t for t in teachers}

    # Enrich courses with section_strength and faculty_type
    enriched = []
    for c in courses:
        sec = section_map.get(c.section_id)
        tch = teacher_map.get(c.teacher_id)
        if not sec or not tch:
            return {"status": "FAILED", "message": f"Course {c.course_code} has a missing section or teacher assignment"}
        enriched.append({
            "id": c.id,
            "course_code": c.course_code,
            "course_name": c.course_name,
            "course_type": c.course_type.value if hasattr(c.course_type, 'value') else c.course_type,
            "weekly_sessions": c.weekly_sessions,
            "duration": c.duration,
            "section_id": c.section_id,
            "teacher_id": c.teacher_id,
            "required_room_type": c.required_room_type.value if hasattr(c.required_room_type, 'value') else c.required_room_type,
            "section_strength": sec.strength if sec else 0,
            "faculty_type": tch.faculty_type.value if tch and hasattr(tch.faculty_type, 'value') else "regular",
            "priority": c.priority,
            "link_group": c.link_group,
        })

    sessions = expand_sessions(enriched)
    room_infos = [
        RoomInfo(r.id, r.room_number, r.room_type.value if hasattr(r.room_type, 'value') else r.room_type, r.capacity)
        for r in rooms_db
    ]

    # Build constraint config
    teacher_unavailable = set()
    for a in avail:
        if not a.is_available:
            day_val = a.day.value if hasattr(a.day, 'value') else a.day
            teacher_unavailable.add((a.teacher_id, day_val, a.slot_index))

    # A NULL section_id is global.  A recess/lunch row with a section_id
    # blocks only that section; global recess/lunch rows are expanded to every
    # section.  Those same slots are the only gaps allowed in a student's day.
    reserved_slots = set()
    recess_slots = set()
    allowed_break_slots = set()
    # Accept the label from the current A2 demo data ("LUNCH BREAK (Demo)")
    # as well as the clean labels used by imports and future official data.
    def is_break_reason(reason):
        normalized = (reason or "").strip().upper()
        return "RECESS" in normalized or "LUNCH" in normalized
    for r in reserved:
        day_val = r.day.value if hasattr(r.day, 'value') else r.day
        slot = (day_val, r.slot_index)
        is_break = is_break_reason(r.reason)
        if r.section_id is not None and is_break:
            recess_slots.add((r.section_id, day_val, r.slot_index))
            allowed_break_slots.add((r.section_id, day_val, r.slot_index))
        elif is_break:
            # Global recess/lunch rows apply to every active section.
            section_breaks = {(section.id, day_val, r.slot_index) for section in sections}
            recess_slots.update(section_breaks)
            allowed_break_slots.update(section_breaks)
        else:
            reserved_slots.add(slot)

    # Also mark timeslots that are flagged as reserved
    for ts in timeslots:
        if ts.is_reserved:
            day_val = ts.day.value if hasattr(ts.day, 'value') else ts.day
            slot = (day_val, ts.slot_index)
            if is_break_reason(ts.reservation_reason):
                section_breaks = {(section.id, day_val, ts.slot_index) for section in sections}
                recess_slots.update(section_breaks)
                allowed_break_slots.update(section_breaks)
            else:
                reserved_slots.add(slot)

    expected_per_course = {c["id"]: c["weekly_sessions"] for c in enriched}
    valid_room_ids = {r.id for r in rooms_db if r.active}

    constraint_profile = get_current_profile(db)
    constraint_values = constraint_profile.config

    # Determine slots per day
    slots_per_day = 8
    if timeslots:
        max_slot = max(ts.slot_index for ts in timeslots)
        slots_per_day = max_slot + 1

    # Determine active days
    days_set = set()
    for ts in timeslots:
        day_val = ts.day.value if hasattr(ts.day, 'value') else ts.day
        days_set.add(day_val)
    days = sorted(days_set, key=lambda d: ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"].index(d)) if days_set else ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]

    # Resolve the coordinator's clock-time policy before the feasibility
    # preflight, so its weekly capacity bound can account for reserved first
    # periods that interact with C20.
    latest_start_time = time.fromisoformat(
        constraint_values.get("LATEST_SECTION_START_TIME", settings.MAX_SECTION_START_TIME)
    )
    latest_start_slot_by_day = {}
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

    # Catch weekly demand that cannot fit under coordinator-edited daily
    # limits before invoking either solver. These are necessary upper-bound
    # checks, so they only reject schedules that are mathematically impossible.
    section_period_demand = {}
    section_lecture_demand = {}
    teacher_period_demand = {}
    for course in enriched:
        periods = course["weekly_sessions"] * course["duration"]
        section_period_demand[course["section_id"]] = section_period_demand.get(course["section_id"], 0) + periods
        if course["course_type"] == "lecture":
            section_lecture_demand[course["section_id"]] = section_lecture_demand.get(course["section_id"], 0) + periods
        teacher_period_demand[course["teacher_id"]] = teacher_period_demand.get(course["teacher_id"], 0) + periods

    capacity_issues = []
    section_daily_limit = constraint_values["MAX_SECTION_DAILY_HOURS"]
    lecture_daily_limit = constraint_values["MAX_LECTURE_PERIODS_PER_DAY"]
    teacher_daily_limit = constraint_values["MAX_TEACHER_DAILY_HOURS"]
    consecutive_limit = constraint_values["MAX_CONSECUTIVE_PERIODS"]
    section_names = {section.id: section.name for section in sections}
    teacher_names = {teacher.id: teacher.name for teacher in teachers}
    section_capacity_groups = {}
    for section_id, demand in section_period_demand.items():
        # C19 disallows unexplained student gaps, so a section cannot take
        # classes on both sides of a non-break reserved slot. C20 also requires
        # at least one class before the cutoff. Select the most generous
        # eligible side, then cap its continuous runs using C11.
        week_capacity = 0
        for day in days:
            nonbreak_blocked = {slot for reserved_day, slot in reserved_slots if reserved_day == day}
            recess_blocked = {
                slot for section, recess_day, slot in recess_slots
                if section == section_id and recess_day == day
            }
            latest_slot = latest_start_slot_by_day.get(day, -1)
            day_capacity = 0
            region_start = 0
            for region_end in sorted((*nonbreak_blocked, slots_per_day)):
                region = range(region_start, region_end)
                usable_region = [slot for slot in region if slot not in recess_blocked]
                if any(slot <= latest_slot for slot in usable_region):
                    run_length = 0
                    region_capacity = 0
                    for slot in region:
                        if slot in recess_blocked:
                            region_capacity += min(run_length, consecutive_limit)
                            run_length = 0
                        else:
                            run_length += 1
                    region_capacity += min(run_length, consecutive_limit)
                    day_capacity = max(day_capacity, min(section_daily_limit, region_capacity))
                region_start = region_end + 1
            week_capacity += day_capacity

        if demand > week_capacity:
            section_capacity_groups.setdefault((demand, week_capacity), []).append(
                section_names.get(section_id, f"Section {section_id}")
            )
        lecture_demand = section_lecture_demand.get(section_id, 0)
        lecture_capacity = lecture_daily_limit * len(days)
        if lecture_demand > lecture_capacity:
            capacity_issues.append(
                f"{section_names.get(section_id, f'Section {section_id}')} needs {lecture_demand} lecture periods/week, "
                f"but C10 allows at most {lecture_capacity} ({lecture_daily_limit}/day × {len(days)} days)."
            )
    for teacher_id, demand in teacher_period_demand.items():
        capacity = teacher_daily_limit * len(days)
        if demand > capacity:
            capacity_issues.append(
                f"{teacher_names.get(teacher_id, f'Teacher {teacher_id}')} is assigned {demand} periods/week, "
                f"but C17 allows at most {capacity} ({teacher_daily_limit}/day × {len(days)} days)."
            )

    for (demand, capacity), names in section_capacity_groups.items():
        capacity_issues.append(
            f"{', '.join(names)} each need {demand} periods/week, but C11/C12/C19/C20 and the reserved-slot pattern "
            f"allow at most {capacity} periods across {len(days)} days (even this upper bound assumes every available run can be filled). "
            "Review the daily, consecutive-period, and first-class start limits together, or correct the weekly course load."
        )

    if capacity_issues:
        return {
            "status": "FAILED",
            "message": "The active constraint profile makes this schedule infeasible. See the capacity bottlenecks below.",
            "sessions_scheduled": 0,
            "sessions_expected": len(sessions),
            "hard_constraint_violations": 0,
            "soft_constraint_score": 0.0,
            "generation_time_ms": 0,
            "algorithm": "PREFLIGHT_CAPACITY_CHECK",
            "backtracks": 0,
            "restarts": 0,
            "bottlenecks": capacity_issues,
        }

    constraint_config = {
        "reserved_slots": reserved_slots,
        "recess_slots": recess_slots,
        "allowed_break_slots": allowed_break_slots,
        "honours_slots": set(),
        "HONOURS_RESERVED_ENABLED": settings.HONOURS_RESERVED_ENABLED,
        "teacher_unavailable": teacher_unavailable,
        "MAX_CONSECUTIVE_PERIODS": constraint_values["MAX_CONSECUTIVE_PERIODS"],
        "MAX_SECTION_DAILY_HOURS": constraint_values["MAX_SECTION_DAILY_HOURS"],
        "MAX_LECTURE_PERIODS_PER_DAY": constraint_values["MAX_LECTURE_PERIODS_PER_DAY"],
        "MAX_TEACHER_DAILY_HOURS": constraint_values["MAX_TEACHER_DAILY_HOURS"],
        "MAX_SECTION_START_SLOT": settings.MAX_SECTION_START_SLOT,
        "MAX_SECTION_START_SLOT_BY_DAY": latest_start_slot_by_day,
        # Keep full-schedule validation aligned with the master timeslot
        # pattern; C07's standalone default only covers the original 8-slot day.
        "max_slot_index": slots_per_day - 1,
        "SENIOR_FACULTY_CONSTRAINT_MODE": settings.SENIOR_FACULTY_CONSTRAINT_MODE,
        # A valid timetable should also be usable by students.  The optional
        # optimization control selects a dynamic candidate ranking that spreads
        # a section over the week and then avoids within-day idle gaps.
        "PREFER_BALANCED_DAYS": enable_optimization,
        "expected_sessions_per_course": expected_per_course,
        "valid_room_ids": valid_room_ids,
    }

    solver_config = SolverConfig(
        timeout_seconds=timeout,
        max_restarts=settings.SCHEDULER_MAX_RESTARTS,
        debug=settings.SCHEDULER_DEBUG,
        days=days,
        slots_per_day=slots_per_day,
        constraint_config=constraint_config,
    )

    # CP-SAT is the primary solver. The CSP's constructive search remains a
    # fallback for an unavailable solver or a model/data edge case.
    result = CPSATSolver(solver_config).solve(sessions, room_infos)
    if result.status != "VALID":
        logger.warning(
            "CP-SAT did not produce a valid timetable for %s (%s); trying CSP fallback",
            scope_label,
            result.status,
        )
        fallback = CSPSolver(solver_config).solve(sessions, room_infos)
        if fallback.status == "VALID":
            result = fallback

    # Compute soft score
    soft_score = 0.0
    if result.status == "VALID" and result.assignments:
        soft_score = compute_soft_score(result.assignments)

    # Persist
    schedule = GeneratedSchedule(
        generated_at=datetime.utcnow(),
        status=ScheduleStatus.VALID if result.status == "VALID" else ScheduleStatus.FAILED,
        hard_constraint_violations=result.hard_constraint_violations,
        soft_constraint_score=soft_score,
        generation_time_ms=result.generation_time_ms,
        algorithm=result.algorithm,
        backtracks=result.backtracks,
        restarts=result.restarts,
        constraint_profile_version=constraint_profile.version,
        constraint_config_snapshot=dict(constraint_values),
    )
    db.add(schedule)
    db.flush()

    # Build timeslot map for persistence
    ts_map = {}
    for ts in timeslots:
        day_val = ts.day.value if hasattr(ts.day, 'value') else ts.day
        ts_map[(day_val, ts.slot_index)] = ts

    if result.status == "VALID":
        for a in result.assignments:
            ts = ts_map.get((a.day, a.slot_index))
            db.add(TimetableSession(
                course_id=a.course_id,
                section_id=a.section_id,
                teacher_id=a.teacher_id,
                room_id=a.room_id,
                timeslot_id=ts.id if ts else 0,
                day=a.day,
                start_time=ts.start_time if ts else "09:00",
                end_time=ts.end_time if ts else "10:00",
                session_number=1,
                generated_schedule_id=schedule.id,
            ))
        db.commit()
    else:
        db.commit()

    return {
        "status": result.status,
        "schedule_id": schedule.id,
        "generation_time_ms": result.generation_time_ms,
        "hard_constraint_violations": result.hard_constraint_violations,
        "soft_constraint_score": soft_score,
        "sessions_scheduled": result.sessions_scheduled,
        "sessions_expected": result.sessions_expected,
        "backtracks": result.backtracks,
        "restarts": result.restarts,
        "algorithm": result.algorithm,
        "unscheduled_sessions": result.unscheduled_sessions,
        "bottlenecks": result.bottlenecks,
    }
