from sqlalchemy import (
    Boolean, Column, ForeignKey, Integer, String, Table,
)
from sqlalchemy.orm import relationship

from app.database.session import Base


program_elective_group_sections = Table(
    "program_elective_group_sections",
    Base.metadata,
    Column("group_id", Integer, ForeignKey("program_elective_groups.id", ondelete="CASCADE"), primary_key=True),
    Column("section_id", Integer, ForeignKey("sections.id", ondelete="CASCADE"), primary_key=True),
)


class ProgramElective(Base):
    __tablename__ = "program_electives"

    id = Column(Integer, primary_key=True, index=True)
    semester = Column(Integer, nullable=False, index=True)
    course_code = Column(String(50), nullable=False)
    course_name = Column(String(200), nullable=False)
    weekly_sessions = Column(Integer, nullable=False)
    duration = Column(Integer, nullable=False, default=1)
    active = Column(Boolean, nullable=False, default=True)

    groups = relationship("ProgramElectiveGroup", back_populates="elective", cascade="all, delete-orphan")


class ProgramElectiveGroup(Base):
    __tablename__ = "program_elective_groups"

    id = Column(Integer, primary_key=True, index=True)
    program_elective_id = Column(Integer, ForeignKey("program_electives.id"), nullable=False, index=True)
    group_name = Column(String(100), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False, index=True)
    student_count = Column(Integer, nullable=False)
    active = Column(Boolean, nullable=False, default=True)

    elective = relationship("ProgramElective", back_populates="groups")
    teacher = relationship("Teacher")
    sections = relationship("Section", secondary=program_elective_group_sections)
    courses = relationship("Course", back_populates="program_elective_group")
