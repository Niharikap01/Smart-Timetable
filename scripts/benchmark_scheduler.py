"""Benchmark the CSP scheduler with synthetic datasets."""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.scheduler.csp_solver import CSPSolver, SolverConfig
from app.scheduler.session_expander import expand_sessions
from app.scheduler.domain import RoomInfo


def benchmark(label, courses, rooms, days, slots_per_day=8, timeout=30):
    sessions = expand_sessions(courses)
    config = SolverConfig(
        timeout_seconds=timeout, max_restarts=3, debug=False,
        days=days, slots_per_day=slots_per_day,
        constraint_config={
            "reserved_slots": set(), "recess_slots": set(),
            "honours_slots": set(), "HONOURS_RESERVED_ENABLED": False,
            "teacher_unavailable": set(),
            "MAX_CONSECUTIVE_PERIODS": 3, "MAX_SECTION_DAILY_HOURS": 6,
            "MAX_LECTURE_PERIODS_PER_DAY": 5, "MAX_TEACHER_DAILY_HOURS": 7,
        },
    )
    solver = CSPSolver(config)
    result = solver.solve(sessions, rooms)
    print(f"\n{'='*60}")
    print(f"Dataset:       {label}")
    print(f"Sessions:      {result.sessions_expected}")
    print(f"Rooms:         {len(rooms)}")
    print(f"Timeslots:     {len(days) * slots_per_day}")
    print(f"Status:        {result.status}")
    print(f"Scheduled:     {result.sessions_scheduled}/{result.sessions_expected}")
    print(f"Time (ms):     {result.generation_time_ms}")
    print(f"Backtracks:    {result.backtracks}")
    print(f"Restarts:      {result.restarts}")
    print(f"Violations:    {result.hard_constraint_violations}")


if __name__ == "__main__":
    days5 = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    # Small dataset
    small_courses = [
        {"id": i, "course_code": f"CS{i}", "course_name": f"Course {i}", "course_type": "lecture",
         "weekly_sessions": 3, "duration": 1, "section_id": 1, "teacher_id": (i % 3) + 1,
         "required_room_type": "lecture", "section_strength": 50, "faculty_type": "regular", "priority": 5}
        for i in range(1, 6)
    ]
    small_rooms = [RoomInfo(i, f"CR-{i}", "lecture", 60) for i in range(1, 4)]
    benchmark("Small (5 courses, 3 rooms)", small_courses, small_rooms, days5)

    # Medium dataset
    med_courses = []
    cid = 1
    for sec in range(1, 4):
        for i in range(1, 9):
            med_courses.append({
                "id": cid, "course_code": f"CS{cid}", "course_name": f"C{cid}",
                "course_type": "lecture" if i <= 6 else "lab",
                "weekly_sessions": 3 if i <= 6 else 1,
                "duration": 1 if i <= 6 else 2,
                "section_id": sec, "teacher_id": (cid % 8) + 1,
                "required_room_type": "lecture" if i <= 6 else "lab",
                "section_strength": 55, "faculty_type": "regular", "priority": 5,
            })
            cid += 1
    med_rooms = [RoomInfo(i, f"CR-{i}", "lecture", 65) for i in range(1, 7)]
    med_rooms += [RoomInfo(i + 6, f"LAB-{i}", "lab", 60) for i in range(1, 4)]
    benchmark("Medium (3 sections, 24 courses)", med_courses, med_rooms, days5)

    print(f"\n{'='*60}\nBenchmark complete.")
