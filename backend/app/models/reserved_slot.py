from sqlalchemy import Column, Integer, String, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import relationship
from app.database.session import Base
from app.models.timeslot import DayOfWeek


class ReservedSlot(Base):
    __tablename__ = "reserved_slots"

    id = Column(Integer, primary_key=True, index=True)
    day = Column(SAEnum(DayOfWeek), nullable=False)
    slot_index = Column(Integer, nullable=False)
    reason = Column(String(200), nullable=False)
    # NULL means a department-wide reservation. A value makes this a
    # section-specific block such as that section's recess period.
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=True, index=True)
    section = relationship("Section")
