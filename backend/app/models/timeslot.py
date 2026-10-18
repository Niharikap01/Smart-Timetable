from sqlalchemy import Column, Integer, String, Boolean, Time, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.database.session import Base
import enum


class DayOfWeek(str, enum.Enum):
    MONDAY = "Monday"
    TUESDAY = "Tuesday"
    WEDNESDAY = "Wednesday"
    THURSDAY = "Thursday"
    FRIDAY = "Friday"
    SATURDAY = "Saturday"


class Timeslot(Base):
    __tablename__ = "timeslots"

    id = Column(Integer, primary_key=True, index=True)
    day = Column(SAEnum(DayOfWeek), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    slot_index = Column(Integer, nullable=False)
    is_reserved = Column(Boolean, nullable=False, default=False)
    reservation_reason = Column(String(200), nullable=True)

    timetable_sessions = relationship("TimetableSession", back_populates="timeslot")
