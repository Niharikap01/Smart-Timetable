"""Seed verified CSE-V reference data from the supplied timetable workbook.

Only A2, A3, A5, A7 and A9 have assignments in that source. A1, A4, A6 and
A8 are structural records only. Room capacity and section strength are zero
until the department enters verified values; no capacity is invented here.
"""
import os
import sys
from datetime import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.database.session import Base, SessionLocal, engine
from app.models import (Course, GeneratedSchedule, ReservedSlot, Room, Section,
                        Teacher, TeacherAvailability, Timeslot, TimetableSession, User)
from app.core.security import hash_password

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
SLOT_TIMES = [(9, 10), (10, 11), (11, 12), (12, 13), (13, 14), (14, 15), (15, 16), (16, 17), (17, 18)]
SECTION_FACULTY = {
    "A2": ("Dr. Chithraja Rajan", "Khushboo Shah", "Pravin Khawse", "Dr. Abhijeet Raipurkar", "Kaushik Roy", "Samiha Khan", "Hirkani Padwad", "R. Rewatkar"),
    "A3": ("V. Kakani", "Kishor Peshwani", "Shital Shende", "Dr. Abhijeet Raipurkar", "Bhushan Gedam", "Samiha Khan", "Hirkani Padwad", "Komal Raut"),
    "A5": ("P. Dhule", "Leena Rokde", "Purva Gogte", "Dr. Rucha Shastrakar", "Bhushan Gedam", "Samiha Khan", "Kiran Ande", "Priyanka Mangalkar"),
    "A7": ("Dr. Abhishek Sahu", "Shraddha Ghodeswar", "Anshul Pande", "Dr. Rucha Shastrakar", "Kaushik Roy", "Samiha Khan", "Komal Adhav", "Komal Raut"),
    "A9": ("Dr. Abhishek Sahu", "Khushboo Shah", "Anshul Pande", "Dr. Abhijeet Raipurkar", "Bhushan Gedam", "Samiha Khan", "Barkha Dange", "Jaishree Wankhede"),
}
LAB_FACULTY = {
    "A2": ("Dr. Chithraja Rajan", "Jyotsana Nandagavli", "Shraddha Ghodeswar", "Hirkani Padwad"),
    "A3": ("Shubhangi Tirpude", "Madhura Garge", "Leena Rokde", "Hirkani Padwad"),
    "A5": ("Ashwini Raju Agashe", "Kishor Peshwani", "D. Borikar", "Kiran Ande"),
    "A7": ("Ayesha Khan", "Shital Shende", "D. Borikar", "Komal Adhav"),
    "A9": ("Dr. Abhishek Sahu", "Anshul Pande", "Nikita Katariya", "Nupur Banode Jaiswal"),
}
THEORY = [("24CS01TH0501", "Machine Learning", 3, None), ("24CS01TH0502", "Software Engineering", 3, None), ("24CS01TH0503", "Cloud Computing", 3, None), ("24CS01TH0506-DPD", "Distributed and Parallel Databases", 3, "ELECTIVE_CLUSTER"), ("24CS01TH0506-ECOM", "E-Commerce & ERP", 3, "ELECTIVE_CLUSTER"), ("24CS01TH0506-IDPS", "Intrusion Detection and Prevention System", 3, "ELECTIVE_CLUSTER"), ("24CS01TH0507", "Design Patterns", 1, None), ("24CSOEC01TH0505", "Open Elective", 1, None)]
LABS = [("24CS01PR0501", "Machine Learning Lab", "LAB_ML_CC", "B1/B2"), ("24CS01PR0503", "Cloud Computing Lab", "LAB_ML_CC", "B3/B4"), ("24CS01PR0502", "Software Engineering Lab", "LAB_SE_DP", "B1/B2"), ("24CS01PR0504", "Design Patterns Lab", "LAB_SE_DP", "B3/B4")]


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for model in [TimetableSession, GeneratedSchedule, ReservedSlot, TeacherAvailability, Course, Timeslot, Room, Section, Teacher, User]:
            db.query(model).delete()
        db.commit()
        db.add(User(username="admin", hashed_password=hash_password("admin123"), is_admin=True))
        teachers = {}
        for index, name in enumerate(sorted({n for row in SECTION_FACULTY.values() for n in row} | {n for row in LAB_FACULTY.values() for n in row}), 1):
            teacher = Teacher(name=name, employee_id=f"WORKBOOK-{index:03d}", email=f"workbook-{index:03d}@pending.local", faculty_type="regular")
            db.add(teacher); teachers[name] = teacher
        sections = {}
        for number in range(1, 10):
            label = f"A{number}"; section = Section(name=f"CSE-5{label}", semester=5, strength=0, program="CSE", year=3)
            db.add(section); sections[label] = section
        db.flush()
        room_numbers = ["DT-103", "DT-105", "DT-106", "DT-109", "DT-111", "DT-112", "DT-203", "DT-205", "DT-206", "DT-209", "DT-211", "DT-212", "DT-301", "DT-303", "DT-304", "DT-306", "DT-307", "DT-310", "DT-701", "DT-702", "DT-805", "DT-811"]
        labs = {"DT-105", "DT-109", "DT-111", "DT-205", "DT-211", "DT-303", "DT-306", "DT-307", "DT-805", "DT-811"}
        for number in room_numbers:
            db.add(Room(room_number=number, room_type="lab" if number in labs else "lecture", capacity=0))
        for day in DAYS:
            for idx, (start, end) in enumerate(SLOT_TIMES): db.add(Timeslot(day=day, start_time=time(start), end_time=time(end), slot_index=idx))
        db.flush()
        for label, faculty in SECTION_FACULTY.items():
            section = sections[label]
            for (code, name, weekly, group), teacher_name in zip(THEORY, faculty):
                db.add(Course(course_code=code, course_name=name, course_type="lecture", weekly_sessions=weekly, duration=1, section_id=section.id, teacher_id=teachers[teacher_name].id, required_room_type="lecture", priority=5, link_group=group))
            for (code, name, group, batch), teacher_name in zip(LABS, LAB_FACULTY[label]):
                db.add(Course(course_code=code, course_name=name, course_type="lab", weekly_sessions=1, duration=2, section_id=section.id, teacher_id=teachers[teacher_name].id, required_room_type="lab", priority=8, link_group=group, batch_label=batch))
        for day in ["Thursday", "Friday", "Saturday"]: db.add(ReservedSlot(day=day, slot_index=0, reason="MDM"))
        recesses = {"A2": {"Monday": 2, "Tuesday": 2, "Wednesday": 1, "Thursday": 1, "Friday": 2, "Saturday": 3}, "A3": {"Monday": 1, "Tuesday": 2, "Wednesday": 2, "Thursday": 2, "Friday": 2, "Saturday": 3}, "A5": {"Monday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 2, "Saturday": 3}, "A7": {"Monday": 1, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 2, "Saturday": 2}, "A9": {"Monday": 1, "Thursday": 3, "Friday": 3, "Saturday": 2}}
        for label, blocks in recesses.items():
            for day, slot in blocks.items(): db.add(ReservedSlot(day=day, slot_index=slot, reason="RECESS", section_id=sections[label].id))
        db.commit()
        print("Seeded verified CSE-V reference data. Set official section strengths and room capacities before generation.")
    finally:
        db.close()


if __name__ == "__main__": seed()
