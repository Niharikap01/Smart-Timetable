from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.database.session import Base
import enum


class CourseType(str, enum.Enum):
    LECTURE = "lecture"
    LAB = "lab"
    TUTORIAL = "tutorial"


class RoomType(str, enum.Enum):
    LECTURE = "lecture"
    LAB = "lab"


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    course_code = Column(String(50), nullable=False, index=True)
    course_name = Column(String(200), nullable=False)
    course_type = Column(SAEnum(CourseType), nullable=False)
    weekly_sessions = Column(Integer, nullable=False)
    duration = Column(Integer, nullable=False, default=1)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    required_room_type = Column(SAEnum(RoomType), nullable=False)
    priority = Column(Integer, nullable=False, default=5)
    active = Column(Boolean, nullable=False, default=True)
    # Courses sharing the same (section_id, link_group) must be placed in the
    # same (day, slot_index) by the solver, e.g. link_group="ELEC1" for the
    # DPD/ECOM/IDPS cluster, or link_group="LAB1" for a parallel lab pair.
    # NULL = ordinary course, scheduled independently.
    link_group = Column(String(50), nullable=True, index=True)
    # Free-text label for which batches this offering serves, e.g. "B1/B2".
    # Not used by the solver — for display/reporting only.
    batch_label = Column(String(50), nullable=True)

    section = relationship("Section", back_populates="courses")
    teacher = relationship("Teacher", back_populates="courses")
    timetable_sessions = relationship("TimetableSession", back_populates="course")
