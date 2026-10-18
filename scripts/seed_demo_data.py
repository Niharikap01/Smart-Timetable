"""Load a complete, clearly-labelled CSE-V demonstration dataset.

This is intentionally fictional.  It is for exercising the real scheduling
engine before official departmental data is available.  Re-running this script
replaces the current local SQLite data with the same predictable demo dataset.

Run from the project root:
    C:\\Users\\HP\\AppData\\Local\\Programs\\Python\\Python311\\python.exe scripts/seed_demo_data.py
"""

import os
import sys
from datetime import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.security import hash_password
from app.database.session import Base, SessionLocal, engine
from app.models import (
    Course,
    GeneratedSchedule,
    ReservedSlot,
    Room,
    Section,
    Teacher,
    TeacherAvailability,
    Timeslot,
    TimetableSession,
    User,
)


DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
SLOT_TIMES = [
    (9, 10), (10, 11), (11, 12), (12, 13),
    (13, 14), (14, 15), (15, 16), (16, 17),
]

# Semester V / third-year CSE data is deliberately shaped like a departmental
# timetable: comparable section sizes, multiple rooms, shared subject faculty,
# parallel laboratory batches, elective baskets, and a visiting-faculty slot.
SECTIONS = [
    ("CSE-5A1", 58), ("CSE-5A2", 60), ("CSE-5A3", 56),
    ("CSE-5A4", 62), ("CSE-5A5", 59), ("CSE-5A6", 61),
    ("CSE-5A7", 57), ("CSE-5A8", 60), ("CSE-5A9", 55),
]

TEACHERS = [
    ("ML-1", "Dr. Ananya Deshmukh", "senior"),
    ("ML-2", "Dr. Rohan Kulkarni", "regular"),
    ("ML-3", "Dr. Meera Iyer", "regular"),
    ("SE-1", "Prof. S. R. Patil", "senior"),
    ("SE-2", "Dr. Nikhil Sharma", "regular"),
    ("SE-3", "Ms. Kavita Joshi", "contract"),
    ("CC-1", "Dr. Priya Nair", "regular"),
    ("CC-2", "Mr. Arjun Verma", "regular"),
    ("CC-3", "Dr. Farah Khan", "regular"),
    ("DB-1", "Dr. Shweta Rao", "senior"),
    ("DB-2", "Dr. Amit Joshi", "regular"),
    ("DB-3", "Ms. Pooja Mehta", "regular"),
    ("DS-1", "Dr. Sana Khan", "regular"),
    ("DS-2", "Dr. Harish Babu", "regular"),
    ("DS-3", "Ms. Ritu Singh", "regular"),
    ("CS-1", "Dr. Vivek Menon", "regular"),
    ("CS-2", "Ms. Nandini Roy", "regular"),
    ("CS-3", "Mr. Karan Shah", "regular"),
    ("SEM-1", "Dr. Ashok Kumar", "visiting"),
    ("SEM-2", "Ms. Leena Dutta", "visiting"),
    ("LAB-1", "Ms. Neha Gupta", "regular"),
    ("LAB-2", "Mr. Kunal Bhat", "regular"),
    ("LAB-3", "Ms. Isha Kapoor", "regular"),
    ("LAB-4", "Mr. Deepak Saha", "regular"),
    ("LAB-5", "Ms. Swati Kulkarni", "regular"),
    ("LAB-6", "Mr. Prakash Jain", "regular"),
    ("LAB-7", "Ms. Tanvi Rao", "regular"),
    ("LAB-8", "Mr. Aditya Nene", "regular"),
    ("LAB-9", "Ms. Divya Nair", "regular"),
    ("LAB-10", "Mr. Gaurav Soni", "regular"),
]

LECTURE_ROOMS = [
    ("CSE-201", 72, 2), ("CSE-202", 72, 2), ("CSE-203", 72, 2),
    ("CSE-204", 68, 2), ("CSE-205", 68, 2), ("CSE-301", 66, 3),
    ("CSE-302", 66, 3), ("CSE-303", 66, 3), ("CSE-304", 66, 3),
    ("CSE-305", 66, 3),
]
LAB_ROOMS = [
    ("CSE-LAB-01", 72, 1), ("CSE-LAB-02", 70, 1),
    ("CSE-LAB-03", 68, 2), ("CSE-LAB-04", 68, 2),
    ("AI-LAB-01", 66, 3), ("PROJECT-LAB", 64, 3),
]


def add_course(db, *, code, name, course_type, weekly_sessions, duration,
               section_id, teacher_id, room_type, priority, link_group=None,
               batch_label=None):
    db.add(Course(
        course_code=code,
        course_name=name,
        course_type=course_type,
        weekly_sessions=weekly_sessions,
        duration=duration,
        section_id=section_id,
        teacher_id=teacher_id,
        required_room_type=room_type,
        priority=priority,
        link_group=link_group,
        batch_label=batch_label,
        active=True,
    ))


def seed_demo_data():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # A demo seed must be repeatable.  Delete child records before their
        # parent records so this also works when SQLite foreign keys are on.
        for model in [
            TimetableSession, GeneratedSchedule, ReservedSlot,
            TeacherAvailability, Course, Timeslot, Room, Section, Teacher, User,
        ]:
            db.query(model).delete()
        db.commit()

        db.add(User(
            username="demo_admin",
            hashed_password=hash_password("demo123"),
            is_admin=True,
        ))

        teachers = {}
        for index, (key, name, faculty_type) in enumerate(TEACHERS, start=1):
            teacher = Teacher(
                name=name,
                employee_id=f"DEMO-CSE-{index:03d}",
                email=f"demo.cse.{index:03d}@example.edu",
                faculty_type=faculty_type,
                max_daily_hours=7,
                preferences="Demo faculty record — replace with official data.",
                active=True,
            )
            db.add(teacher)
            teachers[key] = teacher

        sections = {}
        for name, strength in SECTIONS:
            section = Section(
                name=name,
                semester=5,
                strength=strength,
                program="CSE",
                year=3,
                active=True,
            )
            db.add(section)
            sections[name] = section

        for room_number, capacity, floor in LECTURE_ROOMS:
            db.add(Room(
                room_number=room_number,
                room_type="lecture",
                capacity=capacity,
                building="CSE Academic Block",
                floor=floor,
                active=True,
            ))
        for room_number, capacity, floor in LAB_ROOMS:
            db.add(Room(
                room_number=room_number,
                room_type="lab",
                capacity=capacity,
                building="CSE Academic Block",
                floor=floor,
                active=True,
            ))

        for day in DAYS:
            for slot_index, (start_hour, end_hour) in enumerate(SLOT_TIMES):
                # 13:00–14:00 is an institution-wide lunch break.  It remains
                # visible in the timeslot data but unavailable to the solver.
                is_lunch = slot_index == 4
                db.add(Timeslot(
                    day=day,
                    start_time=time(start_hour),
                    end_time=time(end_hour),
                    slot_index=slot_index,
                    is_reserved=is_lunch,
                    reservation_reason="LUNCH BREAK" if is_lunch else None,
                ))

        db.flush()

        # A few declared absences make availability filtering visible during
        # testing.  Visiting seminar faculty are available Tue/Thu/Fri only,
        # excluding lunch (which is globally reserved anyway).
        visiting_available_days = {"Tuesday", "Thursday", "Friday"}
        for visiting_key in ("SEM-1", "SEM-2"):
            for day in DAYS:
                if day not in visiting_available_days:
                    for slot_index in range(len(SLOT_TIMES)):
                        db.add(TeacherAvailability(
                            teacher_id=teachers[visiting_key].id,
                            day=day,
                            slot_index=slot_index,
                            is_available=False,
                        ))

        for section_index, (section_name, _strength) in enumerate(SECTIONS):
            section = sections[section_name]
            rotation = section_index % 3
            group_prefix = section_name.replace("CSE-", "DEMO-")

            # Three-credit core lectures: shared faculty across the nine
            # sections gives the solver genuine cross-section faculty-conflict
            # work to perform while following the supplied A2 pattern.
            core_lectures = [
                ("CSE501", "Machine Learning", "ML"),
                ("CSE502", "Software Engineering", "SE"),
                ("CSE503", "Cloud Computing", "CC"),
            ]
            for code, name, subject_key in core_lectures:
                add_course(
                    db,
                    code=code,
                    name=name,
                    course_type="lecture",
                    weekly_sessions=3,
                    duration=1,
                    section_id=section.id,
                    teacher_id=teachers[f"{subject_key}-{rotation + 1}"].id,
                    room_type="lecture",
                    priority=6,
                )

            # The reference pattern: a three-credit DPD course, followed by
            # one-credit Design Patterns and Open Elective courses.
            add_course(
                db,
                code="CSE504",
                name="Distributed and Parallel Databases",
                course_type="lecture",
                weekly_sessions=3,
                duration=1,
                section_id=section.id,
                teacher_id=teachers[f"DB-{rotation + 1}"].id,
                room_type="lecture",
                priority=5,
            )
            add_course(
                db,
                code="CSE505",
                name="Design Patterns",
                course_type="lecture",
                weekly_sessions=1,
                duration=1,
                section_id=section.id,
                teacher_id=teachers[f"DS-{rotation + 1}"].id,
                room_type="lecture",
                priority=5,
            )
            add_course(
                db,
                code="CSE506",
                name="Open Elective: Professional Communication",
                course_type="lecture",
                weekly_sessions=1,
                duration=1,
                section_id=section.id,
                teacher_id=teachers[f"CS-{rotation + 1}"].id,
                room_type="lecture",
                priority=4,
            )

            # The practical is a two-hour parallel B1/B2 and B3/B4 lab pair.
            # Its link group intentionally permits the paired records to share
            # one section slot while ensuring different laboratories are used.
            lab_keys = [
                f"LAB-{(section_index * 2) % 10 + 1}",
                f"LAB-{(section_index * 2 + 1) % 10 + 1}",
            ]
            lab_offerings = [
                ("CSE5P01", "Machine Learning Laboratory", f"{group_prefix}-ML-CC-LAB", "B1/B2", lab_keys[0]),
                ("CSE5P03", "Cloud Computing Laboratory", f"{group_prefix}-ML-CC-LAB", "B3/B4", lab_keys[1]),
            ]
            for code, name, link_group, batch_label, teacher_key in lab_offerings:
                add_course(
                    db,
                    code=code,
                    name=name,
                    course_type="lab",
                    weekly_sessions=1,
                    duration=2,
                    section_id=section.id,
                    teacher_id=teachers[teacher_key].id,
                    room_type="lab",
                    priority=9,
                    link_group=link_group,
                    batch_label=batch_label,
                )

        # The explicit rows make the lunch rule visible in the reservations
        # list as well as in the timetable data.
        for day in DAYS:
            db.add(ReservedSlot(day=day, slot_index=4, reason="LUNCH BREAK"))
        # MDM is a department-wide fixed activity, not a course choice.  A
        # global reservation keeps 09:00–10:00 free for every section on the
        # three specified days while the timetable UI labels it explicitly.
        for day in ("Thursday", "Friday", "Saturday"):
            db.add(ReservedSlot(day=day, slot_index=0, reason="MDM"))

        db.commit()

        print("Demo data loaded successfully.")
        print("  Sections: 9 | Faculty: 30 | Rooms: 16 | Timeslots: 48")
        print("  Active course offerings: 72 | Session records to schedule: 144")
        print("  This is fictional test data. Replace it with official data when available.")
        print("  Demo login (if authentication is enabled): demo_admin / demo123")
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()
