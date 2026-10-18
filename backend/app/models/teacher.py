from sqlalchemy import Column, Integer, String, Boolean, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.database.session import Base
import enum


class FacultyType(str, enum.Enum):
    REGULAR = "regular"
    VISITING = "visiting"
    SENIOR = "senior"
    CONTRACT = "contract"


class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    employee_id = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(200), unique=True, nullable=False)
    max_daily_hours = Column(Integer, nullable=False, default=7)
    faculty_type = Column(
        SAEnum(FacultyType), nullable=False, default=FacultyType.REGULAR
    )
    preferences = Column(String(1000), nullable=True)
    active = Column(Boolean, nullable=False, default=True)

    courses = relationship("Course", back_populates="teacher")
    availability = relationship("TeacherAvailability", back_populates="teacher")
    timetable_sessions = relationship("TimetableSession", back_populates="teacher")
