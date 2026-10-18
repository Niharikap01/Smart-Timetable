from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey,
    Enum as SAEnum, Time, JSON,
)
from sqlalchemy.orm import relationship
from app.database.session import Base
from app.models.timeslot import DayOfWeek
import enum
from datetime import datetime


class ScheduleStatus(str, enum.Enum):
    VALID = "VALID"
    FAILED = "FAILED"
    IN_PROGRESS = "IN_PROGRESS"


class GeneratedSchedule(Base):
    __tablename__ = "generated_schedules"

    id = Column(Integer, primary_key=True, index=True)
    generated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(SAEnum(ScheduleStatus), nullable=False)
    hard_constraint_violations = Column(Integer, nullable=False, default=0)
    soft_constraint_score = Column(Float, nullable=True)
    generation_time_ms = Column(Integer, nullable=True)
    algorithm = Column(String(100), nullable=False, default="GOOGLE_OR_TOOLS_CP_SAT")
    version = Column(String(50), nullable=True)
    backtracks = Column(Integer, nullable=True)
    restarts = Column(Integer, nullable=True)
    constraint_profile_version = Column(Integer, nullable=True)
    constraint_config_snapshot = Column(JSON, nullable=True)

    sessions = relationship("TimetableSession", back_populates="schedule")


class TimetableSession(Base):
    __tablename__ = "timetable_sessions"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    timeslot_id = Column(Integer, ForeignKey("timeslots.id"), nullable=False)
    day = Column(SAEnum(DayOfWeek), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    session_number = Column(Integer, nullable=False, default=1)
    generated_schedule_id = Column(
        Integer, ForeignKey("generated_schedules.id"), nullable=False
    )

    course = relationship("Course", back_populates="timetable_sessions")
    section = relationship("Section", back_populates="timetable_sessions")
    teacher = relationship("Teacher", back_populates="timetable_sessions")
    room = relationship("Room", back_populates="timetable_sessions")
    timeslot = relationship("Timeslot", back_populates="timetable_sessions")
    schedule = relationship("GeneratedSchedule", back_populates="sessions")
