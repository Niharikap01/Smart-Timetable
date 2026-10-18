from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship
from app.database.session import Base


class Section(Base):
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    semester = Column(Integer, nullable=False)
    strength = Column(Integer, nullable=False)
    program = Column(String(100), nullable=False, default="CSE")
    year = Column(Integer, nullable=False)
    active = Column(Boolean, nullable=False, default=True)

    courses = relationship("Course", back_populates="section")
    timetable_sessions = relationship("TimetableSession", back_populates="section")
