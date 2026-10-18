from sqlalchemy import Column, Integer, ForeignKey, Boolean, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.database.session import Base
from app.models.timeslot import DayOfWeek


class TeacherAvailability(Base):
    __tablename__ = "teacher_availability"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    day = Column(SAEnum(DayOfWeek), nullable=False)
    slot_index = Column(Integer, nullable=False)
    is_available = Column(Boolean, nullable=False, default=True)

    teacher = relationship("Teacher", back_populates="availability")
